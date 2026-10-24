import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatTableModule } from '@angular/material/table';
import { EsitoImport } from '../../modelli/importazione';
import { messaggio } from '../../servizi/errori';
import { dataBreve } from '../../servizi/formati';
import { KpiService } from '../../servizi/kpi.service';

/** Colonne che il file deve avere nell'intestazione, le stesse dell'API. */
export const COLONNE_CSV = [
  'macchina', 'inizio', 'durata_s', 'pezzi', 'scarti', 't_funz_s', 't_fermo_s', 'causale', 'kwh', 'tempo_ciclo_medio_s',
];

/** Caricamento di un file CSV di rilevazioni ed esito: righe memorizzate, già presenti e scartate con il motivo. */
@Component({
  selector: 'app-import',
  imports: [MatButtonModule, MatCardModule, MatIconModule, MatProgressBarModule, MatTableModule],
  templateUrl: './import.html',
  styleUrl: './import.scss',
})
export class Import {
  private readonly http = inject(HttpClient);
  private readonly kpi = inject(KpiService);

  protected readonly colonneCsv = COLONNE_CSV.join(',');
  protected readonly colonne = ['riga', 'macchina', 'inizio', 'motivi'];
  protected readonly file = signal<File | null>(null);
  protected readonly invio = signal(false);
  protected readonly esito = signal<EsitoImport | null>(null);
  protected readonly errore = signal<string | null>(null);
  protected readonly dataBreve = dataBreve;

  protected scegli(evento: Event): void {
    const input = evento.target as HTMLInputElement;
    this.file.set(input.files?.[0] ?? null);
    this.esito.set(null);
    this.errore.set(null);
  }

  protected importa(): void {
    const file = this.file();
    if (!file) return;
    const dati = new FormData();
    dati.append('file', file);
    this.invio.set(true);
    this.errore.set(null);
    this.esito.set(null);
    this.http.post<EsitoImport>('/api/rilevazioni/import', dati).subscribe({
      next: (esito) => {
        this.invio.set(false);
        this.esito.set(esito);
        // I giorni importati sono già ricalcolati: il cruscotto rilegge i KPI e gli alert.
        if (esito.memorizzate) {
          this.kpi.kpi.reload();
          this.kpi.alert.reload();
        }
      },
      error: (e: HttpErrorResponse) => {
        this.invio.set(false);
        this.errore.set(`File non importato: ${messaggio(e)}`);
      },
    });
  }
}
