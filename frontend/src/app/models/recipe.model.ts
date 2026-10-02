/**
 * Modelo de datos de una receta en el frontend.
 *
 * Las recetas vienen del backend (ver `models/api.model.ts` para el contrato
 * HTTP y `services/recipe-api.service.ts` para la conversión DTO → Recipe).
 * Los campos que el dataset no tiene para una receta llegan como `null`; la UI
 * los omite en lugar de inventarlos.
 *
 * `neverCooked`, `isFavorite`, `isSaved` y `lastCookedAt` NO vienen del dataset:
 * son estado del usuario que mantiene `RecipeService` (localStorage, mientras
 * no exista base de datos).
 */

export type MealCategory = 'desayuno' | 'comida' | 'cena' | 'postre' | 'bebida';
export type Difficulty = 'facil' | 'intermedio' | 'reto';

export interface RecipeIngredient {
  /** Renglón tal cual viene del dataset (cantidad + ingrediente, p. ej. "2 tazas de harina"). */
  name: string;
  /** El dataset no separa cantidades; queda vacío. */
  amount: string;
}

export interface Recipe {
  /** `recipe_id` del dataset, como texto (se usa en la URL: /receta/:id). */
  id: string;
  name: string;
  category: MealCategory | null;
  country: string | null;    // mismo valor que la columna `country` del dataset (ej. 'México', 'Internacional')
  minutes: number | null;    // `total_time_min`
  servings: number | null;
  difficulty: Difficulty | null; // `app_difficulty`
  rating: number | null;
  sourceUrl: string | null;
  neverCooked: boolean;
  isFavorite: boolean;
  isSaved: boolean;          // "guardada para cocinar después"
  lastCookedAt: string | null; // ISO date string, o null si nunca se ha cocinado
  ingredients: RecipeIngredient[];
  /** Vacío en las tarjetas; solo se llena al abrir el detalle (GET /recipes/{id}). */
  steps: string[];
}

/** Antojos de Sorpréndeme: etiqueta de la UI → valor que entiende el backend. */
export const MOODS: { label: string; value: string }[] = [
  { label: 'Algo rápido', value: 'rapido' },
  { label: 'Saludable', value: 'saludable' },
  { label: 'Reconfortante', value: 'reconfortante' },
  { label: 'Dulce', value: 'dulce' },
  { label: 'Picante', value: 'picante' },
  { label: 'Ligero', value: 'ligero' },
];

export const DIFFICULTY_LABELS: Record<Difficulty, string> = {
  facil: 'Fácil',
  intermedio: 'Intermedio',
  reto: 'Reto',
};

/**
 * Agrupación de los valores de `country` del dataset en regiones, para el
 * filtro "País o región" de Sorpréndeme.
 */
export const REGIONS: { name: string; countries: string[] }[] = [
  { name: 'Norteamérica', countries: ['México'] },
  {
    name: 'Centroamérica y Caribe',
    countries: ['Costa Rica', 'Cuba', 'El Salvador', 'Guatemala', 'Honduras', 'Nicaragua', 'Panama', 'Puerto Rico', 'República Dominicana'],
  },
  {
    name: 'Sudamérica',
    countries: ['Argentina', 'Bolivia', 'Chile', 'Colombia', 'Ecuador', 'Paraguay', 'Perú', 'Uruguay', 'Venezuela'],
  },
  { name: 'Europa', countries: ['España'] },
  { name: 'Internacional', countries: ['Internacional'] },
];

/** 'any' | 'region:<nombre>' | 'country:<país>' */
export type PlaceFilter = string;

export interface Allergen {
  id: string;
  label: string;
  /** Palabras que delatan el alérgeno en el nombre de un ingrediente (sin acentos). */
  keywords: string[];
  /** Frases que contienen una keyword pero NO son el alérgeno (ej. "leche de coco"). */
  exceptions?: string[];
}

export const COMMON_ALLERGENS: Allergen[] = [
  {
    id: 'lacteos', label: 'Lácteos',
    keywords: ['leche', 'queso', 'yogur', 'yogurt', 'crema', 'mantequilla', 'nata', 'requeson', 'suero de leche', 'jocoque', 'ghee'],
    exceptions: ['leche de coco', 'leche de almendra', 'leche de soya', 'leche de soja', 'leche de avena', 'leche de arroz', 'crema de cacahuate', 'crema de mani', 'crema de coco'],
  },
  {
    id: 'gluten', label: 'Gluten',
    keywords: ['harina', 'trigo', 'pan', 'pasta', 'espagueti', 'fideo', 'galleta', 'cebada', 'centeno', 'cuscus', 'seitan', 'cerveza', 'tortilla de harina', 'tortillas de trigo'],
    exceptions: ['harina de maiz', 'harina de arroz', 'harina de almendra', 'harina de coco', 'pasta de tomate', 'pasta de achiote', 'pasta de chile'],
  },
  { id: 'huevo', label: 'Huevo', keywords: ['huevo', 'yema', 'clara de huevo', 'mayonesa', 'merengue'] },
  {
    id: 'frutos-secos', label: 'Frutos secos',
    keywords: ['nuez', 'nueces', 'almendra', 'avellana', 'pistache', 'pistacho', 'anacardo', 'maranon', 'castana', 'pinon', 'pecana'],
    exceptions: ['nuez moscada'],
  },
  { id: 'cacahuate', label: 'Cacahuate', keywords: ['cacahuate', 'cacahuete', 'mani'] },
  {
    id: 'mariscos', label: 'Mariscos',
    keywords: ['marisco', 'camaron', 'gamba', 'langosta', 'langostino', 'cangrejo', 'jaiba', 'pulpo', 'calamar', 'mejillon', 'almeja', 'ostion', 'ostra', 'vieira'],
  },
  {
    id: 'pescado', label: 'Pescado',
    keywords: ['pescado', 'salmon', 'atun', 'bacalao', 'sardina', 'merluza', 'tilapia', 'anchoa', 'trucha', 'robalo', 'huachinango', 'corvina', 'lenguado', 'mojarra'],
  },
  { id: 'soya', label: 'Soya', keywords: ['soya', 'soja', 'tofu', 'edamame', 'miso', 'tempeh'] },
  { id: 'sesamo', label: 'Ajonjolí', keywords: ['ajonjoli', 'sesamo', 'tahini', 'tahin'] },
];
