import { Component, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { ChatWidgetComponent } from './shared/chat-widget/chat-widget.component';
import { RecipeService } from './services/recipe.service';

/**
 * Shell de la aplicación: sidebar (desktop) + bottom-nav (mobile) + el
 * <router-outlet> donde se pintan las páginas + el chatbot flotante, que
 * vive aquí (no dentro de cada página) precisamente para que esté disponible
 * en todas las vistas al mismo tiempo.
 */
@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, ChatWidgetComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
})
export class AppComponent {
  recipeService = inject(RecipeService);
}
