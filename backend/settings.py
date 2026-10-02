"""Configuración del backend (variables de entorno)."""

from __future__ import annotations

import os

# `ng serve` usa el puerto 4200 por defecto. Se puede cambiar con una lista
# separada por comas, p. ej.: CHEFWISE_CORS_ORIGINS="http://localhost:4200,https://chefwise.example"
_DEFAULT_ORIGINS = "http://localhost:4200,http://127.0.0.1:4200"


def cors_origins() -> list[str]:
    raw = os.getenv("CHEFWISE_CORS_ORIGINS", _DEFAULT_ORIGINS)
    return [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]
