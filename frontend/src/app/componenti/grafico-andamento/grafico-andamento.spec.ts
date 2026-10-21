import { registerLocaleData } from '@angular/common';
import localeIt from '@angular/common/locales/it';
import { PuntoKpi, ValoriKpi } from '../../modelli/kpi';
import { Grafico, opzioniAndamento } from './grafico-andamento';

registerLocaleData(localeIt);

function punto(da: string, oee: number | null, disponibilita: number, parziale = false): PuntoKpi {
  return { periodo: da, da, a: da, parziale, kpi: { oee, disponibilita } as ValoriKpi };
}

describe('opzioniAndamento', () => {
  const grafico: Grafico = {
    titolo: 'OEE e componenti',
    formato: 'percentuale',
    grandezze: [{ chiave: 'oee', nome: 'OEE' }, { chiave: 'disponibilita', nome: 'Disponibilità' }],
  };
  const serie = [punto('2026-10-15', 0.71, 0.86), punto('2026-10-16', null, 0.9, true)];

  it('mette una linea per KPI e un periodo per punto, con buchi per i KPI non calcolabili e periodi parziali sbiaditi', () => {
    const opzioni = opzioniAndamento(grafico, serie, 'giorno') as any;

    expect(opzioni.xAxis.data).toEqual(['15/10', '16/10']);
    expect(opzioni.series.map((s: any) => [s.name, s.type, s.data])).toEqual([
      ['OEE', 'line', [0.71, { value: null, itemStyle: { opacity: 0.4 } }]],
      ['Disponibilità', 'line', [0.86, { value: 0.9, itemStyle: { opacity: 0.4 } }]],
    ]);
    expect(opzioni.yAxis.axisLabel.formatter(0.7)).toBe('70%');
    expect(opzioni.yAxis.axisLabel.formatter(0.035)).toBe('3,5%');

    const tooltip = opzioni.tooltip.formatter([
      { dataIndex: 1, marker: '', seriesName: 'OEE', value: null },
      { dataIndex: 1, marker: '', seriesName: 'Disponibilità', value: 0.9 },
    ]);
    expect(tooltip).toBe('ven 16/10/2026 (parziale)<br> OEE: <b>n.d.</b><br> Disponibilità: <b>90,0%</b>');
  });
});
