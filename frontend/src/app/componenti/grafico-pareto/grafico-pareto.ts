import { formatNumber } from '@angular/common';
import { Component, computed, input, signal } from '@angular/core';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import type { EChartsCoreOption } from 'echarts/core';
import { NgxEchartsDirective } from 'ngx-echarts';
import { CausaleRipartita } from '../../modelli/kpi';
import { formatta } from '../../servizi/formati';

export type Misura = 'durata' | 'costo';

const ore = (secondi: number) => secondi / 3600;

/**
 * Opzioni del diagramma di Pareto: una barra per causale, dalla più grande, e la linea della percentuale cumulata
 * (asse di destra) che mostra quante causali bastano a spiegare la maggior parte dei fermi. Per il costo si escludono
 * le causali senza costo (la manutenzione programmata).
 */
export function opzioniPareto(causali: CausaleRipartita[], misura: Misura): EChartsCoreOption {
  const valore = (c: CausaleRipartita) => (misura === 'durata' ? ore(c.durata_s) : c.costo_eur);
  const ordinate = causali.filter((c) => valore(c) > 0).sort((x, y) => valore(y) - valore(x));
  const totale = ordinate.reduce((somma, c) => somma + valore(c), 0);
  let cumulata = 0;
  const percentuali = ordinate.map((c) => (cumulata += valore(c)) / totale);
  const formato = (v: number) => (misura === 'durata' ? `${formatNumber(v, 'it-IT', '1.1-1')} h` : formatta(v, 'euro'));

  return {
    grid: { left: 8, right: 8, top: 40, bottom: 8, containLabel: true },
    legend: { top: 0 },
    tooltip: {
      trigger: 'axis',
      formatter: (punti: { dataIndex: number }[]) => {
        const i = punti[0].dataIndex;
        const c = ordinate[i];
        return `${c.descrizione_causale}<br>${c.n_fermi} fermi · <b>${formato(valore(c))}</b><br>` +
          `cumulata: ${formatta(percentuali[i], 'percentuale')}`;
      },
    },
    xAxis: { type: 'category', data: ordinate.map((c) => c.descrizione_causale), axisLabel: { interval: 0, width: 110, overflow: 'break' } },
    yAxis: [
      { type: 'value', axisLabel: { formatter: (v: number) => (misura === 'durata' ? `${v} h` : formatta(v, 'euro')) } },
      { type: 'value', min: 0, max: 1, splitLine: { show: false }, axisLabel: { formatter: (v: number) => `${Math.round(v * 100)}%` } },
    ],
    series: [
      { name: misura === 'durata' ? 'Durata' : 'Costo', type: 'bar', data: ordinate.map(valore) },
      { name: 'Cumulata', type: 'line', yAxisIndex: 1, data: percentuali },
    ],
  };
}

@Component({
  selector: 'app-grafico-pareto',
  imports: [MatButtonToggleModule, NgxEchartsDirective],
  template: `
    <div class="intestazione">
      <h3>Fermi per causale</h3>
      <mat-button-toggle-group hideSingleSelectionIndicator [value]="misura()" (change)="misura.set($event.value)"
        aria-label="Misura del Pareto">
        <mat-button-toggle value="durata">Durata</mat-button-toggle>
        <mat-button-toggle value="costo">Costo</mat-button-toggle>
      </mat-button-toggle-group>
    </div>
    @if (errore()) {
      <p class="vuoto errore">Impossibile caricare i fermi.</p>
    } @else if (vuoto()) {
      <p class="vuoto">{{ misura() === 'durata' ? 'Nessun fermo nel periodo.' : 'Nessun fermo con costo nel periodo.' }}</p>
    } @else {
      <div echarts class="area" [options]="opzioni()"></div>
    }
  `,
  styles: `
    :host {
      display: block;
    }
    .intestazione {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 8px;
    }
    h3 {
      font: var(--mat-sys-title-small);
      margin: 0;
    }
    .area {
      height: 260px;
    }
    .vuoto {
      color: var(--mat-sys-on-surface-variant);
    }
    .errore {
      color: var(--mat-sys-error);
    }
  `,
})
export class GraficoPareto {
  readonly causali = input.required<CausaleRipartita[]>();
  readonly errore = input(false);
  protected readonly misura = signal<Misura>('durata');

  // Per costo possono esserci solo fermi senza costo (manutenzione programmata): anche allora non c'è nulla da disegnare.
  protected readonly vuoto = computed(() =>
    this.causali().every((c) => (this.misura() === 'durata' ? c.durata_s : c.costo_eur) <= 0),
  );

  protected readonly opzioni = computed(() => opzioniPareto(this.causali(), this.misura()));
}
