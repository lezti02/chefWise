import { Injectable, signal } from '@angular/core';

export interface ChatMessage {
  role: 'user' | 'bot';
  text: string;
}

@Injectable({ providedIn: 'root' })
export class ChatService {
  private readonly _messages = signal<ChatMessage[]>([
    { role: 'bot', text: 'Puedes preguntarme en cualquier momento: sustituciones, tiempos de cocción, conversión de unidades, o si algo ya está listo.' },
  ]);
  readonly messages = this._messages.asReadonly();

  /**
   * MOCK — agrega la pregunta del usuario y responde con un texto fijo después
   * de un pequeño delay (simulando latencia de red).
   *
   * INTEGRACIÓN CON BACKEND / AGENTE:
   * Aquí es donde conectas tu agente conversacional (el que decide qué "tool"
   * llamar: sustituciones, conversión de unidades, explicar una técnica, etc.
   * — justo el concepto de agentes que viste en el diplomado).
   *
   * Reemplaza el bloque marcado "MOCK" por algo como:
   *
   *   this.http.post<{ reply: string }>('/api/chat', {
   *     message: text,
   *     history: this._messages(),
   *     recipeId: currentRecipeId, // opcional: si el usuario venía viendo una receta
   *   }).subscribe(res => {
   *     this._messages.update(list => [...list, { role: 'bot', text: res.reply }]);
   *   });
   *
   * Si tu backend responde en streaming (recomendado para agentes, así el
   * usuario ve la respuesta llegar palabra por palabra), considera usar
   * Server-Sent Events o un WebSocket en vez de un POST normal.
   */
  ask(text: string): void {
    if (!text.trim()) return;
    this._messages.update(list => [...list, { role: 'user', text }]);

    // ---- INICIO MOCK: borrar este bloque al conectar el backend ----
    setTimeout(() => {
      this._messages.update(list => [...list, {
        role: 'bot',
        text: 'Esto es solo un prototipo de interfaz — aquí se mostraría la respuesta del asistente conectado al backend.',
      }]);
    }, 300);
    // ---- FIN MOCK ----
  }
}
