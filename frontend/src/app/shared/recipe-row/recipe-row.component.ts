import { Component, EventEmitter, Input, Output } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Recipe } from '../../models/recipe.model';

/**
 * Fila de receta en formato lista (usada en: Inicio → "Cocinados
 * recientemente", Mi cocina → Historial y Quiero cocinar).
 */
@Component({
  selector: 'app-recipe-row',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './recipe-row.component.html',
  styleUrl: './recipe-row.component.scss',
})
export class RecipeRowComponent {
  @Input({ required: true }) recipe!: Recipe;
  @Input() metaOverride?: string;
  /** Oculta los íconos de favorito/guardar, útil en listas de solo lectura. */
  @Input() showIcons = true;
  @Output() toggleFavorite = new EventEmitter<string>();
  @Output() toggleSaved = new EventEmitter<string>();

  /** Renglón por defecto: solo muestra los datos que el dataset sí tiene. */
  get meta(): string {
    const r = this.recipe;
    return [r.minutes ? `${r.minutes} min` : null, r.servings ? `${r.servings} porciones` : null]
      .filter(Boolean)
      .join(' · ');
  }

  onFavoriteClick(e: Event): void {
    e.preventDefault();
    e.stopPropagation();
    this.toggleFavorite.emit(this.recipe.id);
  }

  onSavedClick(e: Event): void {
    e.preventDefault();
    e.stopPropagation();
    this.toggleSaved.emit(this.recipe.id);
  }
}
