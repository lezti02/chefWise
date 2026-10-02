import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map } from 'rxjs';
import { environment } from '../../environments/environment';
import {
  IngredientsRequestDto,
  RecipeDto,
  RecipeSummaryDto,
  RecommendationRequestDto,
  RecommendationResponseDto,
} from '../models/api.model';
import { Recipe } from '../models/recipe.model';

/** Cliente HTTP del backend. Solo habla con la API y convierte DTO → Recipe. */
@Injectable({ providedIn: 'root' })
export class RecipeApiService {
  private http = inject(HttpClient);
  private baseUrl = environment.apiUrl.replace(/\/+$/, '');

  /** POST /recommendations */
  recommend(request: RecommendationRequestDto): Observable<Recipe[]> {
    return this.http
      .post<RecommendationResponseDto>(`${this.baseUrl}/recommendations`, request)
      .pipe(map(res => res.recommendations.map(toRecipe)));
  }

  /** POST /recommendations/by-ingredients */
  recommendByIngredients(request: IngredientsRequestDto): Observable<Recipe[]> {
    return this.http
      .post<RecommendationResponseDto>(`${this.baseUrl}/recommendations/by-ingredients`, request)
      .pipe(map(res => res.recommendations.map(toRecipe)));
  }

  /** GET /recipes/{recipe_id} — receta completa con pasos. */
  getRecipe(id: string): Observable<Recipe> {
    return this.http.get<RecipeDto>(`${this.baseUrl}/recipes/${encodeURIComponent(id)}`).pipe(map(toRecipe));
  }
}

/** Convierte lo que devuelve el backend en el modelo de UI (sin inventar campos). */
export function toRecipe(dto: RecipeSummaryDto | RecipeDto): Recipe {
  return {
    id: String(dto.recipe_id),
    name: dto.name,
    category: dto.category,
    country: dto.country,
    minutes: dto.total_time_min,
    servings: dto.servings,
    difficulty: dto.difficulty,
    rating: dto.rating,
    sourceUrl: dto.source_url,
    neverCooked: true,
    isFavorite: false,
    isSaved: false,
    lastCookedAt: null,
    ingredients: dto.ingredients.map(line => ({ name: line, amount: '' })),
    steps: 'instructions' in dto ? dto.instructions : [],
  };
}
