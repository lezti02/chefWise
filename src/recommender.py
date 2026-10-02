"""Servicio de recomendación Content-Based (TF-IDF + similitud coseno).

Flujo:

    preferencias estructuradas
        -> filtros duros (dificultad, tiempo, país, exclusiones)
        -> filtro por antojos (categorías / etiquetas / texto del dataset)
        -> candidatos
        -> TF-IDF + coseno contra la consulta (solo para esta petición)
        -> ranking (similitud + calidad)
        -> Top-N

Se instancia UNA vez al arrancar el backend: el CSV y los artefactos de
`models/` se cargan en memoria y se reutilizan en cada petición.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from .config import DATASET_PATH, DEFAULT_TOP_N, MODELS_DIR
from .data_loader import RecipeStore, load_recipes
from .filters import build_mood_masks, combine_moods, effective_max_minutes, structural_mask
from .models import TfidfArtifacts, load_artifacts, validate_alignment
from .preferences import MOOD_RULES, UserPreferences
from .ranking import rank_candidates

logger = logging.getLogger(__name__)


@dataclass
class ScoredRecipe:
    summary: dict[str, Any]
    similarity: float | None
    score: float


@dataclass
class RecommendationResult:
    items: list[ScoredRecipe]
    candidates: int
    query_text: str | None
    max_minutes: int | None
    relaxed: list[str] = field(default_factory=list)


class Recommender:
    def __init__(self, store: RecipeStore, artifacts: TfidfArtifacts, *, validate: bool = True) -> None:
        if validate:
            validate_alignment(artifacts, store.df["recipe_text"].fillna("").astype(str).tolist())
        self.store = store
        self.artifacts = artifacts
        self._mood_masks = build_mood_masks(store)
        for key, mask in self._mood_masks.items():
            if mask.any():
                logger.info("Antojo %-13s -> %6d recetas coinciden", key, int(mask.sum()))

    @classmethod
    def from_disk(
        cls,
        dataset_path: Path | str = DATASET_PATH,
        models_dir: Path | str = MODELS_DIR,
    ) -> "Recommender":
        store = load_recipes(dataset_path)
        artifacts = load_artifacts(models_dir)
        logger.info("Recomendador listo: %d recetas, %d términos TF-IDF", len(store), artifacts.matrix.shape[1])
        return cls(store, artifacts)

    # ------------------------------------------------------------------ recetas

    def get_recipe(self, recipe_id: int) -> dict[str, Any]:
        """Receta completa. Lanza `RecipeNotFoundError` si no existe."""
        return self.store.detail(self.store.position_of(recipe_id))

    # ------------------------------------------------------------ recomendación

    def recommend(self, prefs: UserPreferences) -> RecommendationResult:
        """Top-N para "Sorpréndeme" a partir de las preferencias estructuradas."""
        max_minutes = effective_max_minutes(prefs.max_time, prefs.moods)
        base = structural_mask(
            self.store,
            difficulty=prefs.difficulty,
            max_minutes=max_minutes,
            countries=prefs.countries,
            exclude_positions=self.store.positions_of(list(prefs.exclude_ids)),
        )

        candidates, relaxed = self._apply_moods(base, prefs)

        query_text = " ".join(MOOD_RULES[m].query_terms for m in prefs.moods) or None
        similarity = self.artifacts.similarities(query_text) if query_text else None

        return self._build_result(
            candidates,
            similarity,
            prefs.top_n,
            query_text=query_text,
            max_minutes=max_minutes,
            relaxed=relaxed,
        )

    def recommend_by_ingredients(
        self,
        ingredients: list[str],
        *,
        exclude_ids: tuple[int, ...] = (),
        top_n: int = DEFAULT_TOP_N,
    ) -> RecommendationResult:
        """"Con lo que tengo": similitud TF-IDF entre los ingredientes escritos y cada receta."""
        query_text = " ".join(i.strip() for i in ingredients if i and i.strip())
        if not query_text:
            raise ValueError("Se requiere al menos un ingrediente.")

        similarity = self.artifacts.similarities(query_text)
        mask = similarity > 0  # sin ningún término en común no es una recomendación
        exclude_positions = self.store.positions_of(list(exclude_ids))
        if exclude_positions:
            mask[exclude_positions] = False

        return self._build_result(
            mask, similarity, top_n, query_text=query_text, max_minutes=None, relaxed=[]
        )

    # ----------------------------------------------------------------- internos

    def _apply_moods(self, base: np.ndarray, prefs: UserPreferences) -> tuple[np.ndarray, list[str]]:
        """Aplica los antojos con relajación progresiva si quedan muy pocos candidatos.

        Los filtros estructurales (dificultad, tiempo, país) nunca se relajan.
        """
        relaxed: list[str] = []
        strict = combine_moods(self._mood_masks, prefs.moods, require_all=True)
        if strict is None:
            return base, relaxed

        candidates = base & strict
        if candidates.sum() >= prefs.top_n:
            return candidates, relaxed

        if len(prefs.moods) > 1:
            any_mood = combine_moods(self._mood_masks, prefs.moods, require_all=False)
            candidates = base & any_mood
            relaxed.append("antojos: se aceptó cualquiera de los antojos elegidos (no todos a la vez)")
            if candidates.sum() >= prefs.top_n:
                return candidates, relaxed

        relaxed.append("antojos: pocas recetas coinciden; se ordenó por similitud sin exigir la etiqueta")
        return base, relaxed

    def _build_result(
        self,
        candidate_mask: np.ndarray,
        similarity: np.ndarray | None,
        top_n: int,
        *,
        query_text: str | None,
        max_minutes: int | None,
        relaxed: list[str],
    ) -> RecommendationResult:
        positions, scores = rank_candidates(candidate_mask, self.store.quality, top_n, similarity)
        items = [
            ScoredRecipe(
                summary=self.store.summary(int(pos)),
                similarity=round(float(similarity[pos]), 4) if similarity is not None else None,
                score=round(float(score), 4),
            )
            for pos, score in zip(positions, scores)
        ]
        return RecommendationResult(
            items=items,
            candidates=int(candidate_mask.sum()),
            query_text=query_text,
            max_minutes=max_minutes,
            relaxed=relaxed,
        )
