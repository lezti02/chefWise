import { Component, computed, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { RecipeRowComponent } from '../../shared/recipe-row/recipe-row.component';
import { RecipeService } from '../../services/recipe.service';
import { MealCategory } from '../../models/recipe.model';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [RouterLink, RecipeRowComponent],
  templateUrl: './home.component.html',
  styleUrl: './home.component.scss',
})
export class HomeComponent {
  searchTerm = signal('');
  selectedCategory = signal<MealCategory | 'all'>('all');

  categories: { value: MealCategory | 'all'; label: string }[] = [
    { value: 'all', label: 'Todas' },
    { value: 'desayuno', label: 'Desayuno' },
    { value: 'comida', label: 'Comida' },
    { value: 'cena', label: 'Cena' },
    { value: 'postre', label: 'Postre' },
    { value: 'bebida', label: 'Bebidas' },
  ];

  constructor(public recipeService: RecipeService) {}

  /**
   * Últimas cocinadas, filtradas por categoría elegida y por texto buscado.
   * NOTA: este buscador solo filtra el historial local del usuario. Buscar en
   * todo el catálogo requerirá un endpoint de búsqueda en el backend (con debounce).
   */
  recentFiltered = computed(() => {
    let list = this.recipeService.history().slice(0, 6);
    if (this.selectedCategory() !== 'all') {
      list = list.filter(r => r.category === this.selectedCategory());
    }
    const term = this.searchTerm().trim().toLowerCase();
    if (term) list = list.filter(r => r.name.toLowerCase().includes(term));
    return list;
  });

  selectCategory(cat: MealCategory | 'all'): void {
    this.selectedCategory.set(cat);
  }

  onToggleFavorite(id: string): void {
    this.recipeService.toggleFavorite(id);
  }

  onToggleSaved(id: string): void {
    this.recipeService.toggleSaved(id);
  }
}
