import { Injectable, computed, signal } from '@angular/core';
import { MealCategory, Recipe } from '../models/recipe.model';

@Injectable({ providedIn: 'root' })
export class RecipeService {

  /**
   * ESTADO MOCK — por ahora vive en memoria, en el navegador.
   *
   * INTEGRACIÓN CON BACKEND (Python):
   * 1) Crea GET /api/recipes en tu API que regrese un array de Recipe (mismo
   *    shape que recipe.model.ts).
   * 2) Inyecta HttpClient aquí (necesitas provideHttpClient() en app.config.ts,
   *    ya está comentado ahí, solo descoméntalo).
   * 3) En el constructor, reemplaza signal(MOCK_RECIPES) por signal([]) y haz:
   *
   *      constructor(private http: HttpClient) {
   *        this.http.get<Recipe[]>('/api/recipes')
   *          .subscribe(data => this._recipes.set(data));
   *      }
   *
   *    Con eso, todo lo demás en este archivo (favoritos, guardados, historial,
   *    estadísticas) sigue funcionando igual porque ya está construido sobre
   *    signals/computed reactivos, no sobre la lista mock directamente.
   */
  private readonly _recipes = signal<Recipe[]>(MOCK_RECIPES);
  readonly recipes = this._recipes.asReadonly();

  readonly favorites = computed(() => this._recipes().filter(r => r.isFavorite));
  readonly saved = computed(() => this._recipes().filter(r => r.isSaved));

  /** Recetas cocinadas, más recientes primero — alimenta el historial de "Mi cocina". */
  readonly history = computed(() =>
    [...this._recipes()]
      .filter(r => r.lastCookedAt)
      .sort((a, b) => (b.lastCookedAt! > a.lastCookedAt! ? 1 : -1))
  );

  /**
   * Distribución de categorías entre lo cocinado (para la pestaña "Resumen").
   * MOCK simple hecho en el cliente. En producción esto normalmente se calcula
   * en el backend (una consulta agregada), sobre todo el historial real del
   * usuario, no solo lo que hay cargado en el navegador.
   */
  readonly categoryStats = computed(() => {
    const cooked = this.history();
    const total = cooked.length || 1;
    const counts: Record<MealCategory, number> = { desayuno: 0, comida: 0, cena: 0, postre: 0, bebida: 0 };
    cooked.forEach(r => counts[r.category]++);
    return (Object.keys(counts) as MealCategory[])
      .map(category => ({ category, percent: Math.round((counts[category] / total) * 100) }))
      .filter(c => c.percent > 0);
  });

  getById(id: string): Recipe | undefined {
    return this._recipes().find(r => r.id === id);
    // TODO backend: si prefieres no cargar TODAS las recetas de golpe,
    // cambia esto por GET /api/recipes/{id} bajo demanda.
  }

  search(term: string): Recipe[] {
    const q = term.trim().toLowerCase();
    if (!q) return this._recipes();
    return this._recipes().filter(r =>
      r.name.toLowerCase().includes(q) ||
      r.ingredients.some(i => i.name.toLowerCase().includes(q))
    );
    // TODO backend: para búsqueda "de verdad" (tolerante a typos, por sinónimos,
    // etc.) esto es mejor resuelto server-side, ej. GET /api/recipes/search?q=...
  }

  toggleFavorite(id: string): void {
    this._update(id, r => ({ ...r, isFavorite: !r.isFavorite }));
    // TODO backend: POST /api/recipes/{id}/favorite  body: { isFavorite: boolean }
    // Importante: cada favorito es una interacción positiva del usuario.
    // Es justo la señal que tu recomendador de "Sorpréndeme" (filtrado
    // colaborativo / content-based) debería registrar para aprender el gusto.
  }

  toggleSaved(id: string): void {
    this._update(id, r => ({ ...r, isSaved: !r.isSaved }));
    // TODO backend: POST /api/recipes/{id}/save  body: { isSaved: boolean }
  }

  markCooked(id: string): void {
    this._update(id, r => ({ ...r, lastCookedAt: new Date().toISOString(), neverCooked: false }));
    // TODO backend: POST /api/recipes/{id}/cooked
    // Manda también contexto útil para tu modelo si lo tienes: porciones reales
    // que hizo el usuario, si sustituyó algún ingrediente, etc.
  }

  /**
   * "Sorpréndeme": recomendador de descubrimiento (gustos / momento).
   * MOCK: regresa las recetas marcadas como "nunca cocinadas".
   *
   * TODO backend: reemplazar por POST /api/recommend/surprise
   *   body:     { moods: string[], difficulty: Difficulty, maxMinutes: number }
   *   response: Recipe[]  (ya ordenadas por el modelo, de mayor a menor score)
   *
   * Aquí es donde conectas el filtrado por contenido + colaborativo +
   * re-ranking por diversidad que vimos en la estrategia.
   */
  getSurpriseSuggestions(moods: string[], difficulty: string, maxMinutes: number): Recipe[] {
    return this._recipes().filter(r => r.neverCooked);
  }

  /**
   * "Con lo que tengo": recomendador basado en ingredientes disponibles.
   * MOCK: regresa un par de recetas fijas.
   *
   * TODO backend: reemplazar por POST /api/recommend/have-ingredients
   *   body:     { ingredients: string[], servings: number, allowExtras: boolean }
   *   response: Recipe[]  (idealmente con un campo extra tipo
   *                        missingIngredients: string[] por receta)
   */
  getHaveIngredientsSuggestions(ingredients: string[], servings: number, allowExtras: boolean): Recipe[] {
    return this._recipes().slice(0, 2);
  }

  private _update(id: string, updater: (r: Recipe) => Recipe): void {
    this._recipes.update(list => list.map(r => (r.id === id ? updater(r) : r)));
  }
}

/**
 * Datos de ejemplo — bórralos cuando el backend esté conectado.
 */
const MOCK_RECIPES: Recipe[] = [
  {
    id: 'curry-garbanzo', name: 'Curry de garbanzo y espinaca', category: 'comida',
    minutes: 35, servings: 4, difficulty: 'facil', neverCooked: false,
    isFavorite: true, isSaved: false, lastCookedAt: '2026-09-24',
    ingredients: [
      { name: 'Garbanzo cocido', amount: '2 tazas' },
      { name: 'Espinaca fresca', amount: '3 tazas' },
      { name: 'Leche de coco', amount: '1 lata' },
      { name: 'Cebolla', amount: '1 pieza' },
      { name: 'Curry en polvo', amount: '1 cda' },
      { name: 'Ajo', amount: '2 dientes' },
    ],
    steps: [
      'Acitrona la cebolla y el ajo a fuego medio hasta que estén translúcidos, unos 4 minutos.',
      'Agrega el curry en polvo y mueve 30 segundos hasta que suelte aroma.',
      'Incorpora el garbanzo y la leche de coco. Deja hervir suavemente 12 minutos.',
      'Añade la espinaca al final y cocina solo hasta que se marchite, 2 minutos.',
    ],
  },
  {
    id: 'salmon-limon', name: 'Salmón al horno con limón', category: 'cena',
    minutes: 25, servings: 2, difficulty: 'facil', neverCooked: false,
    isFavorite: false, isSaved: false, lastCookedAt: '2026-09-19',
    ingredients: [
      { name: 'Filete de salmón', amount: '2 piezas' },
      { name: 'Limón', amount: '1 pieza' },
      { name: 'Aceite de oliva', amount: '1 cda' },
    ],
    steps: [
      'Precalienta el horno a 200°C.',
      'Coloca el salmón en una charola, baña con aceite y jugo de limón.',
      'Hornea 15 minutos o hasta que se desmenuce fácilmente.',
    ],
  },
  {
    id: 'tacos-coliflor', name: 'Tacos de coliflor asada', category: 'comida',
    minutes: 30, servings: 3, difficulty: 'facil', neverCooked: false,
    isFavorite: true, isSaved: false, lastCookedAt: '2026-09-15',
    ingredients: [
      { name: 'Coliflor', amount: '1 pieza' },
      { name: 'Tortillas de maíz', amount: '9 piezas' },
      { name: 'Especias para tacos', amount: '2 cdas' },
    ],
    steps: [
      'Corta la coliflor en floretes y mézclala con las especias y aceite.',
      'Asa a 220°C por 20 minutos, moviendo a la mitad.',
      'Sirve sobre tortillas calientes con tus toppings favoritos.',
    ],
  },
  {
    id: 'sopa-fria-pepino', name: 'Sopa fría de pepino y yogurt', category: 'comida',
    minutes: 15, servings: 2, difficulty: 'facil', neverCooked: true,
    isFavorite: false, isSaved: false, lastCookedAt: null,
    ingredients: [
      { name: 'Pepino', amount: '2 piezas' },
      { name: 'Yogurt natural', amount: '1 taza' },
      { name: 'Eneldo fresco', amount: 'al gusto' },
    ],
    steps: [
      'Licúa el pepino pelado con el yogurt hasta que quede tersa.',
      'Sazona con sal, pimienta y eneldo. Refrigera 20 minutos antes de servir.',
    ],
  },
  {
    id: 'arroz-frito-huevo', name: 'Arroz frito con huevo y jengibre', category: 'desayuno',
    minutes: 20, servings: 2, difficulty: 'facil', neverCooked: true,
    isFavorite: false, isSaved: false, lastCookedAt: null,
    ingredients: [
      { name: 'Arroz cocido (de un día antes)', amount: '2 tazas' },
      { name: 'Huevo', amount: '2 piezas' },
      { name: 'Jengibre fresco', amount: '1 cdita' },
    ],
    steps: [
      'Saltea el jengibre en aceite bien caliente unos segundos.',
      'Agrega el arroz y sofríe 4 minutos, moviendo constantemente.',
      'Haz espacio en el sartén, revuelve el huevo ahí y luego intégralo al arroz.',
    ],
  },
  {
    id: 'lentejas-curry-coco', name: 'Lentejas al curry con coco', category: 'cena',
    minutes: 35, servings: 4, difficulty: 'intermedio', neverCooked: true,
    isFavorite: false, isSaved: true, lastCookedAt: null,
    ingredients: [
      { name: 'Lenteja seca', amount: '1.5 tazas' },
      { name: 'Leche de coco', amount: '1 lata' },
      { name: 'Curry en polvo', amount: '1 cda' },
    ],
    steps: [
      'Cuece la lenteja en agua hasta que esté suave, cuela.',
      'Incorpora la leche de coco y el curry, deja hervir 10 minutos.',
    ],
  },
  {
    id: 'ensalada-quinoa', name: 'Ensalada tibia de quinoa', category: 'comida',
    minutes: 25, servings: 3, difficulty: 'facil', neverCooked: true,
    isFavorite: false, isSaved: true, lastCookedAt: null,
    ingredients: [
      { name: 'Quinoa', amount: '1 taza' },
      { name: 'Jitomate cherry', amount: '1 taza' },
      { name: 'Queso feta', amount: '100 g' },
    ],
    steps: [
      'Cuece la quinoa según las instrucciones del paquete.',
      'Mezcla tibia con jitomate, queso feta y un aderezo simple de limón y aceite.',
    ],
  },
  {
    id: 'arroz-huevo-jitomate', name: 'Arroz con huevo y salsa de jitomate', category: 'desayuno',
    minutes: 20, servings: 2, difficulty: 'facil', neverCooked: false,
    isFavorite: false, isSaved: false, lastCookedAt: '2026-09-10',
    ingredients: [
      { name: 'Arroz cocido', amount: '1 taza' },
      { name: 'Huevo', amount: '4 piezas' },
      { name: 'Jitomate', amount: '3 piezas' },
    ],
    steps: [
      'Prepara una salsa sencilla licuando el jitomate con cebolla y ajo.',
      'Fríe la salsa, agrega los huevos y revuelve hasta cuajar.',
      'Sirve sobre el arroz caliente.',
    ],
  },
  {
    id: 'tortilla-espanola', name: 'Tortilla española sencilla', category: 'desayuno',
    minutes: 30, servings: 4, difficulty: 'intermedio', neverCooked: false,
    isFavorite: false, isSaved: false, lastCookedAt: '2026-09-22',
    ingredients: [
      { name: 'Papa', amount: '4 piezas' },
      { name: 'Huevo', amount: '6 piezas' },
      { name: 'Cebolla', amount: '1 pieza' },
    ],
    steps: [
      'Corta la papa y cebolla en láminas finas, fríe a fuego bajo hasta suavizar.',
      'Mezcla con el huevo batido y cocina en sartén por ambos lados.',
    ],
  },
  {
    id: 'pastel-zanahoria', name: 'Pastel de zanahoria', category: 'postre',
    minutes: 50, servings: 8, difficulty: 'intermedio', neverCooked: false,
    isFavorite: true, isSaved: false, lastCookedAt: null,
    ingredients: [
      { name: 'Zanahoria rallada', amount: '2 tazas' },
      { name: 'Harina', amount: '2 tazas' },
      { name: 'Azúcar', amount: '1.5 tazas' },
    ],
    steps: [
      'Mezcla los ingredientes secos y aparte los húmedos, luego combina.',
      'Hornea a 180°C por 35-40 minutos.',
    ],
  },
  {
    id: 'agua-jamaica', name: 'Agua de jamaica', category: 'bebida',
    minutes: 10, servings: 6, difficulty: 'facil', neverCooked: false,
    isFavorite: true, isSaved: false, lastCookedAt: null,
    ingredients: [
      { name: 'Flor de jamaica seca', amount: '1 taza' },
      { name: 'Agua', amount: '2 litros' },
      { name: 'Azúcar', amount: 'al gusto' },
    ],
    steps: [
      'Hierve la jamaica en agua 10 minutos.',
      'Cuela, endulza y deja enfriar antes de servir con hielo.',
    ],
  },
];
