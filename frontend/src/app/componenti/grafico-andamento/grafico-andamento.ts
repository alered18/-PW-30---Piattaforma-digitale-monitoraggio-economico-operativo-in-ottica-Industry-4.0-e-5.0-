import { formatCurrency, formatDate, formatNumber, formatPercent } from '@angular/common';
import { Component, computed, input } from '@angular/core';
import type { EChartsCoreOption } from 'echarts/core';
import { NgxEchartsDirective } from 'ngx-echarts';
import { Granularita, PuntoKpi, SogliaKpi, ValoriKpi } from '../../modelli/kpi';
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

/** Colore delle soglie, lo stesso delle card fuori soglia (colore di errore del tema). */
const COLORE_SOGLIA = '#ba1a1a';

/**
 * KPI che sono somme di un giorno (€/giorno): la loro soglia non vale per una settimana o un mese. Stesso elenco
 * del back-end, che per questi KPI non restituisce lo stato della soglia nei periodi più lunghi di un giorno.
 */
const KPI_GIORNALIERI: (keyof ValoriKpi)[] = ['costo_fermi_eur'];

/**
 * Soglie da disegnare: quelle dei KPI del grafico, tranne le soglie giornaliere se i periodi sono settimane o mesi.
 * La soglia è una serie tratteggiata a valore costante, così compare in legenda e nel tooltip ed è compresa nella
 * scala dell'asse anche quando tutti i valori sono lontani da essa.
 */
function serieSoglie(grafico: Grafico, serie: PuntoKpi[], granularita: Granularita, soglie: SogliaKpi[]) {
  const chiavi = grafico.grandezze.map((g) => g.chiave);
  return soglie
    .filter((s) => chiavi.includes(s.kpi) && (granularita === 'giorno' || !KPI_GIORNALIERI.includes(s.kpi)))
    .map((s) => ({
      name: grafico.grandezze.length > 1
        ? `Soglia ${grafico.grandezze.find((g) => g.chiave === s.kpi)!.nome}`
        : s.verso === 'min' ? 'Soglia minima' : 'Soglia massima',
      type: 'line',
      data: serie.map(() => s.valore),
      symbol: 'none',
      lineStyle: { type: 'dashed', width: 1.5 },
      color: COLORE_SOGLIA,
      z: 3,
    }));
}

/** Costruisce le opzioni di ECharts per l'andamento di uno o più KPI nella serie dei periodi, con le loro soglie. */
export function opzioniAndamento(
  grafico: Grafico,
  serie: PuntoKpi[],
  granularita: Granularita,
  soglie: SogliaKpi[] = [],
): EChartsCoreOption {
  const tipo = grafico.tipo ?? 'line';
  const unita = grafico.unita ? ` ${grafico.unita}` : '';
  const linee = serieSoglie(grafico, serie, granularita, soglie);
  const legenda = grafico.grandezze.length + linee.length > 1;
  return {
    grid: { left: 8, right: 16, top: legenda ? 40 : 16, bottom: 8, containLabel: true },
    legend: legenda ? { top: 0 } : undefined,
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
    series: [...grafico.grandezze.map((g) => ({
      name: g.nome,
      type: tipo,
      // null (KPI non calcolabile) lascia un buco nella linea invece di un valore inventato. I periodi parziali
      // (ad esempio il giorno in corso) sono sbiaditi: un totale ancora incompleto non va letto come un calo.
      data: serie.map((p) => {
        const valore = p.kpi[g.chiave] as number | null;
        return p.parziale ? { value: valore, itemStyle: { opacity: 0.4 } } : valore;
      }),
      showSymbol: serie.length <= 31,
    })), ...linee],
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
  readonly soglie = input<SogliaKpi[]>([]);

  protected readonly opzioni = computed(() =>
    opzioniAndamento(this.grafico(), this.serie(), this.granularita(), this.soglie()),
  );
}
