import { DatePipe } from '@angular/common';
import { Component, computed, inject, linkedSignal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatCardModule } from '@angular/material/card';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import { MatTableModule } from '@angular/material/table';
import { Granularita, PuntoKpi, RispostaKpi, ValoriKpi } from '../../modelli/kpi';
import { dataBreve, etichettaPeriodo, Formato, formatta } from '../../servizi/formati';
import { KpiService } from '../../servizi/kpi.service';

interface Indicatore {
  chiave: keyof ValoriKpi;
  nome: string;
  unita: string;
  formato: Formato;
}

/** Card del cruscotto, raggruppate per tema. */
const GRUPPI: { titolo: string; indicatori: Indicatore[] }[] = [
  {
    titolo: 'Produzione',
    indicatori: [
      { chiave: 'n_buoni', nome: 'Confezioni buone', unita: 'conf', formato: 'intero' },
      { chiave: 'produzione_kg', nome: 'Produzione', unita: 'kg', formato: 'intero' },
      { chiave: 'produttivita_conf_h', nome: 'Produttività', unita: 'conf/h', formato: 'intero' },
    ],
  },
  {
    titolo: 'Efficienza',
    indicatori: [
      { chiave: 'oee', nome: 'OEE', unita: '', formato: 'percentuale' },
      { chiave: 'disponibilita', nome: 'Disponibilità', unita: '', formato: 'percentuale' },
      { chiave: 'prestazioni', nome: 'Prestazioni', unita: '', formato: 'percentuale' },
      { chiave: 'qualita', nome: 'Qualità', unita: '', formato: 'percentuale' },
      { chiave: 'saturazione', nome: 'Saturazione', unita: '', formato: 'percentuale' },
    ],
  },
  {
    titolo: 'Scarti',
    indicatori: [
      { chiave: 'tasso_scarto', nome: 'Incidenza degli scarti', unita: '', formato: 'percentuale' },
      { chiave: 'n_scarti', nome: 'Confezioni scartate', unita: 'conf', formato: 'intero' },
      { chiave: 'costo_scarti_eur', nome: 'Valore degli scarti', unita: '', formato: 'euro' },
    ],
  },
  {
    titolo: 'Energia e ambiente',
    indicatori: [
      { chiave: 'kwh', nome: 'Consumo energetico', unita: 'kWh', formato: 'intero' },
      { chiave: 'kwh_conf', nome: 'Consumo per confezione', unita: 'kWh/conf', formato: 'decimale' },
      { chiave: 'co2_kg', nome: 'Emissioni di CO₂', unita: 'kg', formato: 'intero' },
      { chiave: 'co2_kg_conf', nome: 'CO₂ per confezione', unita: 'kg/conf', formato: 'decimale' },
    ],
  },
  {
    titolo: 'Costi',
    indicatori: [
      { chiave: 'costo_fermi_eur', nome: 'Costo stimato dei fermi', unita: '', formato: 'euro' },
      { chiave: 'costo_totale_eur', nome: 'Costo di produzione', unita: '', formato: 'euro' },
      { chiave: 'costo_unitario_eur', nome: 'Costo per confezione', unita: '', formato: 'euro' },
    ],
  },
];

@Component({
  selector: 'app-cruscotto',
  imports: [
    DatePipe,
    ReactiveFormsModule,
    MatButtonToggleModule,
    MatCardModule,
    MatDatepickerModule,
    MatFormFieldModule,
    MatProgressBarModule,
    MatSelectModule,
    MatTableModule,
  ],
  templateUrl: './cruscotto.html',
  styleUrl: './cruscotto.scss',
})
export class Cruscotto {
  protected readonly servizio = inject(KpiService);
  protected readonly gruppi = GRUPPI;
  protected readonly oggi = new Date();
  protected readonly colonne = ['periodo', 'n_buoni', 'oee', 'tasso_scarto', 'kwh_conf', 'costo_fermi_eur'];
  protected readonly formatta = formatta;

  // Il calendario emette prima l'inizio e poi la fine: i KPI si richiedono solo a intervallo completo.
  protected readonly intervallo = new FormGroup({
    da: new FormControl<Date | null>(this.servizio.filtri().da),
    a: new FormControl<Date | null>(this.servizio.filtri().a),
  });

  // Mentre arrivano i dati dei nuovi filtri restano visibili quelli precedenti, così la pagina non lampeggia.
  protected readonly risposta = linkedSignal<{ valore?: RispostaKpi; caricamento: boolean }, RispostaKpi | undefined>({
    source: () => {
      const kpi = this.servizio.kpi;
      return { valore: kpi.hasValue() ? kpi.value() : undefined, caricamento: kpi.isLoading() };
    },
    computation: (stato, precedente) => stato.valore ?? (stato.caricamento ? precedente?.value : undefined),
  });
  // Se l'elenco delle macchine non arriva il filtro offre solo la linea (value() di una richiesta in errore solleva).
  protected readonly macchine = computed(() => (this.servizio.macchine.hasValue() ? this.servizio.macchine.value() : []));
  protected readonly totale = computed(() => this.risposta()?.totale ?? null);
  protected readonly serie = computed(() => this.risposta()?.serie ?? []);

  /** "dal 21/09/2026 al 20/10/2026 · Linea" */
  protected readonly riferimento = computed(() => {
    const r = this.risposta();
    if (!r) return '';
    const ambito = r.ambito === 'linea' ? 'Linea' : this.nomeMacchina(r.ambito);
    return `dal ${dataBreve(r.da)} al ${dataBreve(r.a)} · ${ambito}`;
  });

  constructor() {
    this.intervallo.valueChanges.pipe(takeUntilDestroyed()).subscribe(({ da, a }) => {
      if (da && a) this.servizio.aggiorna({ da, a });
    });
  }

  protected cambiaGranularita(granularita: Granularita): void {
    this.servizio.aggiorna({ granularita });
  }

  protected cambiaAmbito(ambito: string): void {
    this.servizio.aggiorna({ ambito });
  }

  protected etichetta(punto: PuntoKpi): string {
    // La granularità della risposta, non quella dei filtri: durante il caricamento si vedono ancora i dati precedenti.
    return etichettaPeriodo(punto, this.risposta()?.granularita ?? 'giorno');
  }

  private nomeMacchina(codice: string): string {
    const macchina = this.macchine().find((m) => m.codice === codice);
    return macchina ? `${macchina.codice} ${macchina.nome}` : codice;
  }
}
