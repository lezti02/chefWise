"""Evaluación offline de recomendadores (común a TF-IDF y a embeddings).

El proyecto no tiene interacciones de usuarios ni juicios humanos de relevancia, así que la
relevancia se define con una regla explícita y auditable sobre el propio catálogo:

    Una receta `d` es relevante para una receta consulta `q` si ambas son el mismo
    "tipo de plato" (p. ej. `tacos`, `ensalada`, `sopa_caldo`). El tipo de plato se deriva del
    NOMBRE con la taxonomía `DISH_FAMILIES` (primera coincidencia gana, buscando solo en las
    primeras `HEAD_WORDS` palabras para no confundir "pollo con ensalada" con una ensalada). Las
    familias dulces/saladas ambiguas ("pastel", "helado"...) exigen además la `app_category` correcta.

Esto es un proxy, no una verdad absoluta: mide si un modelo recupera platos del mismo tipo, no si
a una persona concreta le gustaría la receta. Las limitaciones están en el notebook 04.

El conjunto (`EvalSet`) se genera UNA vez con una semilla fija, se guarda en JSON con la relevancia
ya materializada y se reutiliza tal cual para cualquier modelo: así todos los modelos se comparan
con exactamente las mismas consultas, la misma relevancia y los mismos K.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

import numpy as np
import pandas as pd

from .config import PROJECT_ROOT

EVAL_DIR = PROJECT_ROOT / "data" / "evaluation"
EVAL_SET_PATH = EVAL_DIR / "eval_set_v1.json"
EVAL_SET_VERSION = "v1"

DEFAULT_KS = (5, 10)
DEFAULT_SEED = 42
DEFAULT_QUERIES_PER_GROUP = 10
DEFAULT_MIN_GROUP_SIZE = 20

# --------------------------------------------------------------------------- taxonomía

# (familia, regex sobre el nombre normalizado, categorías de la app permitidas o None).
# El ORDEN importa: gana la primera coincidencia ("ensalada de pasta" -> ensalada).
# Solo hay familias de tipo de plato; ninguna se define por ingrediente principal.
# `allowed` se usa solo para desambiguar palabras que sirven para platos dulces y salados.
HEAD_WORDS = 4
DISH_FAMILIES: tuple[tuple[str, str, frozenset[str] | None], ...] = (
    ("ensalada", r"\bensaladas?\b", None),
    ("sopa_caldo", r"\b(sopas?|caldos?|consomes?|pozole|gazpacho|salmorejo|caldillo)\b", None),
    ("tacos", r"\btacos?\b", None),
    ("enchiladas", r"\benchiladas?\b", None),
    ("quesadillas", r"\bquesadillas?\b", None),
    ("burritos", r"\bburritos?\b", None),
    ("tamales", r"\btamales?\b", None),
    ("tostadas", r"\btostadas?\b", None),
    ("pizza", r"\bpizzas?\b", None),
    ("hamburguesa", r"\bhamburguesas?\b", None),
    ("sandwich", r"\b(sandwich(es)?|emparedados?|bocadillos?)\b", None),
    ("pasta", r"\b(pastas?|espaguetis?|espagueti|spaghetti|tallarines|macarrones|lasana|canelones|fettuccine|fideos?|ravioles|noquis)\b", None),
    ("risotto_paella", r"\b(risottos?|paellas?)\b", None),
    ("ceviche", r"\bceviches?\b", None),
    ("empanadas", r"\bempanad(a|as|illas)\b", None),
    ("croquetas", r"\bcroquetas?\b", None),
    ("albondigas", r"\balbondigas?\b", None),
    ("brochetas", r"\bbrochetas?\b", None),
    ("quiche", r"\bquiches?\b", None),
    ("guiso_estofado", r"\b(guisos?|estofados?)\b", None),
    ("galletas", r"\b(galletas?|cookies?)\b", frozenset({"postre"})),
    ("cheesecake", r"\bcheesecakes?\b", frozenset({"postre"})),
    ("cupcakes_muffins", r"\b(cupcakes?|muffins?|magdalenas?)\b", frozenset({"postre"})),
    ("pastel_tarta", r"\b(pastel(es)?|tartas?|bizcochos?|panques?|brownies?)\b", frozenset({"postre"})),
    ("flan_natilla", r"\b(flanes?|natillas?)\b", frozenset({"postre"})),
    ("gelatina", r"\bgelatinas?\b", frozenset({"postre"})),
    ("mousse", r"\bmousses?\b", frozenset({"postre"})),
    ("helado", r"\b(helados?|nieves?|paletas?)\b", frozenset({"postre"})),
    ("batido_licuado", r"\b(batidos?|smoothies?|licuados?|malteadas?)\b", frozenset({"bebida"})),
    ("coctel_alcohol", r"\b(cocteles?|cocktails?|margaritas?|mojitos?|sangrias?)\b", frozenset({"bebida"})),
    ("mermelada", r"^(mermeladas?|confituras?|jaleas?)\b", None),
    # "salsa" solo cuenta si el plato ES una salsa (nombre que empieza así), no "pollo en salsa".
    ("dip_salsa", r"^(salsas?|aderezos?|dips?|guacamole|hummus)\b", None),
)

_COMPILED = tuple((name, re.compile(rx), cats) for name, rx, cats in DISH_FAMILIES)


def family_pattern(family: str) -> re.Pattern[str]:
    """Regex (sobre texto normalizado) con la que se detecta un tipo de plato."""
    for name, pattern, _ in _COMPILED:
        if name == family:
            return pattern
    raise KeyError(family)


def normalize_text(value: object) -> str:
    """Minúsculas, sin acentos ni signos: para aplicar la taxonomía de forma estable."""
    text = unicodedata.normalize("NFKD", str(value).lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def assign_dish_family(name: object, app_category: object) -> str | None:
    """Tipo de plato de una receta, o None si ninguna familia aplica."""
    normalized = " ".join(normalize_text(name).split()[:HEAD_WORDS])
    category = None if pd.isna(app_category) else str(app_category)
    for family, regex, allowed in _COMPILED:
        if regex.search(normalized) and (allowed is None or category in allowed):
            return family
    return None


def assign_groups(df: pd.DataFrame) -> pd.Series:
    """Grupo de evaluación (= tipo de plato) por receta; None si ninguna familia aplica."""
    groups = [assign_dish_family(n, c) for n, c in zip(df["name"], df["app_category"])]
    return pd.Series(groups, index=df.index, name="eval_group", dtype="object")


# ----------------------------------------------------------------------- conjunto de evaluación


@dataclass(frozen=True)
class EvalSet:
    """Consultas + relevancia ya materializada. Inmutable una vez generado."""

    version: str
    seed: int
    dataset_rows: int
    queries_per_group: int
    min_group_size: int
    queries: tuple[tuple[int, str], ...]  # (recipe_id de la consulta, grupo)
    groups: dict[str, frozenset[int]]  # grupo -> recipe_id de todas las recetas relevantes

    def relevant_for(self, recipe_id: int, group: str) -> frozenset[int]:
        """Relevantes para una consulta = su grupo sin ella misma."""
        return self.groups[group] - {recipe_id}

    def to_json(self) -> dict:
        return {
            "version": self.version,
            "seed": self.seed,
            "dataset_rows": self.dataset_rows,
            "queries_per_group": self.queries_per_group,
            "min_group_size": self.min_group_size,
            "relevance_rule": (
                "relevante = mismo tipo de plato (taxonomía DISH_FAMILIES sobre las primeras "
                f"{HEAD_WORDS} palabras del nombre); la propia consulta se excluye"
            ),
            "queries": [{"recipe_id": rid, "group": g} for rid, g in self.queries],
            "groups": {g: sorted(ids) for g, ids in sorted(self.groups.items())},
        }

    @classmethod
    def from_json(cls, payload: dict) -> "EvalSet":
        return cls(
            version=payload["version"],
            seed=payload["seed"],
            dataset_rows=payload["dataset_rows"],
            queries_per_group=payload["queries_per_group"],
            min_group_size=payload["min_group_size"],
            queries=tuple((int(q["recipe_id"]), q["group"]) for q in payload["queries"]),
            groups={g: frozenset(int(i) for i in ids) for g, ids in payload["groups"].items()},
        )


def build_eval_set(
    df: pd.DataFrame,
    *,
    seed: int = DEFAULT_SEED,
    queries_per_group: int = DEFAULT_QUERIES_PER_GROUP,
    min_group_size: int = DEFAULT_MIN_GROUP_SIZE,
) -> EvalSet:
    """Genera el conjunto de evaluación (muestreo estratificado por grupo, semilla fija).

    Solo entran grupos con al menos `min_group_size` recetas, para que haya suficientes
    relevantes por consulta. De cada grupo se muestrean `queries_per_group` consultas, de modo
    que ningún tipo de plato domine el promedio.
    """
    required = {"recipe_id", "name", "app_category"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas para construir el conjunto de evaluación: {sorted(missing)}")

    keys = assign_groups(df)
    members = df.loc[keys.notna(), ["recipe_id"]].assign(group=keys[keys.notna()])
    sizes = members.groupby("group")["recipe_id"].size()
    kept = sizes[sizes >= min_group_size].index

    rng = np.random.default_rng(seed)
    queries: list[tuple[int, str]] = []
    groups: dict[str, frozenset[int]] = {}
    for group in sorted(kept):
        ids = np.sort(members.loc[members["group"] == group, "recipe_id"].to_numpy())
        groups[group] = frozenset(int(i) for i in ids)
        picked = rng.choice(ids, size=min(queries_per_group, len(ids)), replace=False)
        queries.extend((int(i), group) for i in np.sort(picked))

    return EvalSet(
        version=EVAL_SET_VERSION,
        seed=seed,
        dataset_rows=len(df),
        queries_per_group=queries_per_group,
        min_group_size=min_group_size,
        queries=tuple(queries),
        groups=groups,
    )


def save_eval_set(eval_set: EvalSet, path: Path | str = EVAL_SET_PATH) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(eval_set.to_json(), ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def load_eval_set(path: Path | str = EVAL_SET_PATH) -> EvalSet:
    return EvalSet.from_json(json.loads(Path(path).read_text(encoding="utf-8")))


# ------------------------------------------------------------------------------- métricas


def precision_at_k(ranked: Sequence[int], relevant: frozenset[int] | set[int], k: int) -> float:
    """Fracción de los K primeros que son relevantes."""
    return sum(1 for r in ranked[:k] if r in relevant) / k


def recall_at_k(ranked: Sequence[int], relevant: frozenset[int] | set[int], k: int) -> float:
    """Fracción de TODOS los relevantes que aparecen en los K primeros."""
    if not relevant:
        return float("nan")
    return sum(1 for r in ranked[:k] if r in relevant) / len(relevant)


def hit_rate_at_k(ranked: Sequence[int], relevant: frozenset[int] | set[int], k: int) -> float:
    """1 si hay al menos un relevante entre los K primeros, 0 si no."""
    return float(any(r in relevant for r in ranked[:k]))


def ndcg_at_k(ranked: Sequence[int], relevant: frozenset[int] | set[int], k: int) -> float:
    """NDCG@K con relevancia binaria: DCG = sum rel_i / log2(i + 1), normalizado por el ideal."""
    dcg = sum(1.0 / math.log2(i + 2) for i, r in enumerate(ranked[:k]) if r in relevant)
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    return dcg / idcg if idcg > 0 else float("nan")


METRIC_FUNCS: dict[str, Callable[[Sequence[int], frozenset[int], int], float]] = {
    "Precision": precision_at_k,
    "Recall": recall_at_k,
    "HitRate": hit_rate_at_k,
    "NDCG": ndcg_at_k,
}


def metric_columns(ks: Iterable[int] = DEFAULT_KS) -> list[str]:
    return [f"{name}@{k}" for k in ks for name in METRIC_FUNCS]


def top_k_ids(
    similarities: np.ndarray,
    recipe_ids: np.ndarray,
    k: int,
    exclude_pos: int | None = None,
) -> list[int]:
    """recipe_id de las K recetas más similares. Desempate estable por posición del CSV."""
    sims = np.asarray(similarities, dtype=np.float64).copy()
    if exclude_pos is not None:
        sims[exclude_pos] = -np.inf
    order = np.argsort(-sims, kind="stable")[:k]
    return [int(recipe_ids[i]) for i in order]


def evaluate(
    eval_set: EvalSet,
    similarity_fn: Callable[[int, int], np.ndarray],
    recipe_ids: np.ndarray,
    id_to_pos: dict[int, int],
    ks: Sequence[int] = DEFAULT_KS,
) -> pd.DataFrame:
    """Métricas por consulta para un modelo.

    `similarity_fn(recipe_id, position)` devuelve la similitud de la consulta contra TODAS las
    recetas (vector de largo N, mismo orden que el CSV). La propia consulta se excluye del ranking.
    Devuelve una fila por consulta con las columnas de `metric_columns(ks)`.
    """
    k_max = max(ks)
    rows = []
    for recipe_id, group in eval_set.queries:
        pos = id_to_pos[recipe_id]
        ranked = top_k_ids(similarity_fn(recipe_id, pos), recipe_ids, k_max, exclude_pos=pos)
        relevant = eval_set.relevant_for(recipe_id, group)
        row = {"recipe_id": recipe_id, "group": group, "n_relevant": len(relevant)}
        for k in ks:
            for name, func in METRIC_FUNCS.items():
                row[f"{name}@{k}"] = func(ranked, relevant, k)
        rows.append(row)
    return pd.DataFrame(rows)


def random_baseline(eval_set: EvalSet, n_recipes: int, ks: Sequence[int] = DEFAULT_KS) -> dict[str, float]:
    """Valor esperado de un ranking al azar (referencia para interpretar las métricas).

    Con |R| relevantes entre N-1 candidatos: Precision@K = |R|/(N-1); Recall@K = K/(N-1);
    HitRate@K = 1 - C(N-1-|R|, K) / C(N-1, K) (aprox. hipergeométrica exacta); NDCG@K esperado
    = Precision@K * (sum_{i<K} 1/log2(i+2)) / IDCG.
    """
    out: dict[str, list[float]] = {c: [] for c in metric_columns(ks)}
    pool = n_recipes - 1
    for recipe_id, group in eval_set.queries:
        r = len(eval_set.relevant_for(recipe_id, group))
        for k in ks:
            p = r / pool
            miss = 1.0
            for i in range(k):
                miss *= max(pool - r - i, 0) / (pool - i)
            disc = sum(1.0 / math.log2(i + 2) for i in range(k))
            idcg = sum(1.0 / math.log2(i + 2) for i in range(min(r, k)))
            out[f"Precision@{k}"].append(p)
            out[f"Recall@{k}"].append(k / pool)
            out[f"HitRate@{k}"].append(1.0 - miss)
            out[f"NDCG@{k}"].append(p * disc / idcg)
    return {c: float(np.mean(v)) for c, v in out.items()}


# ------------------------------------------------------------------------ comparación estadística


def paired_bootstrap(
    a: np.ndarray,
    b: np.ndarray,
    *,
    n_resamples: int = 10_000,
    seed: int = DEFAULT_SEED,
) -> tuple[float, float, float]:
    """Diferencia media (b - a) por consulta con IC 95 % por bootstrap pareado.

    Las dos series deben estar alineadas por consulta (mismas consultas, mismo orden).
    """
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if a.shape != b.shape:
        raise ValueError("Las series de métricas deben tener la misma longitud.")
    diff = b - a
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(diff), size=(n_resamples, len(diff)))
    means = diff[idx].mean(axis=1)
    low, high = np.percentile(means, [2.5, 97.5])
    return float(diff.mean()), float(low), float(high)
