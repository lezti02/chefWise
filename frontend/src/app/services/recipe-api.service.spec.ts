import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { RecipeApiService } from './recipe-api.service';
import { itemDto, recipeDto, recommendationsResponse } from '../testing/api-fixtures';

describe('RecipeApiService', () => {
  let api: RecipeApiService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideZonelessChangeDetection(), provideHttpClient(), provideHttpClientTesting()],
    });
    api = TestBed.inject(RecipeApiService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('POST /recommendations envía las preferencias y convierte la respuesta en recetas', () => {
    let result: ReturnType<typeof Object> | undefined;
    const request = {
      antojos: ['rapido'],
      difficulty: 'facil' as const,
      max_time: 30,
      countries: [],
      exclude_ids: [],
      top_n: 12,
    };

    api.recommend(request).subscribe(r => (result = r));

    const req = http.expectOne(r => r.url.endsWith('/recommendations'));
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual(request);
    req.flush(recommendationsResponse([itemDto(123, { name: 'Tacos reales', total_time_min: null, country: null })]));

    const [recipe] = result as any[];
    expect(recipe.id).toBe('123');
    expect(recipe.name).toBe('Tacos reales');
    expect(recipe.minutes).toBeNull();
    expect(recipe.country).toBeNull();
    expect(recipe.ingredients).toEqual([
      { name: '2 huevos', amount: '' },
      { name: '1 taza de leche', amount: '' },
    ]);
    expect(recipe.steps).toEqual([]);
  });

  it('GET /recipes/{id} trae ingredientes y pasos tal cual los devuelve el backend', () => {
    let result: any;
    api.getRecipe('42').subscribe(r => (result = r));

    const req = http.expectOne(r => r.url.endsWith('/recipes/42'));
    expect(req.request.method).toBe('GET');
    req.flush(recipeDto(42, { instructions: ['Paso uno real', 'Paso dos real'] }));

    expect(result.id).toBe('42');
    expect(result.steps).toEqual(['Paso uno real', 'Paso dos real']);
  });

  it('POST /recommendations/by-ingredients', () => {
    api.recommendByIngredients({ ingredients: ['pollo'], exclude_ids: [], top_n: 5 }).subscribe();
    const req = http.expectOne(r => r.url.endsWith('/recommendations/by-ingredients'));
    expect(req.request.body.ingredients).toEqual(['pollo']);
    req.flush(recommendationsResponse([]));
  });
});
