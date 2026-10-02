"""Acceso al dataset procesado (el CSV es la fuente de verdad de las recetas).

El CSV se lee UNA sola vez al arrancar y se deja en memoria como `RecipeStore`.
El orden de filas del DataFrame es el mismo que el de la matriz TF-IDF guardada
en `models/`, por eso la posición (0..n-1) es el vínculo entre ambos.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import DATASET_PATH, RATING_PRIOR_VOTES
from .exceptions import DatasetNotFoundError, DatasetSchemaError, RecipeNotFoundError
from .text_utils import split_ingredients, split_steps, split_tags

REQUIRED_COLUMNS = [
    "recipe_id",
    "name",
    "ingredients",
    "instructions",
    "country",
    "app_category",
    "app_difficulty",
    "total_time_min",
    "rating",
    "recipe_text",
]

OPTIONAL_COLUMNS = [
    "source",
    "url",
    "meal_type",
    "category_tags",
    "diet_tags",
    "difficulty",
    "prep_time_min",
    "cook_time_min",
    "servings",
    "rating_votes",
    "num_comments",
    "context",
]


@dataclass
class RecipeStore:
    """Dataset en memoria + vectores numpy precalculados para filtrar rápido."""

    df: pd.DataFrame
    id_to_pos: dict[int, int]
    total_time: np.ndarray  # float, NaN si se desconoce
    quality: np.ndarray  # 0-1, rating bayesiano (neutro si no hay rating)

    def __len__(self) -> int:
        return len(self.df)

    def position_of(self, recipe_id: int) -> int:
        try:
            return self.id_to_pos[int(recipe_id)]
        except (KeyError, ValueError, TypeError):
            raise RecipeNotFoundError(f"No existe la receta con recipe_id={recipe_id}") from None

    def positions_of(self, recipe_ids: list[int]) -> list[int]:
        """Posiciones de los ids que existan (los desconocidos se ignoran)."""
        return [self.id_to_pos[i] for i in recipe_ids if i in self.id_to_pos]

    def summary(self, pos: int) -> dict[str, Any]:
        """Campos para tarjetas/listas."""
        row = self.df.iloc[pos]
        return {
            "recipe_id": int(row["recipe_id"]),
            "name": str(row["name"]),
            "ingredients": split_ingredients(row["ingredients"]),
            "difficulty": _clean_str(row.get("app_difficulty")),
            "total_time_min": _clean_int(row.get("total_time_min")),
            "servings": _clean_int(row.get("servings")),
            "country": _clean_str(row.get("country")),
            "category": _clean_str(row.get("app_category")),
            "meal_type": _clean_str(row.get("meal_type")),
            "rating": _clean_float(row.get("rating")),
            "rating_votes": _clean_int(row.get("rating_votes")),
            "source": _clean_str(row.get("source")),
            "source_url": _clean_str(row.get("url")),
        }

    def detail(self, pos: int) -> dict[str, Any]:
        """Receta completa: resumen + pasos y metadatos extra del CSV."""
        row = self.df.iloc[pos]
        return {
            **self.summary(pos),
            "instructions": split_steps(row["instructions"]),
            "difficulty_source": _clean_str(row.get("difficulty")),
            "prep_time_min": _clean_int(row.get("prep_time_min")),
            "cook_time_min": _clean_int(row.get("cook_time_min")),
            "category_tags": split_tags(row.get("category_tags")),
            "diet_tags": split_tags(row.get("diet_tags")),
            "description": _clean_str(row.get("context")),
            "num_comments": _clean_int(row.get("num_comments")),
        }


def load_recipes(path: Path | str = DATASET_PATH) -> RecipeStore:
    """Lee el CSV procesado y prepara el `RecipeStore`. Falla con mensajes claros."""
    path = Path(path)
    if not path.is_file():
        raise DatasetNotFoundError(
            f"No se encontró el dataset procesado en: {path}. "
            "Define CHEFWISE_DATASET_PATH o coloca el CSV en data/processed/."
        )

    header = pd.read_csv(path, nrows=0).columns
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise DatasetSchemaError(f"Al CSV {path.name} le faltan columnas obligatorias: {missing}")

    usecols = REQUIRED_COLUMNS + [c for c in OPTIONAL_COLUMNS if c in header]
    df = pd.read_csv(path, usecols=usecols)

    if df["recipe_id"].isna().any() or not df["recipe_id"].is_unique:
        raise DatasetSchemaError("`recipe_id` debe existir y ser único en todas las filas.")
    df["recipe_id"] = df["recipe_id"].astype("int64")

    id_to_pos = {int(rid): pos for pos, rid in enumerate(df["recipe_id"].to_numpy())}
    return RecipeStore(
        df=df,
        id_to_pos=id_to_pos,
        total_time=df["total_time_min"].to_numpy(dtype="float64", na_value=np.nan),
        quality=_bayesian_quality(df),
    )


def _bayesian_quality(df: pd.DataFrame) -> np.ndarray:
    """Rating suavizado hacia la media global y escalado a 0-1 (rating 1..5)."""
    rating = df["rating"].to_numpy(dtype="float64", na_value=np.nan)
    if "rating_votes" in df.columns:
        votes = df["rating_votes"].to_numpy(dtype="float64", na_value=np.nan)
    else:
        votes = np.where(np.isnan(rating), np.nan, 1.0)
    # Rating sin conteo de votos: se trata como un solo voto (es lo único que sabemos).
    votes = np.where(np.isnan(rating), 0.0, np.where(np.isnan(votes), 1.0, votes))
    rating = np.where(np.isnan(rating), 0.0, rating)

    known = votes > 0
    global_mean = float(rating[known].mean()) if known.any() else 3.0
    bayes = (votes * rating + RATING_PRIOR_VOTES * global_mean) / (votes + RATING_PRIOR_VOTES)
    return np.clip((bayes - 1.0) / 4.0, 0.0, 1.0)


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _clean_str(value: Any) -> str | None:
    if _is_missing(value):
        return None
    text = str(value).strip()
    return text or None


def _clean_int(value: Any) -> int | None:
    if _is_missing(value):
        return None
    number = float(value)
    return None if math.isnan(number) else int(round(number))


def _clean_float(value: Any) -> float | None:
    if _is_missing(value):
        return None
    number = float(value)
    return None if math.isnan(number) else round(number, 2)
