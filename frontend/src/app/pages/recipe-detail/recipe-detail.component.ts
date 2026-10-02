import { Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Observable, catchError, map, of, startWith, switchMap } from 'rxjs';
import { RecipeService } from '../../services/recipe.service';
import { DIFFICULTY_LABELS, Recipe } from '../../models/recipe.model';

type DetailState =
  | { status: 'loading' }
  | { status: 'ok'; recipe: Recipe }
  | { status: 'not-found' }
  | { status: 'error' };

@Component({
  selector: 'app-recipe-detail',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './recipe-detail.component.html',
  styleUrl: './recipe-detail.component.scss',
})
export class RecipeDetailComponent {
  private route = inject(ActivatedRoute);
  private recipeService = inject(RecipeService);

  difficultyLabels = DIFFICULTY_LABELS;

  /** GET /recipes/{id} cada vez que cambia el :id de la URL. */
  state = toSignal(
    this.route.paramMap.pipe(
      map(p => p.get('id') ?? ''),
      switchMap(id => this.load(id))
    ),
    { initialValue: { status: 'loading' } as DetailState }
  );

  recipe = computed(() => {
    const s = this.state();
    return s.status === 'ok' ? this.recipeService.decorate(s.recipe) : null;
  });

  allergens = computed(() => {
    const r = this.recipe();
    return r ? this.recipeService.allergensIn(r) : [];
  });

  private load(id: string): Observable<DetailState> {
    if (!/^\d+$/.test(id)) return of({ status: 'not-found' });
    return this.recipeService.loadRecipe(id).pipe(
      map((recipe): DetailState => ({ status: 'ok', recipe })),
      catchError((e: unknown) =>
        of<DetailState>({ status: e instanceof HttpErrorResponse && (e.status === 404 || e.status === 422) ? 'not-found' : 'error' })
      ),
      startWith<DetailState>({ status: 'loading' })
    );
  }

  toggleFavorite(): void {
    const r = this.recipe();
    if (r) this.recipeService.toggleFavorite(r.id);
  }

  toggleSaved(): void {
    const r = this.recipe();
    if (r) this.recipeService.toggleSaved(r.id);
  }

  /**
   * "Cociné esto": registra la receta en el historial (RecipeService.markCooked).
   * Esto es justo lo que alimenta la pestaña "Historial" y "Resumen" de Mi cocina.
   */
  markCooked(): void {
    const r = this.recipe();
    if (r) this.recipeService.markCooked(r.id);
  }
}
