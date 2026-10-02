"""Utilidades de texto para presentar los campos del CSV (sin inventar contenido)."""

from __future__ import annotations

import re
import unicodedata

_STEP_NUMBER = re.compile(r"^(\d+)(?:\s+|$)")
# Coma separadora salvo que esté entre dos dígitos (decimales: "1,5 kg").
_COMMA_SEPARATOR = re.compile(r"(?<!\d),|,(?!\d)")


def normalize_text(text: str) -> str:
    """Minúsculas y sin acentos (misma idea que `strip_accents='unicode'` del TF-IDF)."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def split_ingredients(raw: object) -> list[str]:
    """Convierte la celda `ingredients` en una lista de renglones.

    Tres fuentes del CSV (RecetasGratis, Kiwilimon, Cookpad) separan con `|`.
    Las otras cuatro (Yanuq, El Mueble, Vitónica, Directo al Paladar) guardaron
    los ingredientes separados por comas, así que solo ahí se parte por coma.
    """
    if not isinstance(raw, str) or not raw.strip():
        return []
    parts = raw.split("|") if "|" in raw else _COMMA_SEPARATOR.split(raw)
    return [p.strip() for p in parts if p.strip()]


def split_steps(raw: object) -> list[str]:
    """Convierte la celda `instructions` en pasos.

    Los pasos van separados por `|`. RecetasGratis y Cookpad los numeran
    ("1 Escurre..."); ese prefijo se quita únicamente cuando TODOS los pasos
    están numerados de forma consecutiva, para no recortar un "2 tazas de..."
    que sea parte del texto. Algunas recetas terminan con un número suelto ("... | 5"):
    al quitar la numeración queda un paso vacío, que se descarta.
    """
    if not isinstance(raw, str) or not raw.strip():
        return []
    steps = [s.strip() for s in raw.split("|") if s.strip()]
    numbered = bool(steps)
    for i, step in enumerate(steps, start=1):
        match = _STEP_NUMBER.match(step)
        if not match or int(match.group(1)) != i:
            numbered = False
            break
    if numbered:
        steps = [s for s in (_STEP_NUMBER.sub("", s, count=1).strip() for s in steps) if s]
    return steps


def split_tags(raw: object) -> list[str]:
    """Convierte `category_tags` / `diet_tags` (separados por `|`) en lista."""
    if not isinstance(raw, str) or not raw.strip():
        return []
    return [t.strip() for t in raw.split("|") if t.strip()]
