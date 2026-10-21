import { formatCurrency, formatDate, formatNumber, formatPercent } from '@angular/common';
import { Component, computed, input } from '@angular/core';
import type { EChartsCoreOption } from 'echarts/core';
import { NgxEchartsDirective } from 'ngx-echarts';
import { Granularita, PuntoKpi, ValoriKpi } from '../../modelli/kpi';
import { etichettaPeriodo, Formato, formatta } from '../../servizi/formati';

/** Una linea (o una serie di barre) del grafico: quale KPI e con che nome in legenda. */
export interface Grandezza {
  chiave: keyof ValoriKpi;
  nome: string;
}

export interface Grafico {
  titolo: string;
  grandezze: Grandezza[];
  formato: Formato;
  unita?: string;
  /** Le barre si usano per le quantità che si sommano nel periodo (costi, emissioni), le linee per i rapporti. */
  tipo?: 'line' | 'bar';
}

/** Etichetta dell'asse orizzontale, più corta di quella della tabella: "12/10" (giorno o inizio settimana), "ott 2026". */
function etichettaAsse(punto: PuntoKpi, granularita: Granularita): string {
  return formatDate(punto.da, granularita === 'mese' ? 'MMM yyyy' : 'dd/MM', 'it-IT');
}

/** Valori dell'asse verticale, senza decimali superflui (72% invece di 72,0%, ma 3,5% resta 3,5%). */
function valoreAsse(valore: number, formato: Formato): string {
  switch (formato) {
    case 'percentuale':
      return formatPercent(valore, 'it-IT', '1.0-1');
    case 'euro':
      return formatCurrency(valore, 'it-IT', '€', 'EUR', '1.0-0');
    default:
      return formatNumber(valore, 'it-IT', '1.0-3');
  }
}

/** Costruisce le opzioni di ECharts per l'andamento di uno o più KPI nella serie dei periodi. */
export function opzioniAndamento(grafico: Grafico, serie: PuntoKpi[], granularita: Granularita): EChartsCoreOption {
  const tipo = grafico.tipo ?? 'line';
  const unita = grafico.unita ? ` ${grafico.unita}` : '';
  return {
    grid: { left: 8, right: 16, top: grafico.grandezze.length > 1 ? 40 : 16, bottom: 8, containLabel: true },
    legend: grafico.grandezze.length > 1 ? { top: 0 } : undefined,
    tooltip: {
      trigger: 'axis',
      // Intestazione con il periodo completo; i periodi incompleti sono segnalati come nella tabella.
      formatter: (punti: { dataIndex: number; marker: string; seriesName: string; value: number | null }[]) => {
        const punto = serie[punti[0].dataIndex];
        const intestazione = etichettaPeriodo(punto, granularita) + (punto.parziale ? ' (parziale)' : '');
        const righe = punti.map((p) => `${p.marker} ${p.seriesName}: <b>${formatta(p.value, grafico.formato)}${unita}</b>`);
        return [intestazione, ...righe].join('<br>');
      },
    },
    xAxis: { type: 'category', data: serie.map((p) => etichettaAsse(p, granularita)) },
    // Per i rapporti l'asse parte vicino ai valori, così si vedono le variazioni; le barre partono sempre da zero.
    yAxis: { type: 'value', scale: tipo === 'line', axisLabel: { formatter: (v: number) => valoreAsse(v, grafico.formato) } },
    series: grafico.grandezze.map((g) => ({
      name: g.nome,
      type: tipo,
      // null (KPI non calcolabile) lascia un buco nella linea invece di un valore inventato. I periodi parziali
      // (ad esempio il giorno in corso) sono sbiaditi: un totale ancora incompleto non va letto come un calo.
      data: serie.map((p) => {
        const valore = p.kpi[g.chiave] as number | null;
        return p.parziale ? { value: valore, itemStyle: { opacity: 0.4 } } : valore;
      }),
      showSymbol: serie.length <= 31,
    })),
  };
}

@Component({
  selector: 'app-grafico-andamento',
  imports: [NgxEchartsDirective],
  template: `
    <h3>{{ grafico().titolo }}</h3>
    <div echarts class="area" [options]="opzioni()"></div>
  `,
  styles: `
    :host {
      display: block;
    }
    h3 {
      font: var(--mat-sys-title-small);
      margin: 0 0 8px;
    }
    .area {
      height: 260px;
    }
  `,
})
export class GraficoAndamento {
  readonly grafico = input.required<Grafico>();
  readonly serie = input.required<PuntoKpi[]>();
  readonly granularita = input.required<Granularita>();

  protected readonly opzioni = computed(() => opzioniAndamento(this.grafico(), this.serie(), this.granularita()));
}
