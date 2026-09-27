import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ChatService } from '../../services/chat.service';

/**
 * Chatbot flotante GLOBAL. Se monta una sola vez en app.component.html (no
 * dentro de cada página), por eso aparece en cualquier vista, no solo dentro
 * de una receta. Al mandar la primera pregunta, el panel se expande para
 * poder seguir la conversación cómodamente.
 */
@Component({
  selector: 'app-chat-widget',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './chat-widget.component.html',
  styleUrl: './chat-widget.component.scss',
})
export class ChatWidgetComponent {
  open = signal(false);
  expanded = signal(false);
  draft = '';

  constructor(public chat: ChatService) {}

  toggleOpen(): void {
    this.open.update(v => !v);
  }

  close(): void {
    this.open.set(false);
    this.expanded.set(false);
  }

  send(): void {
    if (!this.draft.trim()) return;
    this.expanded.set(true);
    this.chat.ask(this.draft);
    this.draft = '';
  }
}
