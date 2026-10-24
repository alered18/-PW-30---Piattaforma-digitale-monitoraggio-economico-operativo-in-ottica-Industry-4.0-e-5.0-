import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { FormArray, FormControl, ReactiveFormsModule, ValidatorFn, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTableModule } from '@angular/material/table';
import { Soglia, ValoriKpi } from '../../modelli/kpi';
import { messaggio } from '../../servizi/errori';
import { KpiService } from '../../servizi/kpi.service';

/**
 * Come si scrive la soglia di ogni KPI nel modulo. Le percentuali si inseriscono come tali (5 = 5%) e si inviano
 * all'API come frazioni (0,05); il costo dei fermi è un importo giornaliero.
 */
const UNITA: Partial<Record<keyof ValoriKpi, { unita: string; percentuale: boolean }>> = {
  oee: { unita: '%', percentuale: true },
  disponibilita: { unita: '%', percentuale: true },
  tasso_scarto: { unita: '%', percentuale: true },
  saturazione: { unita: '%', percentuale: true },
  kwh_conf: { unita: 'kWh/conf', percentuale: false },
  costo_fermi_eur: { unita: '€/giorno', percentuale: false },
};

/** Riga del modulo: la soglia letta dall'API e il campo con il valore da modificare. */
interface Riga {
  soglia: Soglia;
  unita: string;
  percentuale: boolean;
  campo: FormControl<number | null>;
}

@Component({
  selector: 'app-soglie',
  imports: [
    ReactiveFormsModule,
    MatButtonModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressBarModule,
    MatTableModule,
  ],
  templateUrl: './soglie.html',
  styleUrl: './soglie.scss',
})
export class Soglie {
  private readonly http = inject(HttpClient);
  private readonly kpi = inject(KpiService);
  private readonly avvisi = inject(MatSnackBar);

  protected readonly colonne = ['kpi', 'ambito', 'condizione', 'valore'];
  protected readonly righe = signal<Riga[]>([]);
  protected readonly campi = new FormArray<FormControl<number | null>>([]);
  protected readonly caricamento = signal(true);
  protected readonly salvataggio = signal(false);
  protected readonly errore = signal<string | null>(null);

  constructor() {
    this.carica();
  }

  protected salva(): void {
    if (this.campi.invalid) return;
    const modifiche = this.righe().map((r) => ({
      kpi: r.soglia.kpi,
      ambito: r.soglia.ambito,
      // Si arrotonda per non inviare 0.050000000000000003 al posto di 0.05.
      valore: r.percentuale ? Number((r.campo.value! / 100).toFixed(4)) : r.campo.value!,
    }));
    this.salvataggio.set(true);
    this.errore.set(null);
    this.http.put<Soglia[]>('/api/soglie', modifiche).subscribe({
      next: (soglie) => {
        this.mostra(soglie);
        this.salvataggio.set(false);
        // Il cruscotto rilegge KPI e alert, che ora riflettono le nuove soglie.
        this.kpi.kpi.reload();
        this.kpi.alert.reload();
        this.avvisi.open('Soglie salvate: KPI e alert sono stati rivalutati.', 'OK', { duration: 4000 });
      },
      error: (e: HttpErrorResponse) => {
        this.salvataggio.set(false);
        this.errore.set(`Soglie non salvate: ${messaggio(e)}`);
      },
    });
  }

  /** Riporta i campi ai valori memorizzati. */
  protected annulla(): void {
    this.carica();
  }

  private carica(): void {
    this.caricamento.set(true);
    this.errore.set(null);
    this.http.get<Soglia[]>('/api/soglie').subscribe({
      next: (soglie) => {
        this.mostra(soglie);
        this.caricamento.set(false);
      },
      error: (e: HttpErrorResponse) => {
        this.caricamento.set(false);
        this.errore.set(`Impossibile leggere le soglie: ${messaggio(e)}`);
      },
    });
  }

  private mostra(soglie: Soglia[]): void {
    this.campi.clear();
    const righe = soglie.map((soglia) => {
      const { unita, percentuale } = UNITA[soglia.kpi] ?? { unita: '', percentuale: false };
      const validatori = [Validators.required, Validators.min(0)];
      // Il database memorizza le soglie con 4 decimali: per una percentuale sono 2 decimali (2,55% = 0,0255).
      if (percentuale) validatori.push(Validators.max(100), alPiuDecimali(2));
      else validatori.push(alPiuDecimali(4));
      // 0.07 * 100 darebbe 7.000000000000001: si arrotonda ai decimali ammessi.
      const campo = new FormControl(percentuale ? Number((soglia.valore * 100).toFixed(2)) : soglia.valore, validatori);
      this.campi.push(campo);
      return { soglia, unita, percentuale, campo };
    });
    this.righe.set(righe);
    this.campi.markAsPristine();
  }
}

/** Rifiuta i valori con più decimali di quanti il database ne conserva, invece di arrotondarli in silenzio. */
function alPiuDecimali(n: number): ValidatorFn {
  return (c) => (c.value === null || Number(c.value.toFixed(n)) === c.value ? null : { decimali: n });
}
