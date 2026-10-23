import { httpResource } from '@angular/common/http';
import { effect, Injectable, signal } from '@angular/core';
import { Alert, CausaleRipartita, Granularita, Macchina, RispostaKpi } from '../modelli/kpi';
import { dataIso } from './formati';

export interface FiltriKpi {
  da: Date;
  a: Date;
  granularita: Granularita;
  /** 'linea' oppure il codice di una macchina. */
  ambito: string;
}

/** Ogni quanto si rileggono i KPI quando il periodo comprende oggi. */
export const AGGIORNAMENTO_MS = 10_000;

function ultimiGiorni(n: number, oggi = new Date()): Pick<FiltriKpi, 'da' | 'a'> {
  const da = new Date(oggi.getFullYear(), oggi.getMonth(), oggi.getDate() - (n - 1));
  return { da, a: new Date(oggi.getFullYear(), oggi.getMonth(), oggi.getDate()) };
}

/**
 * Stato dei KPI condiviso dalle pagine: i filtri sono un signal e la risposta dell'API si ricarica da sola a ogni
 * loro modifica (httpResource annulla la richiesta precedente se non è ancora arrivata). Se il periodo comprende
 * oggi i dati cambiano mentre il generatore lavora, quindi si rileggono anche ogni 10 secondi.
 */
@Injectable({ providedIn: 'root' })
export class KpiService {
  readonly filtri = signal<FiltriKpi>({ ...ultimiGiorni(30), granularita: 'giorno', ambito: 'linea' });

  readonly kpi = httpResource<RispostaKpi>(() => {
    const f = this.filtri();
    return {
      url: '/api/kpi',
      params: { da: dataIso(f.da), a: dataIso(f.a), granularita: f.granularita, ambito: f.ambito },
    };
  });

  readonly ripartizioneFermi = httpResource<CausaleRipartita[]>(() => {
    const f = this.filtri();
    return { url: '/api/fermi/ripartizione', params: { da: dataIso(f.da), a: dataIso(f.a), ambito: f.ambito } };
  });

  /** Superamenti di soglia del periodo: per la linea anche quelli delle singole macchine. */
  readonly alert = httpResource<Alert[]>(() => {
    const f = this.filtri();
    const params: Record<string, string> = { da: dataIso(f.da), a: dataIso(f.a), tipo: 'soglia' };
    if (f.ambito !== 'linea') params['macchina'] = f.ambito;
    return { url: '/api/anomalie', params };
  });

  readonly macchine = httpResource<Macchina[]>(() => '/api/macchine', { defaultValue: [] });

  /** Ora in cui sono arrivati gli ultimi KPI. */
  readonly aggiornatoAlle = signal<Date | null>(null);

  /** Vero se il periodo selezionato comprende la data odierna. */
  comprendeOggi(): boolean {
    const { da, a } = this.filtri();
    const oggi = dataIso(new Date());
    return dataIso(da) <= oggi && oggi <= dataIso(a);
  }

  constructor() {
    effect((alTermine) => {
      if (!this.comprendeOggi()) return;
      const timer = setInterval(() => {
        this.kpi.reload();
        this.ripartizioneFermi.reload();
        this.alert.reload();
      }, AGGIORNAMENTO_MS);
      alTermine(() => clearInterval(timer));
    });
    // Ogni risposta arrivata, anche se uguale alla precedente, è un nuovo oggetto: l'effetto riparte e segna l'ora.
    effect(() => {
      if (this.kpi.hasValue()) {
        this.kpi.value();
        this.aggiornatoAlle.set(new Date());
      }
    });
  }

  aggiorna(modifiche: Partial<FiltriKpi>): void {
    this.filtri.update((f) => ({ ...f, ...modifiche }));
  }
}
