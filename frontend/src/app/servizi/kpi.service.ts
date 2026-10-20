import { httpResource } from '@angular/common/http';
import { Injectable, signal } from '@angular/core';
import { Granularita, Macchina, RispostaKpi } from '../modelli/kpi';
import { dataIso } from './formati';

export interface FiltriKpi {
  da: Date;
  a: Date;
  granularita: Granularita;
  /** 'linea' oppure il codice di una macchina. */
  ambito: string;
}

function ultimiGiorni(n: number, oggi = new Date()): Pick<FiltriKpi, 'da' | 'a'> {
  const da = new Date(oggi.getFullYear(), oggi.getMonth(), oggi.getDate() - (n - 1));
  return { da, a: new Date(oggi.getFullYear(), oggi.getMonth(), oggi.getDate()) };
}

/**
 * Stato dei KPI condiviso dalle pagine: i filtri sono un signal e la risposta dell'API si ricarica da sola a ogni
 * loro modifica (httpResource annulla la richiesta precedente se non è ancora arrivata).
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

  readonly macchine = httpResource<Macchina[]>(() => '/api/macchine', { defaultValue: [] });

  aggiorna(modifiche: Partial<FiltriKpi>): void {
    this.filtri.update((f) => ({ ...f, ...modifiche }));
  }
}
