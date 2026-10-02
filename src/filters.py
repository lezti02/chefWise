"""Filtros duros sobre el dataset: devuelven máscaras booleanas alineadas con el CSV."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .data_loader import RecipeStore
from .preferences import MOOD_RULES, MoodRule
from .text_utils import normalize_text


def _normalized_series(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).map(normalize_text)


def _tag_sets(store: RecipeStore) -> list[frozenset[str]]:
    """Etiquetas normalizadas por receta (category_tags + diet_tags + meal_type)."""
    df = store.df
    columns = [c for c in ("category_tags", "diet_tags", "meal_type") if c in df.columns]
    merged = df[columns].fillna("").agg(" | ".join, axis=1) if columns else pd.Series([""] * len(df))
    result: list[frozenset[str]] = []
    for text in merged.map(normalize_text):
        result.append(frozenset(t.strip().rstrip(".") for t in text.split("|") if t.strip()))
    return result


def build_mood_masks(store: RecipeStore) -> dict[str, np.ndarray]:
    """Precalcula UNA vez (al arrancar) qué recetas cumplen cada antojo."""
    df = store.df
    n = len(df)
    names = _normalized_series(df["name"])
    ingredients = _normalized_series(df["ingredients"])
    name_and_ingredients = names + " " + ingredients
    tag_sets = _tag_sets(store)
    categories = df["app_category"].fillna("").to_numpy()

    masks: dict[str, np.ndarray] = {}
    for key, rule in MOOD_RULES.items():
        mask = np.zeros(n, dtype=bool)
        if rule.categories:
            mask |= np.isin(categories, list(rule.categories))
        if rule.tags:
            mask |= np.fromiter((bool(tags & rule.tags) for tags in tag_sets), dtype=bool, count=n)
        if rule.name_regex:
            mask |= names.str.contains(rule.name_regex, regex=True).to_numpy(dtype=bool)
        if rule.text_regex:
            mask |= name_and_ingredients.str.contains(rule.text_regex, regex=True).to_numpy(dtype=bool)
        masks[key] = mask
    return masks


def has_structural_signal(rule: MoodRule) -> bool:
    """¿El antojo restringe candidatos (True) o solo aporta texto/tiempo (False)?"""
    return bool(rule.categories or rule.tags or rule.name_regex or rule.text_regex)


def effective_max_minutes(max_time: int | None, moods: tuple[str, ...]) -> int | None:
    """Tope de tiempo final: el menor entre el slider y el de los antojos (p. ej. "rápido")."""
    caps = [max_time] if max_time is not None else []
    caps += [MOOD_RULES[m].max_minutes for m in moods if MOOD_RULES[m].max_minutes is not None]
    return min(caps) if caps else None


def structural_mask(
    store: RecipeStore,
    *,
    difficulty: str | None,
    max_minutes: int | None,
    countries: tuple[str, ...],
    exclude_positions: list[int],
) -> np.ndarray:
    """Filtros que SIEMPRE se respetan: dificultad, tiempo, país y exclusiones.

    Si se pide un tiempo o una dificultad, las recetas sin ese dato en el CSV
    se descartan: no se puede afirmar que cumplan.
    """
    df = store.df
    mask = np.ones(len(df), dtype=bool)

    if difficulty is not None:
        mask &= (df["app_difficulty"] == difficulty).to_numpy(dtype=bool)
    if max_minutes is not None:
        with np.errstate(invalid="ignore"):
            mask &= store.total_time <= max_minutes  # NaN <= x es False
    if countries:
        mask &= df["country"].isin(countries).to_numpy(dtype=bool)
    if exclude_positions:
        mask[exclude_positions] = False
    return mask


def combine_moods(masks: dict[str, np.ndarray], moods: tuple[str, ...], *, require_all: bool) -> np.ndarray | None:
    """Une las máscaras de los antojos que restringen candidatos (None si no hay ninguna)."""
    selected = [masks[m] for m in moods if has_structural_signal(MOOD_RULES[m])]
    if not selected:
        return None
    stacked = np.vstack(selected)
    return stacked.all(axis=0) if require_all else stacked.any(axis=0)
