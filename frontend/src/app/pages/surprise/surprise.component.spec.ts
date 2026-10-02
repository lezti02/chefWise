import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, TestRequest, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideZonelessChangeDetection } from '@angular/core';
import { provideRouter } from '@angular/router';
import { SurpriseComponent } from './surprise.component';
import { itemDto, recommendationsResponse } from '../../testing/api-fixtures';

describe('SurpriseComponent (consume la API real)', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [provideZonelessChangeDetection(), provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  const nextRequest = (): TestRequest => http.expectOne(r => r.url.endsWith('/recommendations'));

  async function render() {
    const fixture = TestBed.createComponent(SurpriseComponent);
    const el = fixture.nativeElement as HTMLElement;
    return { fixture, el };
  }

  it('pide recomendaciones al backend con los controles por defecto y pinta tarjetas reales', async () => {
    const { fixture, el } = await render();

    const req = nextRequest();
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({
      antojos: ['rapido'],
      difficulty: 'facil',
      max_time: 30,
      countries: [],
      exclude_ids: [],
      top_n: 12,
    });
    req.flush(recommendationsResponse([itemDto(101, { name: 'Pasta rápida' }), itemDto(102, { name: 'Sopa de fideo' })]));
    await fixture.whenStable();
    fixture.detectChanges();

    const cards = Array.from(el.querySelectorAll('a.rcard'));
    expect(cards.length).toBe(2);
    expect(cards.map(c => c.querySelector('.name')?.textContent?.trim())).toEqual(['Pasta rápida', 'Sopa de fideo']);
    // Click en la tarjeta => /receta/<recipe_id real>
    expect(cards[0].getAttribute('href')).toBe('/receta/101');
  });

  it('"Mostrar ideas nuevas" manda el estado actual de los controles', async () => {
    const { fixture, el } = await render();
    nextRequest().flush(recommendationsResponse([itemDto(1)]));
    await fixture.whenStable();
    fixture.detectChanges();

    const chip = (text: string) =>
      Array.from(el.querySelectorAll<HTMLElement>('.chip')).find(c => c.textContent?.trim() === text)!;
    chip('Picante').click();
    chip('Intermedio').click();
    const buttons = Array.from(el.querySelectorAll<HTMLButtonElement>('.stepper button'));
    buttons[1].click(); // +  => 35 min
    fixture.detectChanges();

    el.querySelector<HTMLButtonElement>('button.btn-primary')!.click();

    const req = nextRequest();
    expect(req.request.body).toMatchObject({
      antojos: ['rapido', 'picante'],
      difficulty: 'intermedio',
      max_time: 35,
    });
    req.flush(recommendationsResponse([itemDto(7, { name: 'Chilaquiles' })]));
    await fixture.whenStable();
    fixture.detectChanges();
    expect(el.querySelector('a.rcard .name')?.textContent?.trim()).toBe('Chilaquiles');
  });

  it('con los mismos controles, "ideas nuevas" excluye lo ya mostrado', async () => {
    const { fixture, el } = await render();
    nextRequest().flush(recommendationsResponse([itemDto(1), itemDto(2)]));
    await fixture.whenStable();
    fixture.detectChanges();

    el.querySelector<HTMLButtonElement>('button.btn-primary')!.click();
    const req = nextRequest();
    expect(req.request.body.exclude_ids.sort()).toEqual([1, 2]);
    req.flush(recommendationsResponse([itemDto(3)]));
  });

  it('muestra un mensaje claro si el backend no responde', async () => {
    const { fixture, el } = await render();
    nextRequest().flush('boom', { status: 500, statusText: 'Server Error' });
    await fixture.whenStable();
    fixture.detectChanges();

    expect(el.querySelectorAll('a.rcard').length).toBe(0);
    expect(el.querySelector('[role="alert"]')?.textContent).toContain('backend');
  });
});
