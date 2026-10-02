"""Ranking final de los candidatos: similitud TF-IDF + un pequeño peso de calidad."""

from __future__ import annotations

import numpy as np

from .config import QUALITY_WEIGHT


def rank_candidates(
    candidate_mask: np.ndarray,
    quality: np.ndarray,
    top_n: int,
    similarity: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Devuelve (posiciones, scores) de los top_n candidatos, de mayor a menor score.

    score = similitud coseno (0 si no hubo consulta de texto) + QUALITY_WEIGHT * calidad.
    El desempate final es la posición en el CSV, para que el resultado sea determinista.
    """
    positions = np.flatnonzero(candidate_mask)
    if positions.size == 0:
        return positions, np.empty(0)

    base = similarity[positions] if similarity is not None else 0.0
    scores = base + QUALITY_WEIGHT * quality[positions]

    order = np.lexsort((positions, -scores))[:top_n]
    return positions[order], scores[order]
