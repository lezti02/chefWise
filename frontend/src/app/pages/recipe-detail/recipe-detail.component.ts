import { Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { map } from 'rxjs';
import { RecipeService } from '../../services/recipe.service';

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

  private id = toSignal(this.route.paramMap.pipe(map(p => p.get('id') ?? '')), { initialValue: '' });
  recipe = computed(() => this.recipeService.getById(this.id()));

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
