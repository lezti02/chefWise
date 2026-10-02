#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Limpieza y estandarización de la base de recetas (recetas_unificadas_limpias.csv)

Uso:
    python limpiar_recetas.py --input recetas_unificadas_limpias.csv \
                              --output recetas_limpias.csv \
                              --report-dir informe [--strict-url-dedup]

Orden de ejecución (los números son los de las reglas originales):
    8a  Deduplicación por URL
    5   Desparseo de listas de Python
    4   Mojibake / emojis / entidades HTML / '<' '>' como separadores
    1   Marcas comerciales, electrodomésticos y símbolos ® ™
    2   Referencias a Kiwilimón
    6   Autopromoción y enlaces
    3   Tiempos (listed_time_min)
    7   Dificultades
    8b  Recetas sin instrucciones
    --  Eliminación de 'context' y regeneración de columnas derivadas
"""
import argparse
import ast
import html
import json
import re
import unicodedata
from collections import Counter, OrderedDict
from pathlib import Path

import numpy as np
import pandas as pd

TEXT_COLS = ["name", "ingredients", "instructions"]
STATS = Counter()      # ocurrencias por regla  {(paso, etiqueta): n}
EXAMPLES = {}          # ejemplos antes/después por paso
AUDIT = Counter()      # candidatos a marca no cubiertos (preceden a ® / ™)
AUDIT_EX = {}


# ----------------------------------------------------------------------------
# Utilidades generales
# ----------------------------------------------------------------------------
def tidy(t: str) -> str:
    """Limpieza de espacios/puntuación; solo se aplica a textos ya modificados."""
    segs = []
    for s in t.split(" | "):
        s = re.sub(r"[ \t\u00a0]{2,}", " ", s)
        s = re.sub(r"\(\s*[,;.:\-]?\s*\)", "", s)
        s = re.sub(r"\s+([,.;:!?])", r"\1", s)
        s = re.sub(r"([,;:])(\s*\1)+", r"\1", s)
        s = re.sub(r",\s*([.;:!?])", r"\1", s)
        s = re.sub(r"\b(?:de|del|con|para|y)\s*(?=[,.;:!?)]|$)", "", s, flags=re.I)
        s = re.sub(r"[ \t]{2,}", " ", s)
        s = re.sub(r",\s*$", "", s)
        s = s.strip(" ,;")
        if s:
            segs.append(s)
    return " | ".join(segs)


def _is_start(s: str, pos: int) -> bool:
    pre = s[:pos].rstrip()
    return (not pre) or pre[-1] in "|.!?:¡¿("


def rsub(rx, repl, t, step, label):
    """re.sub con conteo de ocurrencias y capitalización según contexto."""
    def f(m):
        r = repl(m) if callable(repl) else m.expand(repl)
        if r and _is_start(m.string, m.start()):
            r = r[0].upper() + r[1:]
        return r
    t2, n = rx.subn(f, t)
    if n:
        STATS[(step, label)] += n
    return t2


def renumber(t: str) -> str:
    segs = [s for s in t.split(" | ") if s.strip()]
    if segs and all(re.match(r"^\d+\s", s) for s in segs):
        segs = [f"{i} {re.sub(r'^\d+\s+', '', s)}" for i, s in enumerate(segs, 1)]
    return " | ".join(segs)


def snippet(old, new, w=55):
    p, m = 0, min(len(old), len(new))
    while p < m and old[p] == new[p]:
        p += 1
    q = 0
    while q < m - p and old[-1 - q] == new[-1 - q]:
        q += 1
    a = max(0, p - w)
    return old[a:len(old) - q + w][:230], new[a:len(new) - q + w][:230]


def apply_step(df, step, cols, func, tracker):
    """Aplica func(texto)->texto a las columnas; registra filas modificadas."""
    for col in cols:
        old = df[col]
        new = old.map(lambda t: func(t) if isinstance(t, str) else t)
        mask = old.notna() & new.ne(old)
        for idx in df.index[mask]:
            tracker[step][col].add(idx)
            ex = EXAMPLES.setdefault(step, [])
            if len(ex) < 3:
                a, b = snippet(old[idx], new[idx])
                ex.append((col, int(df.at[idx, "recipe_id"]), a, b))
        df[col] = new


# ----------------------------------------------------------------------------
# PASO 5: listas de Python -> texto
# ----------------------------------------------------------------------------
def parse_pylist(t: str):
    s = t.strip()
    try:
        v = ast.literal_eval(s)
        if isinstance(v, (list, tuple)):
            return [str(x) for x in v]
    except Exception:
        pass
    inner = s.lstrip("[").rstrip("]").strip()           # lista truncada/malformada
    inner = inner.strip("'\" ")
    return re.split(r"""['"]\s*,\s*['"]""", inner)


def desparse_ingredients(t):
    if not re.match(r"^\s*\[", t):
        return t
    items = [re.sub(r"\s+", " ", i).strip() for i in parse_pylist(t)]
    STATS[("5", "ingredients: lista -> ' | '")] += 1
    return " | ".join(i for i in items if i)


def desparse_instructions(t):
    if not re.match(r"^\s*\[", t):
        return t
    items = [re.sub(r"\s+", " ", i).strip() for i in parse_pylist(t)]
    items = [re.sub(r"^\d+[.)]?\s+", "", i) for i in items if i]
    STATS[("5", "instructions: lista -> numerada")] += 1
    return " | ".join(f"{n} {i}" for n, i in enumerate(items, 1))


# ----------------------------------------------------------------------------
# PASO 4: mojibake, emojis, HTML, '<' '>'
# ----------------------------------------------------------------------------
_CONT = "".join(
    chr(b) if b in (0x81, 0x8D, 0x8F, 0x90, 0x9D) else bytes([b]).decode("cp1252")
    for b in range(0x80, 0xC0)
)
MOJI_RE = re.compile(
    rf"[ÂÃ][{_CONT}]|â[{_CONT}]{{2}}|ï[{_CONT}]{{2}}|ð[{_CONT}]{{3}}|[ÂÃâïð][{_CONT}]{{0,3}}"
)
EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\u2300-\u23FF"
    "\uFE0E\uFE0F\u200D\u20E3\U000E0020-\U000E007F]+"
)
INVISIBLE_RE = re.compile("[\u200b-\u200f\u202a-\u202e\u2060\ufeff]")
ENT_MAP = {"&#8206;": "", "&#8207;": "", "&#8243;": '"', "&#8242;": "'",
           "&#133;": "...", "&hellip;": "...", "&nbsp;": " ", "&#160;": " "}
ENT_RE = re.compile(r"&(?:#\d+|#x[0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);")
TAG_RE = re.compile(r"</?(?:br|p|b|i|u|em|strong|span|div|li|ul|ol|a|img)\b[^>]*>", re.I)


def _moji_fix(m):
    run = m.group(0)
    bs = bytearray()
    for ch in run:
        try:
            bs += ch.encode("cp1252")
        except UnicodeEncodeError:
            if ord(ch) < 256:
                bs.append(ord(ch))
            else:
                return ""
    try:
        return bytes(bs).decode("utf-8").replace("\xa0", " ")
    except UnicodeDecodeError:
        return ""         # secuencia irrecuperable (bytes perdidos) -> se elimina


def _math_to_plain(s):
    return "".join(unicodedata.normalize("NFKC", c) if 0x1D400 <= ord(c) <= 0x1D7FF else c for c in s)


def fix_encoding(t):
    o = t
    t2, n = MOJI_RE.subn(_moji_fix, t)
    if n:
        STATS[("4", "mojibake reparado/eliminado")] += n
    t = _math_to_plain(t2)
    t2, n = EMOJI_RE.subn("", t)
    if n:
        STATS[("4", "emojis/pictogramas eliminados")] += n
    t = t2
    for k, v in ENT_MAP.items():
        if k in t:
            STATS[("4", "entidad HTML " + k)] += t.count(k)
            t = t.replace(k, v)
    if ENT_RE.search(t):
        t, n = ENT_RE.subn(lambda m: html.unescape(m.group(0)), t)
        STATS[("4", "otras entidades HTML")] += n
    t, n = INVISIBLE_RE.subn("", t)
    if n:
        STATS[("4", "caracteres invisibles")] += n
    t, n = TAG_RE.subn(" ", t)
    if n:
        STATS[("4", "etiquetas HTML")] += n
    return tidy(t) if t != o else t


def fix_angle(t):
    if "<" not in t and ">" not in t:
        return t
    t = t.replace("<3", "\x00H\x00")           # corazón ASCII: se conserva
    t = re.sub(r"\bve<", "vez", t)             # errata detectada: 've<' = 'vez'

    def f(m):
        s, pre = m.string, (m.string[m.start() - 1] if m.start() else "")
        if m.start() == 0:
            return ""
        if m.end() == len(s):
            return "" if pre in ".!?" else "."
        return " " if pre in ".,;:!?" else ", "

    out = []
    for seg in t.split(" | "):
        seg2, n = re.subn(r"\s*[<>]+\s*", f, seg)
        STATS[("4", "'<' '>' usados como separador")] += n
        out.append(seg2)
    return tidy(" | ".join(out)).replace("\x00H\x00", "<3")


# ----------------------------------------------------------------------------
# PASO 1: marcas, electrodomésticos, ® y TM
# ----------------------------------------------------------------------------
M = r"(?:\s?[®™])?"       # símbolo opcional tras la marca
PRE = r"(?:\b(?:de\s+la\s+marca|de\s+marca|marca|de|del|tipo)\s+)?"


def _alt(names):
    return "|".join(sorted(names, key=len, reverse=True))


# Marcas ambiguas (palabras comunes): solo se tocan si van seguidas de ® / ™
WITH_MARK = [
    r"D['’]?Gari", r"Gari", r"San\s+Juan", r"Tres\s+Estrellas", r"Del\s+Fuerte", r"Santa\s+Clara",
    r"Primavera", r"Extra\s+Special", r"Extra\s+Especial", r"Huichol", r"D[eo]l?\s+Campo", r"Domino",
    r"Berries\s+Paradise", r"San\s+Marcos", r"Gloria", r"Tortillinas", r"Luigi", r"Chantilly", r"Eva",
    r"Langa", r"Dolores", r"Ades", r"Evenflo(?:\s+Advance)?", r"Virgen\s+In[eé]s", r"Clavel", r"Iberia",
    r"Singles", r"Capullo", r"Ol[eé]ico", r"Plenia", r"Emergen-C", r"Silk", r"Zumba\s+Pica", r"Sos",
    r"Kinder", r"La\s+Moderna", r"Mark", r"Lybra", r"Bormioli", r"Saníssimo", r"Not\s+Butter",
    r"Cocina\s+Mestiza", r"Hummus", r"Caperucita", r"Valle\s+Frut", r"Fuerte\s+Origen",
]
WITH_MARK_REPL = [          # (patrón, reemplazo genérico) — requieren ® / ™
    (r"PAM|Pam", "aceite en aerosol"),
    (r"Sidral\s+Mundet", "refresco de manzana"),
    (r"Reddi\s+Wip", "crema batida en aerosol"),
    (r"(?:[Oo]lla\s+de\s+)?Presi[oó]n\s+Express", "olla de presión"),
]
# Marcas inequívocas: se eliminan siempre (lista del usuario + hallazgos del análisis)
ALWAYS_USER = [r"McCormick", r"Great\s+Value", r"Bimbo", r"Nestl[eéè]", r"Barilla", r"Heinz",
               r"Quaker", r"Danone", r"Alpina", r"Herdez"]
ALWAYS_FOOD = [r"D['’]Gari", r"Gamesa", r"Nutrioli", r"Oikos", r"Fage", r"Kikkoman", r"Yoplait",
               r"Danette", r"Skwinkles", r"Libanius", r"Jumex", r"Clemente\s+Jacques", r"La\s+Coste[ñn]a",
               r"Embasa", r"Valle\s+Frut", r"La\s+Asturiana", r"T[ií]a\s+Rosa", r"Do[ñn]a\s+Mar[ií]a",
               r"La\s+Botanera", r"La\s+Moderna", r"Best\s+Foods", r"Hellmann['’]?s", r"Kraft", r"Lala",
               r"Calahua", r"Proan", r"Del\s+Monte", r"Rexal"]
ALWAYS_APPLIANCE = [r"Oster", r"Braun", r"Vitamix", r"Weber", r"T-?fal", r"Tefal", r"KitchenAid",
                    r"Nutri\s?bullet", r"Instant\s+Pot", r"Ninja", r"Cuisinart", r"Magimix", r"Moulinex",
                    r"Cecotec", r"Crock-?\s?Pot", r"Royal\s+Prestige", r"Taurus", r"Philips",
                    r"Samsung(?:\s+Family\s*Hub)?"]

RX_WITH_MARK = re.compile(rf"{PRE}\b(?:{_alt(WITH_MARK)})\s?[®™]")
RX_WITH_MARK_REPL = [(re.compile(rf"\b(?:{p})\s?[®™]"), r) for p, r in WITH_MARK_REPL]
RX_ALWAYS_USER = re.compile(rf"{PRE}\b(?:{_alt(ALWAYS_USER)})\b{M}", re.I)
RX_ALWAYS_FOOD = re.compile(rf"{PRE}\b(?:{_alt(ALWAYS_FOOD)})\b{M}", re.I)
RX_ALWAYS_APP = re.compile(rf"{PRE}\b(?:{_alt(ALWAYS_APPLIANCE)})\b{M}", re.I)

AUTO_STRIP = True      # elimina el token capitalizado que precede a ®/™ si no está en las listas
RX_AUTO = re.compile(rf"{PRE}\b[A-ZÁÉÍÓÚÑ][^\s®™]*\s?[®™]")
RX_RESIDUAL = re.compile(r"((?:[A-ZÁÉÍÓÚÑ][^\s®™]*\s+){0,2}[A-ZÁÉÍÓÚÑ][^\s®™]*)\s?[®™]")

THERMO = r"Thermomix(?:\s*(?:TM\s?-?\s?\d{1,2}\b|TM\b|T\d{2}\b))?"


def _knorr(m):
    had_de = bool(re.match(r"(?:de|del)\s", m.group(0), re.I))
    tomate = bool(re.search(r"tomate", m.group(0), re.I))
    pre = re.split(r"[|.;]", m.string[max(0, m.start() - 45):m.start()])[-1]
    if re.search(r"\b(?:cubos?|cubitos?|pastillas?|sobres?|cuadritos?|cucharad(?:a|ita)s?|latas?|"
                 r"paquetes?|envases?|bolsas?)\s*$", pre, re.I):
        return "de caldo en polvo" + (" de tomate" if tomate else "")
    if re.search(r"caldo|consom|sazon|sopa|polvo|salsa|aderezo|crema|mayonesa|concentrado|pur[eé]|"
                 r"jugo|sabor", pre, re.I):
        return " de tomate" if tomate else ""
    return ("de " if had_de else "") + "caldo en polvo" + (" de tomate" if tomate else "")


def _royal(m):
    return m.group(1) if m.group(1) else "polvo para hornear"


REPLACEMENTS = [
    # (etiqueta, regex, reemplazo)
    ("Philadelphia -> queso crema",
     re.compile(rf"(?:queso|crema)(?:\s+(?:crema|de\s+queso))?\s+(?:tipo\s+)?(?:de\s+)?Philadelphia{M}", re.I), "queso crema"),
    ("Philadelphia -> queso crema",
     re.compile(rf"(?<!estilo )(?<!estilo de )(?<!ciudad de )(?:tipo\s+)?Philadelphia{M}", re.I), "queso crema"),
    ("Thermomix -> robot de cocina",
     re.compile(rf"\bde\s+(?:la\s+)?{THERMO}{M}", re.I), "del robot de cocina"),
    ("Thermomix -> robot de cocina",
     re.compile(rf"\bla\s+{THERMO}{M}", re.I), "el robot de cocina"),
    ("Thermomix -> robot de cocina",
     re.compile(rf"\buna\s+{THERMO}{M}", re.I), "un robot de cocina"),
    ("Thermomix -> robot de cocina",
     re.compile(rf"\b(en|con|para|desde|sin|al|usando)\s+{THERMO}{M}", re.I), r"\1 el robot de cocina"),
    ("Thermomix -> robot de cocina",
     re.compile(rf"{THERMO}{M}", re.I), "robot de cocina"),
    ("Mycook/Bimby/Cookeo -> robot de cocina",
     re.compile(rf"\b(?:Mycook(?:\s+(?:Touch|Easy|Pro))?(?:\s+de\s+Taurus)?|Bimby|Cookeo|Thermochef){M}", re.I), "robot de cocina"),
    ("Maizena/Maicena -> fécula de maíz (dup.)",
     re.compile(rf"(f[eé]cula\s+de\s+ma[ií]z)\s+(?:marca\s+)?(?:Maizena|Maicena){M}", re.I), r"\1"),
    ("Maizena/Maicena -> fécula de maíz",
     re.compile(rf"\b(?:Maizena|Maicena){M}", re.I), "fécula de maíz"),
    ("Nutella -> crema de avellanas y cacao",
     re.compile(rf"(?:crema\s+de\s+avellanas?(?:\s+y\s+cacao)?\s+|chocolate\s+para\s+untar\s+)?(?:tipo\s+)?Nutella{M}", re.I),
     "crema de avellanas y cacao"),
    ("Oreo -> galletas de chocolate rellenas",
     re.compile(rf"\bgalleta\s+(?:tipo\s+)?Oreo{M}", re.I), "galleta de chocolate rellena"),
    ("Oreo -> galletas de chocolate rellenas",
     re.compile(rf"\b(?:1|una?)\s+Oreo{M}\b", re.I), "1 galleta de chocolate rellena"),
    ("Oreo -> galletas de chocolate rellenas",
     re.compile(rf"(?:galletas?|galletitas?)\s+(?:tipo\s+)?Oreos?{M}", re.I), "galletas de chocolate rellenas"),
    ("Oreo -> galletas de chocolate rellenas",
     re.compile(rf"\bOreos?{M}", re.I), "galletas de chocolate rellenas"),
    ("Knorr/Maggi -> caldo en polvo",
     re.compile(rf"(?:\b(?:de|del|marca|de\s+la\s+marca|de\s+marca)\s+)?\b(?:Knorr|Maggis?|Maggui)\b{M}"
                r"(?:\s+(?:Suiza|Tomate))?", re.I), _knorr),
    ("Royal (polvo para hornear)",
     re.compile(r"\bRoyal\b(?=\s+(?:polvo\s+(?:para|de)\s+hornear|para\s+hornear|levadura))\s*"), ""),
    ("Royal (polvo para hornear)",
     re.compile(r"((?:polvo\s+(?:para|de)\s+hornear|levadura\s+qu[ií]mica)\s+)?\bRoyal\b"
                r"(?!\s+(?i:Prestige|Icing|Canin|Oak|Jelly|Gala))" + M), _royal),
    ("La Lechera -> leche condensada",
     re.compile(rf"(leche\s+condensada\s+)?\bLa\s+Lechera{M}", re.I),
     lambda m: "leche condensada" if not m.group(1) else m.group(1)),
    ("Splenda -> edulcorante",
     re.compile(rf"(edulcorante|endulzante)\s+(?:bajo\s+en\s+calor[ií]as\s+)?(?:de\s+)?E?Splenda{M}", re.I), r"\1"),
    ("Splenda -> edulcorante",
     re.compile(rf"\bE?splenda{M}", re.I), "edulcorante"),
    ("Samsung Smart Oven -> horno",
     re.compile(r"Smart\s+Oven(?:\s+HotBlast)?(?:\s+de\s+Samsung)?", re.I), "horno"),
    ("Maggie (salsa/jugo) -> eliminada",
     re.compile(r"(?<=salsa )Maggie|(?<=jugo )Maggie|(?<=sazonador )Maggie|(?<=caldo )Maggie", re.I), ""),
    ("demaicena -> de fécula de maíz",
     re.compile(r"\bde(?:maizena|maicena)\b", re.I), "de fécula de maíz"),
    ("Pyrex -> refractario (dup.)",
     re.compile(rf"\b(refractario|recipiente|molde|fuente|charola|vasija)\s+(?:de\s+)?Pyrex{M}", re.I), r"\1"),
    ("Silpat -> tapete de silicón (dup.)",
     re.compile(rf"\b(?:tapete|alfombrilla|l[aá]mina|hoja)\s+(?:de\s+)?Silpat{M}", re.I), "tapete de silicón"),
    ("Lékué -> recipiente de silicón (dup.)",
     re.compile(rf"\b(?:recipiente|estuche|molde)\s+(?:de\s+)?L[eé]ku[eé]{M}", re.I), "recipiente de silicón"),
    ("Pyrex -> refractario",
     re.compile(rf"\bPyrex{M}", re.I), "refractario"),
    ("Silpat -> tapete de silicón",
     re.compile(rf"\bSilpat{M}", re.I), "tapete de silicón"),
    ("Lékué -> recipiente de silicón",
     re.compile(rf"\bL[eé]ku[eé]{M}", re.I), "recipiente de silicón"),
    ("Teflon -> antiadherente",
     re.compile(rf"\b(?:de\s+)?Tefl[oó]n{M}", re.I), "antiadherente"),
    ("Sidral Mundet -> refresco de manzana",
     re.compile(rf"\bSidral(?:\s+Mundet)?{M}", re.I), "refresco de manzana"),
]
ALWAYS_RULES = [("marca secundaria eliminada (lista del usuario)", RX_ALWAYS_USER),
                ("marca de alimento eliminada (hallazgo)", RX_ALWAYS_FOOD),
                ("marca de electrodoméstico/utensilio eliminada", RX_ALWAYS_APP)]


def clean_brands(t, is_name=False):
    o = t
    if is_name:     # "Thermomix Paella" -> "Paella" ; "Paella (Thermomix)" -> "Paella"
        t = rsub(re.compile(rf"^\s*{THERMO}{M}\s*[-–:]?\s+", re.I), "", t, "1", "Thermomix al inicio del título removido")
        t = rsub(re.compile(rf"\s*[-–:(]?\s*(?<!con )(?<!en )(?<!para )(?<!de ){THERMO}{M}\)?\s*$", re.I), "", t, "1", "Thermomix al final del título removido")
    # 1a) marcas ambiguas, solo si llevan ® / ™
    for rx, rep in RX_WITH_MARK_REPL:
        t = rsub(rx, rep, t, "1", "marca con ®/™ -> genérico")
    t = rsub(RX_WITH_MARK, "", t, "1", "marca ambigua + ®/™ eliminada")
    # 1b) reemplazos genéricos
    for label, rx, rep in REPLACEMENTS:
        t = rsub(rx, rep, t, "1", label)
    # 1c) eliminación de marcas
    for label, rx in ALWAYS_RULES:
        t = rsub(rx, "", t, "1", label)
    # 1d) auditoría de marcas no cubiertas (aún con ®/™)
    for m in RX_RESIDUAL.finditer(t):
        k = m.group(1).strip()
        AUDIT[k] += 1
        AUDIT_EX.setdefault(k, t[max(0, m.start() - 40):m.end() + 30])
    # 1e) marcas no listadas: token capitalizado inmediatamente antes de ®/™
    if AUTO_STRIP:
        t = rsub(RX_AUTO, "", t, "1", "marca no listada (token previo a ®/™) eliminada automáticamente")
    # 1f) símbolos ® ™ y TM suelto
    t, n = re.subn(r"\s?[®™]", "", t)
    if n:
        STATS[("1", "símbolos ®/™ eliminados")] += n
    t, n = re.subn(r"(?<=[a-záéíóúñ0-9])TM\b|\(?\bTM\s?-?\s?\d{1,2}\b\)?", "", t)
    if n:
        STATS[("1", "'TM' / modelo TM5 eliminado")] += n
    t = re.sub(r"\b(queso crema)(?:\s+(?:de\s+)?queso crema)+", r"\1", t, flags=re.I)
    t = re.sub(r"\b(recipiente de silicón)(?:\s+(?:de\s+)?\1)+", r"\1", t, flags=re.I)
    t = re.sub(r"\b(edulcorante|endulzante)\s+(?:o|y|/)\s+\1\b", r"\1", t, flags=re.I)
    return tidy(t) if t != o else t


# ----------------------------------------------------------------------------
# PASO 2: Kiwilimón
# ----------------------------------------------------------------------------
KIWI = r"kiwi\s?lim[oó]n"
K_RULES = [
    ("URL de kiwilimon", re.compile(r"\(?\s*(?:https?://|www\.)\S*kiwilimon\S*\s*\)?", re.I)),
    ("paréntesis con 'kiwilimon'", re.compile(rf"\s*\([^()|]*{KIWI}[^()|]*\)", re.I)),
    ("'ver receta ... en kiwilimon'",
     re.compile(rf",?\s*\bver\s+(?:la\s+)?receta[^|.;()]{{0,80}}?(?:en|de|del)\s+{KIWI}", re.I)),
    ("'receta de ... en kiwilimon'",
     re.compile(rf"\s*(?:\b(?:con|seg[uú]n|de)\s+)?(?:la\s+|esta\s+)?\breceta\s+(?:de\s+|del\s+|que\s+est[aá]\s+)?"
                rf"[^|.;()]{{0,80}}?\s*(?:en|de|del)\s+{KIWI}", re.I)),
    ("'los clásicos de kiwilimón'",
     re.compile(rf"[¡!]?\s*[^|.!¡?]*cl[aá]sicos\s+de\s+{KIWI}\s*[!.]?", re.I)),
]
K_FALLBACK = re.compile(rf"[^|.!?]*{KIWI}[^|.!?]*[.!?]?\s*", re.I)


def _prev_word(s, pos):
    w = re.findall(r"(\w+)\s*$", s[:pos])
    return w[0].lower() if w else ""


def _kiwi_name(m):
    if m.group(1):                      # "Kiwilimón" en una sola palabra
        return ""
    if _prev_word(m.string, m.start()) in {"de", "con", "y", "e", "o", "al", "el", "la", "un", "una", "del", "jugo", "sabor"}:
        return m.group(0)               # "Mojito de Kiwi Limón" = fruta kiwi + limón
    return ""


def clean_kiwi_name(t):
    o = t
    rx = re.compile(r"\s*[-–—|:]?\s*(?:\b(Kiwilim[oó]n)\b|\bKiwi\s+Lim[oó]n\b)", re.I)
    t = rsub(rx, _kiwi_name, t, "2", "'Kiwilimón' removido del título")
    return tidy(t) if t != o else t


def clean_kiwi_text(t, numbered=False):
    o = t
    if not re.search(KIWI, t, re.I):
        return t
    for label, rx in K_RULES:
        t = rsub(rx, "", t, "2", label)
    if re.search(KIWI, t, re.I):                       # mención residual -> se quita la oración
        segs = []
        for seg in t.split(" | "):
            seg, n = K_FALLBACK.subn("", seg)
            if n:
                STATS[("2", "oración residual con 'kiwilimon' eliminada")] += n
            segs.append(seg)
        t = " | ".join(segs)
    t = tidy(t)
    return renumber(t) if (numbered and " | " in o and t.count(" | ") != o.count(" | ")) else t


# ----------------------------------------------------------------------------
# PASO 6: autopromoción y enlaces
# ----------------------------------------------------------------------------
URL_RX = re.compile(r"(?:(?:Imagen|Foto|Truco|V[ií]deo|Video|Fuente)\s*:\s*)?"
                    r"(?:https?://\S+|\bwww\.\S+|\b[\w-]+\.(?:com|net|org|es|mx|blogspot\.com|wordpress\.com)\b(?:/\S*)?)", re.I)
CTA_RX = re.compile(r"consulta|visita|m[aá]s recetas|mira|descubre|encuentra|sigue|v[ií]deo|video|canal|blog|"
                    r"pincha|haz clic|click|entra", re.I)
PROMO_RX = re.compile(
    r"\b(?:mi|mis|nuestro|nuestra|nuestros|nuestras)\s+(?:blogs?|canal|perfil|p[aá]gina|web|sitio|youtube|instagram|facebook|tiktok|redes|recetario)\b"
    r"|\bs[ií]gu(?:enos|eme|enme|anos)\b|\bsuscr[ií]b(?:e|ete|ir|irte|ase|anse)\b|\bcampanita\b"
    r"|\b(?:instagram|facebook|tiktok|pinterest|telegram|whatsapp|twitter|youtube)\b"
    r"|\bvisit(?:a|ar|es|e|ando)\s+(?:\w+\s+){0,2}?(?:blog|canal|web|p[aá]gina|perfil|sitio)\b"
    r"|\bvisit(?:a|ar|es|e|ando)\s+(?-i:[A-ZÁÉÍÓÚÑ])"
    r"|[\w.+-]+@[\w-]+\.\w+|(?<![\w])@\w{3,}"
    r"|\bp[aá]sate\s+por\b|\becha\s+un\s+vistazo\s+a\s+mi\b", re.I)
PROMO_PAREN = re.compile(r"\s*\([^()|]*(?:\b(?:mi|nuestro)\s+(?:perfil|blogs?|canal|recetario)|instagram|youtube|facebook|tiktok)[^()|]*\)", re.I)
SENT_SPLIT = re.compile(r"(?<=[.!?])\s*(?=[A-ZÁÉÍÓÚÑ¡¿])|(?<=[.!?])\s+")
CLAUSE_SPLIT = re.compile(r"(?<=[,;])\s+")


def clean_promo(t, numbered=False):
    o = t
    if not (URL_RX.search(t) or PROMO_RX.search(t)):
        return t
    t, n = PROMO_PAREN.subn("", t)
    if n:
        STATS[("6", "paréntesis promocional eliminado (ej. '(receta en mi perfil)')")] += n
    segs, dropped = [], 0
    for seg in t.split(" | "):
        keep = []
        if not numbered:        # ingredientes: se quita solo la cláusula promocional, no el ingrediente
            parts = CLAUSE_SPLIT.split(seg)
            if len(parts) > 1 and not PROMO_RX.search(parts[0]) and not URL_RX.search(parts[0]):
                good = [p_ for p_ in parts if not PROMO_RX.search(p_) and not (URL_RX.search(p_) and CTA_RX.search(p_))]
                if len(good) < len(parts):
                    dropped += 1
                    STATS[("6", "cláusula promocional removida de un ingrediente")] += 1
                    seg = " ".join(good)
        for sent in SENT_SPLIT.split(seg):
            if URL_RX.search(sent):
                if CTA_RX.search(sent) or PROMO_RX.search(sent):
                    dropped += 1
                    STATS[("6", "oración con enlace + llamada a la acción")] += 1
                    continue
                sent = URL_RX.sub("", sent)
                STATS[("6", "URL suelta eliminada")] += 1
            elif PROMO_RX.search(sent):
                dropped += 1
                STATS[("6", "oración autopromocional eliminada")] += 1
                continue
            keep.append(sent)
        seg2 = " ".join(keep).strip()
        if re.fullmatch(r"\d*\W*", seg2):
            seg2 = ""
        if seg2:
            segs.append(seg2)
    t = tidy(" | ".join(segs))
    return renumber(t) if (numbered and dropped and " | " in o) else t


# ----------------------------------------------------------------------------
# Derivadas
# ----------------------------------------------------------------------------
def make_key(s):
    s = unicodedata.normalize("NFKD", str(s).lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s)).strip()


def build_recipe_text(r):
    cols = ["name", "ingredients", "category_tags", "diet_tags", "meal_type", "app_category", "country", "difficulty"]
    return " | ".join(str(r[c]) for c in cols if pd.notna(r[c]) and str(r[c]).strip())


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="/mnt/user-data/uploads/recetas_unificadas_limpias.csv")
    ap.add_argument("--output", default="/mnt/user-data/outputs/recetas_limpias.csv")
    ap.add_argument("--report-dir", default="/mnt/user-data/outputs")
    ap.add_argument("--no-auto-strip-marked-brands", action="store_true",
                    help="no elimina automáticamente el token que precede a ®/™ cuando la marca no está en las listas")
    ap.add_argument("--strict-url-dedup", action="store_true",
                    help="elimina TODAS las filas con URL repetida (incluye recetas distintas que comparten URL)")
    a = ap.parse_args()
    global AUTO_STRIP
    AUTO_STRIP = not a.no_auto_strip_marked_brands
    outdir = Path(a.report_dir)
    outdir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(a.input)
    n_in, cols_in = len(df), list(df.columns)
    orig = df.copy()
    tracker = {k: {c: set() for c in df.columns} for k in ["8a", "5", "4", "1", "2", "6", "3", "7", "8b"]}
    notes = {}

    # ---- 8a. Deduplicación por URL -------------------------------------------------
    dup_url = df.url.duplicated(keep="first")
    dup_url_name = df.duplicated(subset=["url", "name_key"], keep="first")
    notes["8a"] = {
        "filas con URL repetida (regla estricta)": int(dup_url.sum()),
        "URLs distintas afectadas": int(df.url[df.url.duplicated(keep=False)].nunique()),
        "filas duplicadas reales (misma URL y mismo nombre)": int(dup_url_name.sum()),
        "modo aplicado": "ESTRICTO (solo URL)" if a.strict_url_dedup else "SEGURO (URL + nombre)",
    }
    drop_mask = dup_url if a.strict_url_dedup else dup_url_name
    removed_8a = int(drop_mask.sum())
    df = df[~drop_mask].copy()

    # ---- 5. Listas de Python -------------------------------------------------------
    apply_step(df, "5", ["ingredients"], desparse_ingredients, tracker)
    apply_step(df, "5", ["instructions"], desparse_instructions, tracker)

    # ---- 4. Mojibake / HTML / emojis / separadores ---------------------------------
    apply_step(df, "4", TEXT_COLS, fix_encoding, tracker)
    apply_step(df, "4", ["ingredients", "instructions"], fix_angle, tracker)

    # ---- 1. Marcas -----------------------------------------------------------------
    apply_step(df, "1", ["name"], lambda t: clean_brands(t, True), tracker)
    apply_step(df, "1", ["ingredients", "instructions"], clean_brands, tracker)

    # ---- 2. Kiwilimón --------------------------------------------------------------
    apply_step(df, "2", ["name"], clean_kiwi_name, tracker)
    apply_step(df, "2", ["ingredients"], clean_kiwi_text, tracker)
    apply_step(df, "2", ["instructions"], lambda t: clean_kiwi_text(t, True), tracker)

    # ---- 6. Autopromoción ----------------------------------------------------------
    ctx_promo = int(df.context.fillna("").map(lambda t: bool(PROMO_RX.search(t))).sum())
    apply_step(df, "6", ["ingredients"], clean_promo, tracker)
    apply_step(df, "6", ["instructions"], lambda t: clean_promo(t, True), tracker)
    notes["6"] = {"filas con promo en 'context' (columna eliminada después)": ctx_promo}

    # ---- 3. Tiempos ----------------------------------------------------------------
    lt, tt = df.listed_time_min.copy(), df.total_time_min
    secs = lt.notna() & tt.notna() & np.isclose(lt, tt * 60)
    df.loc[secs, "listed_time_min"] = lt[secs] / 60
    tracker["3"]["listed_time_min"].update(df.index[secs])
    lt2 = df.listed_time_min
    need = lt2.isna() | (lt2 == 0)
    can = need & tt.notna() & (tt > 0)
    df.loc[can, "listed_time_min"] = tt[can]
    tracker["3"]["listed_time_min"].update(df.index[can])
    zero_left = (df.listed_time_min == 0)
    df.loc[zero_left, "listed_time_min"] = np.nan        # 0 min no es un tiempo válido
    tracker["3"]["listed_time_min"].update(df.index[zero_left])
    left_null = df.listed_time_min.isna()
    sus = df.listed_time_min.notna() & df.total_time_min.isna() & (df.listed_time_min >= 1440)
    notes["3"] = {
        "segundos -> minutos (listed = total*60)": int(secs.sum()),
        "nulos/0 imputados desde total_time_min": int(can.sum()),
        "0.0 sin total disponible -> NaN": int(zero_left.sum()),
        "nulos que NO se pueden imputar (total_time_min también nulo)": int(left_null.sum()),
        "listed_time_min >= 1440 sin total (posible placeholder, NO modificado)": int(sus.sum()),
    }

    # ---- 7. Dificultades -----------------------------------------------------------
    d_new = df.difficulty.str.strip().str.lower().replace({"muy baja": "baja", "muy alta": "alta"})
    app_map = {"baja": "facil", "media": "intermedio", "alta": "reto"}
    a_new = d_new.map(app_map)
    ch_d = df.difficulty.notna() & d_new.ne(df.difficulty)
    ch_a = df.app_difficulty.notna() & a_new.ne(df.app_difficulty)
    notes["7"] = {
        "difficulty llevada a minúsculas": int((df.difficulty.notna() & (df.difficulty != df.difficulty.str.lower())).sum()),
        "difficulty 'muy baja'/'muy alta' colapsada": int(df.difficulty.isin(["muy baja", "muy alta"]).sum()),
        "app_difficulty corregida": int(ch_a.sum()),
        "app_difficulty NaN con difficulty informada": int((a_new.isna() & d_new.notna()).sum()),
    }
    df["difficulty"], df["app_difficulty"] = d_new, a_new
    tracker["7"]["difficulty"].update(df.index[ch_d])
    tracker["7"]["app_difficulty"].update(df.index[ch_a])

    # ---- 8b. Sin instrucciones -----------------------------------------------------
    blank = df.instructions.isna() | df.instructions.fillna("").str.strip().eq("") | ~df.has_instructions
    rebuilt = 0
    for idx in df.index[blank]:
        c = df.at[idx, "context"]
        if isinstance(c, str) and len(re.findall(r"(?:^|\s)\d+[.)]\s", c)) >= 3:
            steps = [s.strip() for s in re.split(r"(?:^|\s)\d+[.)]\s", c) if s.strip()]
            df.at[idx, "instructions"] = " | ".join(f"{i} {s}" for i, s in enumerate(steps, 1))
            rebuilt += 1
        else:
            df.at[idx, "instructions"] = "Revisión requerida"
        tracker["8b"]["instructions"].add(idx)
    notes["8b"] = {"filas sin instrucciones": int(blank.sum()), "reconstruidas desde context": rebuilt,
                   "marcadas 'Revisión requerida'": int(blank.sum()) - rebuilt}

    # ---- Eliminar 'context' y regenerar derivadas -----------------------------------
    df = df.drop(columns=["context"])
    df["name_key"] = df["name"].map(make_key)
    df["ingredients_key"] = df["ingredients"].map(make_key)
    df["recipe_text"] = df.apply(build_recipe_text, axis=1)
    for src, dst in [("ingredients", "n_ingredients_approx"), ("instructions", "n_steps_approx")]:
        ch = pd.Index(sorted(set().union(*[tracker[s][src] for s in tracker])))
        ch = ch.intersection(df.index[orig.loc[df.index, dst].notna() & df[src].ne("Revisión requerida")])
        df.loc[ch, dst] = df.loc[ch, src].map(lambda t: float(t.count(" | ") + 1))

    out_cols = [c for c in cols_in if c != "context"]
    df[out_cols].to_csv(a.output, index=False, encoding="utf-8-sig")

    # ---- Informe -------------------------------------------------------------------
    titles = OrderedDict([
        ("8a", "8a · Deduplicación por URL"), ("5", "5 · Desparseo de listas de Python"),
        ("4", "4 · Mojibake, emojis, entidades HTML y '<' '>'"),
        ("1", "1 · Marcas comerciales, electrodomésticos y ®/™"), ("2", "2 · Referencias a Kiwilimón"),
        ("6", "6 · Autopromoción y enlaces"), ("3", "3 · Tiempos (listed_time_min)"),
        ("7", "7 · Estandarización de dificultades"), ("8b", "8b · Recetas sin instrucciones")])
    summary = OrderedDict()
    for k, ttl in titles.items():
        rows = set().union(*tracker[k].values())
        bycol = {c: len(v) for c, v in tracker[k].items() if v}
        if k == "8a":
            summary[k] = {"titulo": ttl, "filas_modificadas": removed_8a, "por_columna": {"(filas eliminadas)": removed_8a}}
        else:
            summary[k] = {"titulo": ttl, "filas_modificadas": len(rows), "por_columna": bycol}
        summary[k]["detalle_ocurrencias"] = {l: n for (s, l), n in sorted(STATS.items()) if s == k}
        summary[k]["notas"] = notes.get(k, {})
        summary[k]["ejemplos"] = EXAMPLES.get(k, [])
    all_rows = set().union(*[set().union(*tracker[k].values()) for k in tracker if k != "8a"])
    result = {"filas_entrada": n_in, "filas_salida": len(df), "filas_eliminadas": n_in - len(df),
              "filas_con_al_menos_un_cambio": len(all_rows), "columnas_entrada": len(cols_in),
              "columnas_salida": len(out_cols), "pasos": summary}
    (outdir / "informe_limpieza.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    L = ["# Informe de limpieza de recetas", "",
         f"- Filas de entrada: **{n_in:,}** · Filas de salida: **{len(df):,}** · Eliminadas: **{n_in - len(df):,}**",
         f"- Filas con al menos un cambio de contenido: **{len(all_rows):,}**",
         f"- Columnas: {len(cols_in)} -> {len(out_cols)} (eliminada `context`)", "",
         "| Paso | Registros modificados | Detalle por columna |", "|---|---:|---|"]
    for k, s in summary.items():
        L.append(f"| {s['titulo']} | {s['filas_modificadas']:,} | " +
                 (", ".join(f"{c}: {n:,}" for c, n in s["por_columna"].items()) or "—") + " |")
    L.append("")
    for k, s in summary.items():
        L += [f"## {s['titulo']}", f"**Registros modificados: {s['filas_modificadas']:,}**", ""]
        for kk, vv in s["notas"].items():
            L.append(f"- {kk}: **{vv}**")
        for kk, vv in s["detalle_ocurrencias"].items():
            L.append(f"- {kk}: {vv:,} ocurrencias")
        for col, rid, b, af in s["ejemplos"]:
            L += ["", f"  - ejemplo (`{col}`, recipe_id {rid}):", f"    - antes: `{b}`", f"    - después: `{af}`"]
        L.append("")
    (outdir / "informe_limpieza.md").write_text("\n".join(L), encoding="utf-8")

    pend = pd.DataFrame([(k, n, AUDIT_EX[k]) for k, n in AUDIT.most_common()], columns=["marca_detectada", "ocurrencias", "contexto"])
    pend.to_csv(outdir / "marcas_detectadas_por_simbolo.csv", index=False, encoding="utf-8-sig")
    print(json.dumps({k: v["filas_modificadas"] for k, v in summary.items()}, ensure_ascii=False))
    print("filas:", n_in, "->", len(df), "| marcas detectadas por ®/™ (revisar):", len(pend))


if __name__ == "__main__":
    main()
