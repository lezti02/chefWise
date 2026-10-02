"""Punto de entrada de la API.

    uvicorn backend.main:app --reload

(se ejecuta desde la raíz del proyecto, para que `src` y `backend` sean importables).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.exceptions import RecipeNotFoundError
from src.recommender import Recommender

from .routes import router
from .settings import cors_origins

logger = logging.getLogger("chefwise.api")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Carga CSV + artefactos TF-IDF una sola vez.

    Si falta un archivo obligatorio o los artefactos no corresponden al CSV, la
    excepción (con un mensaje claro) detiene el arranque del servicio.
    """
    try:
        app.state.recommender = Recommender.from_disk()
    except Exception:
        logger.exception("No se pudo iniciar el recomendador; el backend no arrancará.")
        raise
    yield
    app.state.recommender = None


def create_app() -> FastAPI:
    app = FastAPI(title="ChefWise API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins(),
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(RecipeNotFoundError)
    async def recipe_not_found(_: Request, exc: RecipeNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # El detalle va al log del servidor; al cliente solo un mensaje seguro.
        logger.error("Error no controlado en %s", request.url.path, exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Error interno del servidor al procesar la solicitud."},
        )

    app.include_router(router)
    return app


app = create_app()
