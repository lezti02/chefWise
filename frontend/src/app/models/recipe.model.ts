/**
 * Modelo de datos de una receta.
 *
 * INTEGRACIÓN CON BACKEND:
 * Este es el "contrato" entre tu API de Python y el frontend. Lo que sea que
 * regrese tu endpoint FastAPI/Flask en /api/recipes debe tener esta misma forma
 * (o transformarlo aquí mismo antes de usarlo). Si tu backend regresa nombres de
 * campo distintos (snake_case, por ejemplo), lo más limpio es mapearlos una sola
 * vez dentro de RecipeService, no en cada componente.
 */

export type MealCategory = 'desayuno' | 'comida' | 'cena' | 'postre' | 'bebida';
export type Difficulty = 'facil' | 'intermedio' | 'reto';

export interface RecipeIngredient {
  name: string;
  amount: string;
}

export interface Recipe {
  id: string;
  name: string;
  category: MealCategory;
  minutes: number;
  servings: number;
  difficulty: Difficulty;
  neverCooked: boolean;
  isFavorite: boolean;
  isSaved: boolean;          // "guardada para cocinar después"
  lastCookedAt: string | null; // ISO date string, o null si nunca se ha cocinado
  ingredients: RecipeIngredient[];
  steps: string[];
}
