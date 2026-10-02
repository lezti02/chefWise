"""Carga de los artefactos TF-IDF ya entrenados (no se reentrena nada aquí)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer

from .config import MATRIX_FILENAME, MODELS_DIR, VECTORIZER_FILENAME
from .exceptions import ArtifactMismatchError, ArtifactNotFoundError


@dataclass
class TfidfArtifacts:
    vectorizer: TfidfVectorizer
    matrix: sparse.csr_matrix  # filas = recetas (mismo orden que el CSV), L2-normalizadas

    def similarities(self, query_text: str) -> np.ndarray:
        """Similitud coseno de un texto contra TODAS las recetas, solo para esta consulta.

        Vectorizador y matriz están normalizados (norma L2), así que el coseno es
        simplemente el producto punto: no hace falta una matriz receta×receta.
        """
        query_vector = self.vectorizer.transform([query_text])
        return (self.matrix @ query_vector.T).toarray().ravel()


def load_artifacts(models_dir: Path | str = MODELS_DIR) -> TfidfArtifacts:
    models_dir = Path(models_dir)
    vectorizer_path = models_dir / VECTORIZER_FILENAME
    matrix_path = models_dir / MATRIX_FILENAME

    for path in (vectorizer_path, matrix_path):
        if not path.is_file():
            raise ArtifactNotFoundError(
                f"Falta el artefacto del modelo: {path}. "
                "Ejecuta el notebook 03_recomendador_content_based.ipynb (sección 12) "
                "o define CHEFWISE_MODELS_DIR."
            )

    vectorizer = joblib.load(vectorizer_path)
    matrix = joblib.load(matrix_path)

    if not isinstance(vectorizer, TfidfVectorizer):
        raise ArtifactMismatchError(f"{vectorizer_path.name} no contiene un TfidfVectorizer.")
    if not sparse.issparse(matrix):
        raise ArtifactMismatchError(f"{matrix_path.name} no contiene una matriz dispersa.")

    return TfidfArtifacts(vectorizer=vectorizer, matrix=sparse.csr_matrix(matrix))


def validate_alignment(
    artifacts: TfidfArtifacts,
    recipe_texts: list[str],
    n_samples: int = 5,
    tolerance: float = 1e-6,
) -> None:
    """Comprueba que la matriz guardada corresponde al CSV cargado.

    1. Mismo número de filas que recetas.
    2. Las filas están normalizadas (necesario para usar producto punto como coseno).
    3. Re-vectorizar el `recipe_text` de unas filas de muestra reproduce la fila guardada
       (detecta un CSV regenerado/reordenado o artefactos de otra versión).
    """
    matrix, vectorizer = artifacts.matrix, artifacts.vectorizer
    n_rows = len(recipe_texts)
    if matrix.shape[0] != n_rows:
        raise ArtifactMismatchError(
            f"La matriz TF-IDF tiene {matrix.shape[0]} filas pero el CSV tiene {n_rows} recetas. "
            "Regenera los artefactos con el CSV actual."
        )
    if matrix.shape[1] != len(vectorizer.vocabulary_):
        raise ArtifactMismatchError(
            "La matriz y el vectorizador tienen vocabularios de distinto tamaño "
            f"({matrix.shape[1]} vs {len(vectorizer.vocabulary_)})."
        )

    sample_positions = sorted({int(p) for p in np.linspace(0, n_rows - 1, num=min(n_samples, n_rows))})
    for pos in sample_positions:
        stored = matrix[pos]
        norm = float(np.sqrt(stored.multiply(stored).sum()))
        if norm and abs(norm - 1.0) > 1e-3:
            raise ArtifactMismatchError(
                f"La fila {pos} de la matriz TF-IDF no está normalizada (norma={norm:.4f})."
            )
        recomputed = vectorizer.transform([recipe_texts[pos]])
        if abs(recomputed - stored).max() > tolerance:
            raise ArtifactMismatchError(
                f"La fila {pos} de la matriz TF-IDF no coincide con el `recipe_text` del CSV. "
                "Los artefactos de models/ no corresponden a este dataset."
            )
