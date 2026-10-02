import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { RecipeDetailComponent } from './recipe-detail.component';
import { recipeDto } from '../../testing/api-fixtures';

describe('RecipeDetailComponent (GET /recipes/{id})', () => {
  let http: HttpTestingController;
  let harness: RouterTestingHarness;

  beforeEach(async () => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideZonelessChangeDetection(),
        provideRouter([{ path: 'receta/:id', component: RecipeDetailComponent }]),
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpTestingController);
    harness = await RouterTestingHarness.create();
  });

  afterEach(() => http.verify());

  it('abre la receta con el recipe_id de la URL y muestra ingredientes y pasos del backend', async () => {
    await harness.navigateByUrl('/receta/123', RecipeDetailComponent);

    const req = http.expectOne(r => r.url.endsWith('/recipes/123'));
    req.flush(
      recipeDto(123, {
        name: 'Tacos de pollo reales',
        ingredients: ['500 g de pechuga', '12 tortillas'],
        instructions: ['Cuece el pollo.', 'Calienta las tortillas.'],
        total_time_min: null,
      })
    );
    await harness.fixture.whenStable();
    harness.detectChanges();

    const el = harness.routeNativeElement as HTMLElement;
    expect(el.querySelector('h1')?.textContent).toContain('Tacos de pollo reales');
    expect(Array.from(el.querySelectorAll('.ing-list li')).map(li => li.querySelector('span')?.textContent)).toEqual([
      '500 g de pechuga',
      '12 tortillas',
    ]);
    expect(Array.from(el.querySelectorAll('.steps li')).map(li => li.textContent?.trim())).toEqual([
      'Cuece el pollo.',
      'Calienta las tortillas.',
    ]);
    // Tiempo desconocido en el dataset => no se inventa un "0 min".
    expect(el.querySelector('.detail-meta')?.textContent).not.toContain('min');
  });

  it('si la receta no trae instrucciones no inventa pasos', async () => {
    await harness.navigateByUrl('/receta/5', RecipeDetailComponent);
    http.expectOne(r => r.url.endsWith('/recipes/5')).flush(recipeDto(5, { instructions: [] }));
    await harness.fixture.whenStable();
    harness.detectChanges();

    const el = harness.routeNativeElement as HTMLElement;
    expect(el.querySelectorAll('.steps li').length).toBe(0);
    expect(el.textContent).toContain('no tiene instrucciones registradas');
  });

  it('receta inexistente (404) muestra "No encontramos esta receta."', async () => {
    await harness.navigateByUrl('/receta/99999999', RecipeDetailComponent);
    http
      .expectOne(r => r.url.endsWith('/recipes/99999999'))
      .flush({ detail: 'No existe' }, { status: 404, statusText: 'Not Found' });
    await harness.fixture.whenStable();
    harness.detectChanges();

    expect((harness.routeNativeElement as HTMLElement).textContent).toContain('No encontramos esta receta.');
  });
});
