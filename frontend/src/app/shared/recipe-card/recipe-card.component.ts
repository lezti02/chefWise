import { Component, EventEmitter, Input, Output, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Recipe } from '../../models/recipe.model';
import { RecipeService } from '../../services/recipe.service';

/**
 * Tarjeta de receta reutilizable (usada en grids: Sorpréndeme, Con lo que
 * tengo, Favoritas dentro de Mi cocina). Navega al detalle al hacer click en
 * cualquier parte, EXCEPTO en los íconos de favorito/guardar/ocultar, que
 * emiten un evento hacia el componente padre en vez de navegar.
 */
@Component({
  selector: 'app-recipe-card',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './recipe-card.component.html',
  styleUrl: './recipe-card.component.scss',
})
export class RecipeCardComponent {
  private recipeService = inject(RecipeService);

  @Input({ required: true }) recipe!: Recipe;
  /** Texto opcional para el renglón de metadatos; si no se pasa, se arma uno por default. */
  @Input() metaOverride?: string;
  /** Muestra el botón "No volver a mostrar" (tiene sentido en recomendaciones, no en Favoritas). */
  @Input() showHide = true;
  @Output() toggleFavorite = new EventEmitter<string>();
  @Output() toggleSaved = new EventEmitter<string>();
  @Output() hide = new EventEmitter<string>();

  /** Renglón por defecto: solo muestra los datos que el dataset sí tiene. */
  get meta(): string {
    const r = this.recipe;
    return [
      r.minutes ? `${r.minutes} min` : null,
      r.neverCooked ? 'nunca cocinada' : r.servings ? `${r.servings} porciones` : null,
    ]
      .filter(Boolean)
      .join(' · ');
  }

  get allergens(): string[] {
    return this.recipeService.allergensIn(this.recipe);
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

  onHideClick(e: Event): void {
    e.preventDefault();
    e.stopPropagation();
    this.hide.emit(this.recipe.id);
  }
}
