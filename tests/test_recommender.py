"""Pruebas de la lógica de `src/`: parsing, arranque, rendimiento y ausencia de mocks."""

from __future__ import annotations

import re
from pathlib import Path

import joblib
import pytest
from scipy import sparse

from src.config import MODELS_DIR, PROJECT_ROOT
from src.data_loader import load_recipes
from src.exceptions import ArtifactMismatchError, ArtifactNotFoundError, DatasetNotFoundError, DatasetSchemaError
from src.models import TfidfArtifacts, load_artifacts, validate_alignment
from src.recommender import Recommender
from src.text_utils import split_ingredients, split_steps


# ----------------------------------------------------------------------- parsing
def test_split_steps_strips_consecutive_numbering_only():
    assert split_steps("1 Corta | 2 Fríe | 3 Sirve") == ["Corta", "Fríe", "Sirve"]
    # Sin numeración consecutiva no se toca el texto ("2 tazas" es contenido, no número de paso).
    assert split_steps("Mezcla | 2 tazas de harina van aquí") == ["Mezcla", "2 tazas de harina van aquí"]
    # Número de paso suelto al final (artefacto del scraping): se descarta, no se muestra "5".
    assert split_steps("1 Corta | 2 Fríe | 3") == ["Corta", "Fríe"]
    assert split_steps(None) == []
    assert split_steps("") == []


def test_split_ingredients_pipe_and_comma_sources():
    assert split_ingredients("2 huevos | 1 taza de leche") == ["2 huevos", "1 taza de leche"]
    assert split_ingredients("1 kg Patata, 40 ml Aceite , Sal") == ["1 kg Patata", "40 ml Aceite", "Sal"]
    assert split_ingredients("1,5 kg de harina,2 huevos") == ["1,5 kg de harina", "2 huevos"]
    assert split_ingredients(float("nan")) == []


# ------------------------------------------------------------------------ arranque
def test_missing_dataset_fails_with_clear_error(tmp_path):
    with pytest.raises(DatasetNotFoundError, match="CHEFWISE_DATASET_PATH"):
        load_recipes(tmp_path / "no_existe.csv")


def test_dataset_without_required_columns_fails(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("recipe_id,name\n1,Algo\n", encoding="utf-8")
    with pytest.raises(DatasetSchemaError, match="faltan columnas"):
        load_recipes(bad)


def test_missing_artifacts_fail_with_clear_error(tmp_path):
    with pytest.raises(ArtifactNotFoundError, match="tfidf_vectorizer.joblib"):
        load_artifacts(tmp_path)


def test_startup_fails_if_models_dir_is_missing(tmp_path):
    with pytest.raises(ArtifactNotFoundError):
        Recommender.from_disk(models_dir=tmp_path)


def test_misaligned_artifacts_are_detected():
    store = load_recipes()
    artifacts = load_artifacts()
    # Matriz con filas reordenadas = artefactos que ya no corresponden al CSV.
    shuffled = TfidfArtifacts(artifacts.vectorizer, sparse.csr_matrix(artifacts.matrix[::-1]))
    with pytest.raises(ArtifactMismatchError, match="no coincide"):
        validate_alignment(shuffled, store.df["recipe_text"].tolist())

    truncated = TfidfArtifacts(artifacts.vectorizer, artifacts.matrix[:-10])
    with pytest.raises(ArtifactMismatchError, match="filas"):
        validate_alignment(truncated, store.df["recipe_text"].tolist())


def test_real_artifacts_are_aligned_with_the_csv():
    store = load_recipes()
    artifacts = load_artifacts()
    validate_alignment(artifacts, store.df["recipe_text"].tolist(), n_samples=25)
    assert artifacts.matrix.shape[0] == len(store)


# ------------------------------------------------------------------- rendimiento
def test_requests_do_not_reload_dataset_or_artifacts(client, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Se intentó recargar el CSV o los artefactos durante una petición.")

    monkeypatch.setattr("src.data_loader.pd.read_csv", forbidden)
    monkeypatch.setattr(joblib, "load", forbidden)
    first = client.post("/recommendations", json={"antojos": ["picante"]})
    second = client.post("/recommendations", json={"antojos": ["dulce"]})
    detail = client.get("/recipes/1")
    assert first.status_code == second.status_code == detail.status_code == 200


def test_no_full_similarity_matrix_is_built(client):
    recommender = client.app.state.recommender
    sims = recommender.artifacts.similarities("pollo")
    assert sims.shape == (len(recommender.store),)  # un vector por consulta, no n×n


# ----------------------------------------------------------------- sin mocks
def test_models_dir_points_to_the_existing_artifacts():
    assert MODELS_DIR == PROJECT_ROOT / "models"
    assert (MODELS_DIR / "tfidf_vectorizer.joblib").is_file()
    assert (MODELS_DIR / "recipe_tfidf_matrix.joblib").is_file()


MOCK_PATTERN = re.compile(r"MOCK_RECIPES|mockRecipes|fakeRecipes|sampleRecipes|dummyData", re.IGNORECASE)


def _sources(root: Path, suffixes: tuple[str, ...]):
    return [
        p
        for p in root.rglob("*")
        if p.is_file() and p.suffix in suffixes and "node_modules" not in p.parts and "__pycache__" not in p.parts
    ]


def test_backend_and_src_do_not_use_mocks():
    for folder in ("backend", "src"):
        for path in _sources(PROJECT_ROOT / folder, (".py",)):
            assert not MOCK_PATTERN.search(path.read_text(encoding="utf-8")), f"mock en {path}"


def test_frontend_production_code_does_not_use_recipe_mocks():
    frontend_src = PROJECT_ROOT / "frontend" / "src"
    for path in _sources(frontend_src, (".ts", ".html")):
        if path.name.endswith(".spec.ts"):
            continue
        assert not MOCK_PATTERN.search(path.read_text(encoding="utf-8")), f"mock de recetas en {path}"
