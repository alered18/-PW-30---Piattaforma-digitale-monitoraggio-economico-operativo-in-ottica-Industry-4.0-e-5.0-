import { DatePipe } from '@angular/common';
import { httpResource } from '@angular/common/http';
import { Component, computed, DestroyRef, inject } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MacchinaOperatore, StatoOperatore } from '../../modelli/operatore';
import { formatta } from '../../servizi/formati';
import { AGGIORNAMENTO_MS } from '../../servizi/kpi.service';

/** Icona e testo di ogni stato: lo stato si legge anche senza distinguere i colori. */
const STATI = {
  in_funzione: { icona: 'check_circle', testo: 'In funzione' },
  ferma: { icona: 'error', testo: 'Ferma' },
  senza_dati: { icona: 'help', testo: 'Nessun dato recente' },
} as const;

/**
 * Vista per l'operatore di linea: stato delle macchine, avanzamento del turno e alert del giorno, senza filtri né
 * grafici storici. Si aggiorna da sola ogni 10 secondi.
 */
@Component({
  selector: 'app-operatore',
  imports: [DatePipe, MatCardModule, MatIconModule, MatProgressBarModule],
  templateUrl: './operatore.html',
  styleUrl: './operatore.scss',
})
export class Operatore {
  protected readonly risorsa = httpResource<StatoOperatore>(() => '/api/operatore/stato');
  // Durante un rinnovo resta visibile lo stato precedente; dopo un errore la pagina mostra solo il messaggio.
  protected readonly stato = computed(() => (this.risorsa.hasValue() ? this.risorsa.value() : null));
  protected readonly formatta = formatta;

  constructor() {
    const timer = setInterval(() => this.risorsa.reload(), AGGIORNAMENTO_MS);
    inject(DestroyRef).onDestroy(() => clearInterval(timer));
  }

  protected icona(m: MacchinaOperatore): string {
    return STATI[m.stato].icona;
  }

  /** "In funzione", "Ferma: Guasto", "Nessun dato recente". */
  protected testo(m: MacchinaOperatore): string {
    const testo = STATI[m.stato].testo;
    return m.stato === 'ferma' && m.descrizione_causale ? `${testo}: ${m.descrizione_causale}` : testo;
  }
}
