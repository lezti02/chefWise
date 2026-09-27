import { Component, computed, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { RecipeCardComponent } from '../../shared/recipe-card/recipe-card.component';
import { RecipeRowComponent } from '../../shared/recipe-row/recipe-row.component';
import { RecipeService } from '../../services/recipe.service';

type SubTab = 'resumen' | 'historial' | 'favoritas' | 'quiero';

/**
 * "Mi cocina": historial, favoritas, guardadas para después y estadísticas,
 * todo en un mismo lugar con pestañas internas. La pestaña "Favoritas" de
 * aquí reemplaza lo que antes era un ítem aparte en el menú principal.
 */
@Component({
  selector: 'app-my-kitchen',
  standalone: true,
  imports: [DatePipe, RecipeCardComponent, RecipeRowComponent],
  templateUrl: './my-kitchen.component.html',
  styleUrl: './my-kitchen.component.scss',
})
export class MyKitchenComponent {
  activeSub = signal<SubTab>('resumen');

  constructor(public recipeService: RecipeService) {}

  setSub(tab: SubTab): void {
    this.activeSub.set(tab);
  }

  // Los tres primeros números son de ejemplo; en producción calcula esto en
  // el backend (agregaciones sobre el historial real del usuario), no en el
  // cliente con lo que se alcanzó a cargar.
  cookedThisMonth = computed(() => this.recipeService.history().length);
  newFavorites = computed(() => this.recipeService.favorites().length);
  savedCount = computed(() => this.recipeService.saved().length);
  streakDays = signal(4); // ejemplo estático — ver nota arriba

  labelFor(category: string): string {
    const map: Record<string, string> = {
      desayuno: 'Desayuno', comida: 'Comida', cena: 'Cena', postre: 'Postre', bebida: 'Bebidas',
    };
    return map[category] ?? category;
  }

  onToggleFavorite(id: string): void {
    this.recipeService.toggleFavorite(id);
  }

  onToggleSaved(id: string): void {
    this.recipeService.toggleSaved(id);
  }
}
