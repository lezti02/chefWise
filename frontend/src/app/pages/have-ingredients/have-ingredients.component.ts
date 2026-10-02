import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';
import { RecipeCardComponent } from '../../shared/recipe-card/recipe-card.component';
import { RecipeService } from '../../services/recipe.service';
import { Recipe } from '../../models/recipe.model';

@Component({
  selector: 'app-have-ingredients',
  standalone: true,
  imports: [RouterLink, RecipeCardComponent],
  templateUrl: './have-ingredients.component.html',
  styleUrl: './have-ingredients.component.scss',
})
export class HaveIngredientsComponent {
  ingredients = signal<string[]>(['jitomate ×3', 'cebolla', 'arroz — 1 taza', 'huevos ×4']);
  servings = signal(2);
  /** false = "Solo con esto", true = "Permitir 1-2 extras" */
  allowExtras = signal(false);
  loading = signal(false);
  error = signal<string | null>(null);
  private results = signal<Recipe[]>([]);
  visibleResults = computed(() =>
    this.recipeService.filterForUser(this.results()).map(r => this.recipeService.decorate(r))
  );

  private request?: Subscription;

  constructor(public recipeService: RecipeService) {
    inject(DestroyRef).onDestroy(() => this.request?.unsubscribe());
  }

  addIngredient(input: HTMLInputElement): void {
    const value = input.value.trim();
    if (value) this.ingredients.update(list => [...list, value]);
    input.value = '';
  }

  removeIngredient(index: number): void {
    this.ingredients.update(list => list.filter((_, i) => i !== index));
  }

  incServings(): void {
    this.servings.update(v => v + 1);
  }

  decServings(): void {
    this.servings.update(v => Math.max(1, v - 1));
  }

  setAllowExtras(value: boolean): void {
    this.allowExtras.set(value);
  }

  /**
   * Busca qué se puede cocinar con los ingredientes escritos
   * (POST /recommendations/by-ingredients). Personas y "extras" aún no los usa el modelo.
   */
  search(): void {
    if (!this.ingredients().length) return;
    this.request?.unsubscribe();
    this.loading.set(true);
    this.error.set(null);
    this.request = this.recipeService.getHaveIngredientsSuggestions(this.ingredients()).subscribe({
      next: list => {
        this.results.set(list);
        this.loading.set(false);
      },
      error: () => {
        this.results.set([]);
        this.error.set('No pudimos obtener recetas del servidor. Revisa que el backend esté en marcha e inténtalo de nuevo.');
        this.loading.set(false);
      },
    });
  }

  onToggleFavorite(id: string): void {
    this.recipeService.toggleFavorite(id);
  }

  onToggleSaved(id: string): void {
    this.recipeService.toggleSaved(id);
  }

  onHide(id: string): void {
    this.recipeService.hide(id);
  }
}
