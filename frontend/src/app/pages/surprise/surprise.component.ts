import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';
import { RecipeCardComponent } from '../../shared/recipe-card/recipe-card.component';
import { RecipeService, SurpriseQuery } from '../../services/recipe.service';
import { Difficulty, MOODS, PlaceFilter, REGIONS, Recipe } from '../../models/recipe.model';

@Component({
  selector: 'app-surprise',
  standalone: true,
  imports: [RouterLink, RecipeCardComponent],
  templateUrl: './surprise.component.html',
  styleUrl: './surprise.component.scss',
})
export class SurpriseComponent {
  moods = MOODS.map(m => m.label);
  selectedMoods = signal<string[]>(['Algo rápido']);

  difficulties: { value: Difficulty; label: string }[] = [
    { value: 'facil', label: 'Sencillo' },
    { value: 'intermedio', label: 'Intermedio' },
    { value: 'reto', label: 'Me reto hoy' },
  ];
  selectedDifficulty = signal<Difficulty>('facil');

  regions = REGIONS;
  selectedPlace = signal<PlaceFilter>('any');

  maxMinutes = signal(30);

  loading = signal(false);
  error = signal<string | null>(null);

  private suggestions = signal<Recipe[]>([]);
  /** Se recalcula solo si el usuario oculta una receta, cambia sus alergias o marca favoritas. */
  visibleSuggestions = computed(() =>
    this.recipeService.filterForUser(this.suggestions()).map(r => this.recipeService.decorate(r))
  );

  private destroyRef = inject(DestroyRef);
  private request?: Subscription;
  /** Para que "Mostrar ideas nuevas" con los mismos controles no repita las mismas recetas. */
  private lastQueryKey = '';
  private shownIds = new Set<string>();

  constructor(public recipeService: RecipeService) {
    this.destroyRef.onDestroy(() => this.request?.unsubscribe());
    this.showIdeas(); // primera carga con los valores por default
  }

  toggleMood(m: string): void {
    this.selectedMoods.update(list => (list.includes(m) ? list.filter(x => x !== m) : [...list, m]));
  }

  setDifficulty(d: Difficulty): void {
    this.selectedDifficulty.set(d);
  }

  setPlace(value: string): void {
    this.selectedPlace.set(value);
  }

  incMinutes(): void {
    this.maxMinutes.update(v => Math.min(v + 5, 120));
  }

  decMinutes(): void {
    this.maxMinutes.update(v => Math.max(v - 5, 5));
  }

  /** Estado actual de los controles, listo para el backend (POST /recommendations). */
  private currentQuery(): SurpriseQuery {
    const slugByLabel = new Map(MOODS.map(m => [m.label, m.value]));
    return {
      moods: this.selectedMoods()
        .map(label => slugByLabel.get(label))
        .filter((v): v is string => !!v),
      difficulty: this.selectedDifficulty(),
      maxMinutes: this.maxMinutes(),
      place: this.selectedPlace(),
    };
  }

  /**
   * Pide ideas al recomendador real. Con los mismos controles que la vez
   * anterior se excluyen las recetas ya mostradas, para que "Mostrar ideas
   * nuevas" realmente traiga ideas nuevas; si cambian los controles, se empieza de cero.
   */
  showIdeas(): void {
    const query = this.currentQuery();
    const key = JSON.stringify(query);
    if (key !== this.lastQueryKey) this.shownIds.clear();
    this.lastQueryKey = key;
    this.fetch(query, [...this.shownIds], true);
  }

  private fetch(query: SurpriseQuery, exclude: string[], allowRetry: boolean): void {
    this.request?.unsubscribe();
    this.loading.set(true);
    this.error.set(null);

    this.request = this.recipeService.getSurpriseSuggestions({ ...query, extraExcludeIds: exclude }).subscribe({
      next: list => {
        if (!list.length && exclude.length && allowRetry) {
          // Ya se mostró todo lo que cumple: vuelve a empezar con los mismos filtros.
          this.shownIds.clear();
          this.fetch(query, [], false);
          return;
        }
        list.forEach(r => this.shownIds.add(r.id));
        this.suggestions.set(list);
        this.loading.set(false);
      },
      error: () => {
        this.suggestions.set([]);
        this.error.set('No pudimos obtener ideas del servidor. Revisa que el backend esté en marcha e inténtalo de nuevo.');
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
