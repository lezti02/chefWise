import { Component, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
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
  results = signal<Recipe[]>([]);

  constructor(private recipeService: RecipeService) {}

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
   * Busca qué se puede cocinar. Mock — ver el comentario completo en
   * RecipeService.getHaveIngredientsSuggestions para la forma del endpoint real.
   */
  search(): void {
    this.results.set(
      this.recipeService.getHaveIngredientsSuggestions(this.ingredients(), this.servings(), this.allowExtras())
    );
  }

  onToggleFavorite(id: string): void {
    this.recipeService.toggleFavorite(id);
  }

  onToggleSaved(id: string): void {
    this.recipeService.toggleSaved(id);
  }
}
