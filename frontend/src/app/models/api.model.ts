/**
 * Contrato HTTP con el backend (espejo de backend/schemas.py).
 * Los nombres de campo son los del dataset (snake_case).
 */

import { Difficulty, MealCategory } from './recipe.model';

export interface RecommendationRequestDto {
  antojos: string[];
  difficulty: Difficulty | null;
  max_time: number | null;
  countries: string[];
  exclude_ids: number[];
  top_n: number;
}

export interface IngredientsRequestDto {
  ingredients: string[];
  exclude_ids: number[];
  top_n: number;
}

export interface RecipeSummaryDto {
  recipe_id: number;
  name: string;
  ingredients: string[];
  difficulty: Difficulty | null;
  total_time_min: number | null;
  servings: number | null;
  country: string | null;
  category: MealCategory | null;
  meal_type: string | null;
  rating: number | null;
  rating_votes: number | null;
  source: string | null;
  source_url: string | null;
}

export interface RecommendationItemDto extends RecipeSummaryDto {
  similarity: number | null;
  score: number;
}

export interface RecommendationResponseDto {
  recommendations: RecommendationItemDto[];
  meta: {
    candidates: number;
    query_text: string | null;
    applied_max_time: number | null;
    relaxed: string[];
  };
}

export interface RecipeDto extends RecipeSummaryDto {
  instructions: string[];
  difficulty_source: string | null;
  prep_time_min: number | null;
  cook_time_min: number | null;
  category_tags: string[];
  diet_tags: string[];
  description: string | null;
  num_comments: number | null;
}
