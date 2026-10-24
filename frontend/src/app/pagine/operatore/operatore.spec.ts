import { registerLocaleData } from '@angular/common';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import localeIt from '@angular/common/locales/it';
import { LOCALE_ID } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { MacchinaOperatore, StatoOperatore } from '../../modelli/operatore';
import { Operatore } from './operatore';

registerLocaleData(localeIt);

function macchina(codice: string, nome: string, ferma?: [string, string]): MacchinaOperatore {
  return {
    codice, nome, stato: ferma ? 'ferma' : 'in_funzione', causale: ferma?.[0] ?? null,
    descrizione_causale: ferma?.[1] ?? null, ultima_rilevazione: '2026-10-12T15:30:00+02:00',
  };
}

describe('Operatore', () => {
  it('mostra lo stato delle 5 macchine, con la causale di quella ferma, e l\'avanzamento del turno', async () => {
    TestBed.configureTestingModule({
      imports: [Operatore],
      providers: [provideHttpClient(), provideHttpClientTesting(), { provide: LOCALE_ID, useValue: 'it-IT' }],
    });
    const fixture = TestBed.createComponent(Operatore);
    TestBed.tick();
    const stato: StatoOperatore = {
      aggiornato_il: '2026-10-12T15:30:05+02:00',
      turno: {
        inizio: '2026-10-12T14:00:00+02:00', fine: '2026-10-12T22:00:00+02:00', n_buoni: 2450, n_scarti: 62,
        tasso_scarto: 0.0247, obiettivo: 12000, avanzamento: 0.2042,
      },
      macchine: [
        macchina('M1', 'Impastatrice'), macchina('M2', 'Trafila'), macchina('M3', 'Essiccatoio', ['guasto', 'Guasto']),
        macchina('M4', 'Confezionatrice'), macchina('M5', 'Pallettizzatore'),
      ],
      alert: [],
    };
    TestBed.inject(HttpTestingController).expectOne('/api/operatore/stato').flush(stato);
    await fixture.whenStable();
    fixture.detectChanges();

    const pagina: HTMLElement = fixture.nativeElement;
    const schede = Array.from(pagina.querySelectorAll('.macchina'), (s) => ({
      classe: s.classList.contains('ferma'),
      testo: s.querySelector('.stato')?.textContent?.replace(/\s+/g, ' ').trim(),
    }));
    expect(schede.length).toBe(5);
    // La macchina ferma si distingue per colore, icona e testo con la causale.
    expect(schede[2]).toEqual({ classe: true, testo: 'error Ferma: Guasto' });
    expect(schede.filter((s) => s.testo === 'check_circle In funzione').length).toBe(4);

    const turno = pagina.querySelector('.turno')!.textContent!.replace(/\s+/g, ' ');
    expect(turno).toContain('Turno 14:00 – 22:00');
    expect(turno).toContain('2.450 confezioni buone su un obiettivo di 12.000 (20,4%)');
    expect(turno).toContain('Scarto del turno: 2,5% (62 confezioni)');
    expect(pagina.textContent).toContain('Nessun superamento di soglia oggi');
  });
});
