import { registerLocaleData } from '@angular/common';
import localeIt from '@angular/common/locales/it';
import { CausaleRipartita } from '../../modelli/kpi';
import { opzioniPareto } from './grafico-pareto';

registerLocaleData(localeIt);

function causale(descrizione: string, ore: number, costo: number, pianificato = false): CausaleRipartita {
  return { causale: descrizione, descrizione_causale: descrizione, pianificato, n_fermi: 1, durata_s: ore * 3600,
    costo_eur: costo };
}

describe('opzioniPareto', () => {
  const causali = [causale('Guasto', 1, 900), causale('Manutenzione', 2, 0, true), causale('Mancanza materiale', 1, 300)];

  it('ordina le causali dalla più grande e aggiunge la percentuale cumulata', () => {
    const perDurata = opzioniPareto(causali, 'durata') as any;
    expect(perDurata.xAxis.data).toEqual(['Manutenzione', 'Guasto', 'Mancanza materiale']);
    expect(perDurata.series[0].data).toEqual([2, 1, 1]);
    expect(perDurata.series[1].data).toEqual([0.5, 0.75, 1]);

    // Per costo la manutenzione programmata, che non costa, non compare.
    const perCosto = opzioniPareto(causali, 'costo') as any;
    expect(perCosto.xAxis.data).toEqual(['Guasto', 'Mancanza materiale']);
    expect(perCosto.series[1].data).toEqual([0.75, 1]);
  });
});
