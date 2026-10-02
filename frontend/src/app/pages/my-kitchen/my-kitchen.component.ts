import { Component, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { RecipeCardComponent } from '../../shared/recipe-card/recipe-card.component';
import { RecipeRowComponent } from '../../shared/recipe-row/recipe-row.component';
import { RecipeService } from '../../services/recipe.service';
import { Recipe } from '../../models/recipe.model';

type SubTab = 'resumen' | 'historial' | 'favoritas' | 'quiero' | 'preferencias';
const SUB_TABS: SubTab[] = ['resumen', 'historial', 'favoritas', 'quiero', 'preferencias'];

/**
 * "Mi cocina": historial, favoritas, guardadas para después, estadísticas y
 * preferencias (alergias + recetas ocultas), todo en un mismo lugar con
 * pestañas internas. Acepta ?tab=<pestaña> para abrir una directamente.
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

  constructor(public recipeService: RecipeService) {
    const tab = inject(ActivatedRoute).snapshot.queryParamMap.get('tab') as SubTab | null;
    if (tab && SUB_TABS.includes(tab)) this.activeSub.set(tab);
  }

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

  hiddenMeta(r: Recipe): string {
    return [r.country, r.category ? this.labelFor(r.category) : null].filter(Boolean).join(' · ');
  }

  onToggleFavorite(id: string): void {
    this.recipeService.toggleFavorite(id);
  }

  onToggleSaved(id: string): void {
    this.recipeService.toggleSaved(id);
  }

  isPresetOn(id: string): boolean {
    return this.recipeService.allergies().presets.includes(id);
  }

  togglePreset(id: string): void {
    this.recipeService.togglePresetAllergy(id);
  }

  addCustomAllergy(input: HTMLInputElement): void {
    this.recipeService.addCustomAllergy(input.value);
    input.value = '';
  }

  removeCustomAllergy(term: string): void {
    this.recipeService.removeCustomAllergy(term);
  }

  unhide(id: string): void {
    this.recipeService.unhide(id);
  }
}
