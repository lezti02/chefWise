import { Component, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { RecipeCardComponent } from '../../shared/recipe-card/recipe-card.component';
import { RecipeService } from '../../services/recipe.service';
import { Difficulty, Recipe } from '../../models/recipe.model';

@Component({
  selector: 'app-surprise',
  standalone: true,
  imports: [RouterLink, RecipeCardComponent],
  templateUrl: './surprise.component.html',
  styleUrl: './surprise.component.scss',
})
export class SurpriseComponent {
  moods = ['Algo rápido', 'Saludable', 'Reconfortante', 'Dulce', 'Picante', 'Ligero'];
  selectedMoods = signal<string[]>(['Algo rápido']);

  difficulties: { value: Difficulty; label: string }[] = [
    { value: 'facil', label: 'Sencillo' },
    { value: 'intermedio', label: 'Intermedio' },
    { value: 'reto', label: 'Me reto hoy' },
  ];
  selectedDifficulty = signal<Difficulty>('facil');

  maxMinutes = signal(30);
  suggestions = signal<Recipe[]>([]);

  constructor(private recipeService: RecipeService) {
    this.showIdeas(); // primera carga con los valores por default
  }

  toggleMood(m: string): void {
    this.selectedMoods.update(list => (list.includes(m) ? list.filter(x => x !== m) : [...list, m]));
  }

  setDifficulty(d: Difficulty): void {
    this.selectedDifficulty.set(d);
  }

  incMinutes(): void {
    this.maxMinutes.update(v => Math.min(v + 5, 120));
  }

  decMinutes(): void {
    this.maxMinutes.update(v => Math.max(v - 5, 5));
  }

  /**
   * Pide nuevas ideas al recomendador. Hoy es un mock (ver el comentario
   * completo en RecipeService.getSurpriseSuggestions) — cuando lo conectes a
   * tu API, esta función seguramente se vuelva async y necesites un signal
   * de "cargando" mientras esperas la respuesta del modelo.
   */
  showIdeas(): void {
    this.suggestions.set(
      this.recipeService.getSurpriseSuggestions(this.selectedMoods(), this.selectedDifficulty(), this.maxMinutes())
    );
  }

  onToggleFavorite(id: string): void {
    this.recipeService.toggleFavorite(id);
  }

  onToggleSaved(id: string): void {
    this.recipeService.toggleSaved(id);
  }
}
