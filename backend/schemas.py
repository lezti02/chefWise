"""Contrato HTTP entre el frontend (Angular) y el backend.

Los nombres de campo coinciden con las columnas del dataset procesado
(`recipe_id`, `total_time_min`, `country`, `rating`...). Los valores de
`difficulty` y `category` son los de `app_difficulty` / `app_category`, que ya
son los que usa el frontend. Un campo que el CSV no tiene para una receta
viaja como `null`; nunca se rellena con texto inventado.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Antojo = Literal["rapido", "saludable", "reconfortante", "dulce", "picante", "ligero"]
Difficulty = Literal["facil", "intermedio", "reto"]
MealCategory = Literal["desayuno", "comida", "cena", "postre", "bebida"]


class RecommendationRequest(BaseModel):
    """Preferencias de "Sorpréndeme"."""

    model_config = ConfigDict(extra="forbid")

    antojos: list[Antojo] = Field(default_factory=list, max_length=6, description="Chips de 'Antojo'.")
    difficulty: Difficulty | None = Field(None, description="'Nivel de experiencia'.")
    max_time: int | None = Field(None, ge=1, le=720, description="Minutos disponibles.")
    countries: list[str] = Field(default_factory=list, max_length=40, description="Vacío = cualquier país.")
    exclude_ids: list[int] = Field(default_factory=list, max_length=5000, description="recipe_id a omitir.")
    top_n: int = Field(12, ge=1, le=50)


class IngredientsRequest(BaseModel):
    """Ingredientes de "Con lo que tengo"."""

    model_config = ConfigDict(extra="forbid")

    ingredients: list[str] = Field(min_length=1, max_length=50)
    exclude_ids: list[int] = Field(default_factory=list, max_length=5000)
    top_n: int = Field(12, ge=1, le=50)


class RecipeSummary(BaseModel):
    """Lo necesario para pintar una tarjeta."""

    recipe_id: int
    name: str
    ingredients: list[str]
    difficulty: Difficulty | None
    total_time_min: int | None
    servings: int | None
    country: str | None
    category: MealCategory | None
    meal_type: str | None
    rating: float | None
    rating_votes: int | None
    source: str | None
    source_url: str | None


class RecommendationItem(RecipeSummary):
    similarity: float | None = Field(None, description="Coseno TF-IDF; null si no hubo consulta de texto.")
    score: float = Field(description="similitud + peso de calidad; es el valor por el que se ordena.")


class RecommendationMeta(BaseModel):
    candidates: int = Field(description="Recetas que pasaron los filtros antes del Top-N.")
    query_text: str | None
    applied_max_time: int | None
    relaxed: list[str] = Field(default_factory=list, description="Filtros blandos que se relajaron.")


class RecommendationResponse(BaseModel):
    recommendations: list[RecommendationItem]
    meta: RecommendationMeta


class RecipeResponse(RecipeSummary):
    """Receta completa (GET /recipes/{recipe_id})."""

    instructions: list[str]
    difficulty_source: str | None = Field(description="Valor original de `difficulty` en el CSV.")
    prep_time_min: int | None
    cook_time_min: int | None
    category_tags: list[str]
    diet_tags: list[str]
    description: str | None
    num_comments: int | None


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ErrorResponse(BaseModel):
    detail: str
