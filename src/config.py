"""Rutas y parámetros del recomendador.

Todo se puede sobreescribir con variables de entorno para no depender del
directorio desde donde se arranca el servicio.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATASET_PATH = Path(
    os.getenv(
        "CHEFWISE_DATASET_PATH",
        PROJECT_ROOT / "data" / "processed" / "recetas_unificadas_limpias.csv",
    )
)
MODELS_DIR = Path(os.getenv("CHEFWISE_MODELS_DIR", PROJECT_ROOT / "models"))

VECTORIZER_FILENAME = "tfidf_vectorizer.joblib"
MATRIX_FILENAME = "recipe_tfidf_matrix.joblib"

# "Algo rápido" no es una etiqueta del dataset: se traduce a un tope de
# tiempo. 30 min es la mediana de `total_time_min` de las recetas `facil`
# del propio CSV (y ~48% de las recetas con tiempo conocido caben en 30 min).
QUICK_MAX_MINUTES = 30

# Peso de la calidad (rating bayesiano normalizado a 0-1) dentro del score
# final. Es pequeño a propósito: la similitud TF-IDF manda; la calidad solo
# desempata y ordena cuando no hay consulta de texto.
QUALITY_WEIGHT = 0.05

# Suavizado bayesiano del rating: una receta con 1 voto de 5.0 no debe
# superar a una con 200 votos de 4.8.
RATING_PRIOR_VOTES = 5.0

DEFAULT_TOP_N = 12
