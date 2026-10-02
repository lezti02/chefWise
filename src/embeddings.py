"""Modelo 2: embeddings densos + similitud coseno (contraparte de `models.py`, que es TF-IDF).

    recipe_text -> modelo de embeddings -> vector denso -> matriz (N x D, normalizada L2)

Igual que en el Modelo 1, las filas están normalizadas, así que el coseno es el producto punto y
nunca se construye una matriz receta x receta: cada consulta calcula N similitudes.

El nombre del modelo vive en UN solo lugar (`EMBEDDING_MODEL_NAME`) y se puede sobrescribir con la
variable de entorno `CHEFWISE_EMBEDDING_MODEL`. Los artefactos guardan con qué modelo se generaron
y se rechazan si no corresponden al modelo configurado o al CSV (mismo criterio que el Modelo 1).

`sentence-transformers` se importa solo cuando hace falta, para que el backend de producción (que
hoy solo usa TF-IDF) no dependa de torch.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

import numpy as np

from .config import MODELS_DIR
from .exceptions import ArtifactMismatchError, ArtifactNotFoundError

if TYPE_CHECKING:  # pragma: no cover
    from sentence_transformers import SentenceTransformer

# Modelo elegido y por qué (detalle y alternativas en notebooks/04_recomendador_embeddings.ipynb):
#  - multilingüe con español en su preentrenamiento y afinado para recuperación semántica;
#  - contexto de 512 tokens: un `recipe_text` mide ~125 tokens de media y sólo ~0.05 % supera 512
#    (con 128 tokens se truncaría una parte grande de las recetas, justo donde van las etiquetas);
#  - 384 dimensiones: matriz de ~44 MB y ejecutable en CPU/MPS sin GPU.
EMBEDDING_MODEL_NAME = os.getenv("CHEFWISE_EMBEDDING_MODEL", "intfloat/multilingual-e5-small")

EMBEDDING_BATCH_SIZE = 64
EMBEDDING_MODEL_DIRNAME = "embedding_model"
EMBEDDINGS_FILENAME = "recipe_embeddings.npy"
EMBEDDINGS_META_FILENAME = "embedding_metadata.json"


def default_prefixes(model_name: str) -> tuple[str, str]:
    """(prefijo de consulta, prefijo de documento) que exige la familia del modelo.

    La familia E5 se entrenó con "query: " / "passage: " y rinde peor sin ellos. Otros modelos
    (p. ej. paraphrase-multilingual-*) no usan prefijos.
    """
    if "e5" in model_name.lower():
        return "query: ", "passage: "
    return "", ""


def text_fingerprint(texts: Sequence[str]) -> str:
    """Huella del corpus: detecta que los embeddings guardados corresponden a otro CSV/orden."""
    digest = hashlib.sha256()
    for text in texts:
        digest.update(text.encode("utf-8"))
        digest.update(b"\x1f")
    return digest.hexdigest()


def library_versions() -> dict[str, str]:
    import sentence_transformers
    import torch
    import transformers

    return {
        "sentence_transformers": sentence_transformers.__version__,
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "numpy": np.__version__,
    }


def embedding_dimension(model: "SentenceTransformer") -> int:
    getter = getattr(model, "get_embedding_dimension", None) or model.get_sentence_embedding_dimension
    return int(getter())


def load_embedding_model(model_name_or_path: str | Path = EMBEDDING_MODEL_NAME, device: str | None = None) -> "SentenceTransformer":
    """Carga el modelo (descarga de Hugging Face la primera vez si no es una carpeta local)."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(str(model_name_or_path), device=device)


def encode_texts(
    model: "SentenceTransformer",
    texts: Sequence[str],
    *,
    prefix: str = "",
    batch_size: int = EMBEDDING_BATCH_SIZE,
    show_progress_bar: bool = False,
) -> np.ndarray:
    """Embeddings float32 normalizados (norma L2 = 1) de una lista de textos, por batches."""
    prefixed = [prefix + t for t in texts] if prefix else list(texts)
    vectors = model.encode(
        prefixed,
        batch_size=batch_size,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=show_progress_bar,
    )
    return np.ascontiguousarray(vectors, dtype=np.float32)


@dataclass
class EmbeddingArtifacts:
    """Embeddings de las recetas (fila i = receta i del CSV) y, opcionalmente, el modelo cargado."""

    matrix: np.ndarray  # (N, D) float32, filas con norma 1
    metadata: dict[str, Any]
    model: "SentenceTransformer | None" = field(default=None, repr=False)

    @property
    def query_prefix(self) -> str:
        return self.metadata.get("query_prefix", "")

    def similarities_to_row(self, position: int) -> np.ndarray:
        """Coseno de una receta del catálogo contra TODAS (sin tener que re-codificarla)."""
        return self.matrix @ self.matrix[position]

    def similarities(self, query_text: str) -> np.ndarray:
        """Coseno de un texto libre contra TODAS las recetas, con el MISMO modelo que las codificó."""
        if self.model is None:
            raise RuntimeError("Este EmbeddingArtifacts se cargó sin modelo; no puede codificar texto.")
        query_vector = encode_texts(self.model, [query_text], prefix=self.query_prefix)[0]
        return self.matrix @ query_vector


def build_metadata(
    *,
    model: "SentenceTransformer",
    model_name: str,
    matrix: np.ndarray,
    texts: Sequence[str],
    query_prefix: str,
    passage_prefix: str,
    batch_size: int,
    build_seconds: float,
) -> dict[str, Any]:
    return {
        "model_name": model_name,
        "embedding_dim": int(matrix.shape[1]),
        "n_recipes": int(matrix.shape[0]),
        "dtype": str(matrix.dtype),
        "normalized_l2": True,
        "max_seq_length": int(model.max_seq_length),
        "query_prefix": query_prefix,
        "passage_prefix": passage_prefix,
        "text_column": "recipe_text",
        "texts_sha256": text_fingerprint(texts),
        "batch_size": batch_size,
        "device": str(model.device),
        "build_seconds": round(build_seconds, 2),
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "libraries": library_versions(),
    }


def build_embeddings(
    texts: Sequence[str],
    *,
    model_name: str = EMBEDDING_MODEL_NAME,
    batch_size: int = EMBEDDING_BATCH_SIZE,
    model: "SentenceTransformer | None" = None,
    show_progress_bar: bool = True,
) -> EmbeddingArtifacts:
    """Codifica todo el corpus UNA vez y devuelve la matriz con sus metadatos (incluye el tiempo)."""
    model = model or load_embedding_model(model_name)
    query_prefix, passage_prefix = default_prefixes(model_name)

    started = time.perf_counter()
    matrix = encode_texts(
        model, texts, prefix=passage_prefix, batch_size=batch_size, show_progress_bar=show_progress_bar
    )
    elapsed = time.perf_counter() - started

    metadata = build_metadata(
        model=model,
        model_name=model_name,
        matrix=matrix,
        texts=texts,
        query_prefix=query_prefix,
        passage_prefix=passage_prefix,
        batch_size=batch_size,
        build_seconds=elapsed,
    )
    return EmbeddingArtifacts(matrix=matrix, metadata=metadata, model=model)


def save_embedding_artifacts(
    artifacts: EmbeddingArtifacts,
    models_dir: Path | str = MODELS_DIR,
    *,
    save_model: bool = True,
) -> dict[str, Path]:
    """Guarda matriz, metadatos y (opcional) el modelo en `models/`. No toca los archivos TF-IDF."""
    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "matrix": models_dir / EMBEDDINGS_FILENAME,
        "metadata": models_dir / EMBEDDINGS_META_FILENAME,
    }
    np.save(paths["matrix"], artifacts.matrix)
    paths["metadata"].write_text(json.dumps(artifacts.metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    if save_model and artifacts.model is not None:
        paths["model"] = models_dir / EMBEDDING_MODEL_DIRNAME
        artifacts.model.save(str(paths["model"]))
    return paths


def load_embedding_artifacts(
    models_dir: Path | str = MODELS_DIR,
    *,
    texts: Sequence[str] | None = None,
    expected_model_name: str = EMBEDDING_MODEL_NAME,
    load_model: bool = True,
    device: str | None = None,
) -> EmbeddingArtifacts:
    """Carga los embeddings guardados y comprueba que corresponden al modelo y al CSV actuales.

    El modelo se lee de `models/embedding_model/` si existe (sin red); si no, se descarga por nombre.
    """
    models_dir = Path(models_dir)
    matrix_path = models_dir / EMBEDDINGS_FILENAME
    meta_path = models_dir / EMBEDDINGS_META_FILENAME
    for path in (matrix_path, meta_path):
        if not path.is_file():
            raise ArtifactNotFoundError(
                f"Falta el artefacto del Modelo 2: {path}. Ejecuta notebooks/04_recomendador_embeddings.ipynb."
            )

    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    matrix = np.load(matrix_path)

    if metadata["model_name"] != expected_model_name:
        raise ArtifactMismatchError(
            f"Los embeddings se generaron con '{metadata['model_name']}' pero el modelo configurado es "
            f"'{expected_model_name}'. Regenera los embeddings o ajusta CHEFWISE_EMBEDDING_MODEL."
        )
    if matrix.ndim != 2 or matrix.shape != (metadata["n_recipes"], metadata["embedding_dim"]):
        raise ArtifactMismatchError(
            f"{matrix_path.name} tiene forma {matrix.shape}, distinta a la de los metadatos "
            f"({metadata['n_recipes']}, {metadata['embedding_dim']})."
        )
    if texts is not None:
        if len(texts) != matrix.shape[0]:
            raise ArtifactMismatchError(
                f"Hay {matrix.shape[0]} embeddings pero el CSV tiene {len(texts)} recetas."
            )
        if text_fingerprint(texts) != metadata["texts_sha256"]:
            raise ArtifactMismatchError(
                "Los embeddings guardados no corresponden al `recipe_text` del CSV actual "
                "(cambió el contenido o el orden). Regenéralos."
            )

    model = None
    if load_model:
        local = models_dir / EMBEDDING_MODEL_DIRNAME
        model = load_embedding_model(local if local.is_dir() else expected_model_name, device=device)
    return EmbeddingArtifacts(matrix=matrix, metadata=metadata, model=model)
