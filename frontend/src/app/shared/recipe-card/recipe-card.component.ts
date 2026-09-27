import { Component, EventEmitter, Input, Output } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Recipe } from '../../models/recipe.model';

/**
 * Tarjeta de receta reutilizable (usada en grids: Sorpréndeme, Con lo que
 * tengo, Favoritas dentro de Mi cocina). Navega al detalle al hacer click en
 * cualquier parte, EXCEPTO en los íconos de favorito/guardar, que emiten un
 * evento hacia el componente padre en vez de navegar.
 */
@Component({
  selector: 'app-recipe-card',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './recipe-card.component.html',
  styleUrl: './recipe-card.component.scss',
})
export class RecipeCardComponent {
  @Input({ required: true }) recipe!: Recipe;
  /** Texto opcional para el renglón de metadatos; si no se pasa, se arma uno por default. */
  @Input() metaOverride?: string;
  @Output() toggleFavorite = new EventEmitter<string>();
  @Output() toggleSaved = new EventEmitter<string>();

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
