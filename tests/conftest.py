"""Fixtures compartidas. El recomendador real (CSV + artefactos) se carga una vez por sesión."""

from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from src.config import DATASET_PATH


@pytest.fixture(scope="session")
def client():
    # `with` ejecuta el lifespan: carga el CSV y los artefactos reales.
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def csv_df() -> pd.DataFrame:
    """El CSV tal cual, como referencia independiente del código bajo prueba."""
    return pd.read_csv(DATASET_PATH, usecols=["recipe_id", "name", "ingredients", "instructions", "url", "country"])
