/**
 * Respuestas de ejemplo del backend, SOLO para las pruebas (los specs no
 * levantan el servidor). Tienen la forma exacta de `models/api.model.ts`.
 */
import { RecipeDto, RecommendationItemDto, RecommendationResponseDto } from '../models/api.model';

export function itemDto(id: number, overrides: Partial<RecommendationItemDto> = {}): RecommendationItemDto {
  return {
    recipe_id: id,
    name: `Receta ${id}`,
    ingredients: ['2 huevos', '1 taza de leche'],
    difficulty: 'facil',
    total_time_min: 25,
    servings: 4,
    country: 'México',
    category: 'comida',
    meal_type: null,
    rating: 4.5,
    rating_votes: 10,
    source: 'RecetasGratis',
    source_url: `https://example.test/${id}`,
    similarity: 0.2,
    score: 0.25,
    ...overrides,
  };
}

export function recommendationsResponse(items: RecommendationItemDto[]): RecommendationResponseDto {
  return { recommendations: items, meta: { candidates: items.length, query_text: null, applied_max_time: 30, relaxed: [] } };
}

export function recipeDto(id: number, overrides: Partial<RecipeDto> = {}): RecipeDto {
  return {
    ...itemDto(id),
    instructions: ['Bate los huevos.', 'Cocina a fuego medio.'],
    difficulty_source: 'baja',
    prep_time_min: null,
    cook_time_min: null,
    category_tags: [],
    diet_tags: [],
    description: null,
    num_comments: null,
    ...overrides,
  };
}
