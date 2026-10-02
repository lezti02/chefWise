"""Endpoints HTTP. Toda la lógica de recomendación vive en `src/`."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request

from src.preferences import UserPreferences
from src.recommender import RecommendationResult, Recommender

from .schemas import (
    ErrorResponse,
    HealthResponse,
    IngredientsRequest,
    RecipeResponse,
    RecommendationItem,
    RecommendationMeta,
    RecommendationRequest,
    RecommendationResponse,
)

router = APIRouter()


def get_recommender(request: Request) -> Recommender:
    """El recomendador se crea una vez en el arranque (ver `main.lifespan`)."""
    return request.app.state.recommender


RecommenderDep = Annotated[Recommender, Depends(get_recommender)]


def _to_response(result: RecommendationResult) -> RecommendationResponse:
    return RecommendationResponse(
        recommendations=[
            RecommendationItem(**item.summary, similarity=item.similarity, score=item.score)
            for item in result.items
        ],
        meta=RecommendationMeta(
            candidates=result.candidates,
            query_text=result.query_text,
            applied_max_time=result.max_minutes,
            relaxed=result.relaxed,
        ),
    )


@router.get("/health", response_model=HealthResponse, tags=["sistema"])
def health() -> HealthResponse:
    return HealthResponse()


@router.post("/recommendations", response_model=RecommendationResponse, tags=["recomendaciones"])
def recommendations(body: RecommendationRequest, recommender: RecommenderDep) -> RecommendationResponse:
    prefs = UserPreferences(
        moods=tuple(body.antojos),
        difficulty=body.difficulty,
        max_time=body.max_time,
        countries=tuple(body.countries),
        exclude_ids=tuple(body.exclude_ids),
        top_n=body.top_n,
    )
    return _to_response(recommender.recommend(prefs))


@router.post("/recommendations/by-ingredients", response_model=RecommendationResponse, tags=["recomendaciones"])
def recommendations_by_ingredients(body: IngredientsRequest, recommender: RecommenderDep) -> RecommendationResponse:
    result = recommender.recommend_by_ingredients(
        body.ingredients, exclude_ids=tuple(body.exclude_ids), top_n=body.top_n
    )
    return _to_response(result)


@router.get(
    "/recipes/{recipe_id}",
    response_model=RecipeResponse,
    responses={404: {"model": ErrorResponse}},
    tags=["recetas"],
)
def get_recipe(
    recommender: RecommenderDep,
    recipe_id: Annotated[int, Path(ge=1, description="recipe_id del dataset")],
) -> RecipeResponse:
    return RecipeResponse(**recommender.get_recipe(recipe_id))
