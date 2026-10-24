import { Alert } from './kpi';

export type StatoMacchina = 'in_funzione' | 'ferma' | 'senza_dati';

export interface MacchinaOperatore {
  codice: string;
  nome: string;
  /** Dall'ultima rilevazione del turno; 'senza_dati' se non ne arrivano da più di 2 minuti. */
  stato: StatoMacchina;
  causale: string | null;
  descrizione_causale: string | null;
  ultima_rilevazione: string | null;
}

export interface Turno {
  inizio: string;
  fine: string;
  /** Confezioni buone uscite dalla linea dall'inizio del turno. */
  n_buoni: number;
  n_scarti: number;
  tasso_scarto: number | null;
  /** Confezioni buone attese nel turno: capacità di linea × 8 h × quota obiettivo (parametro, 75%). */
  obiettivo: number;
  /** n_buoni / obiettivo, può superare 1; null se l'obiettivo è 0. */
  avanzamento: number | null;
}

export interface StatoOperatore {
  aggiornato_il: string;
  /** null fuori dall'orario di turno. */
  turno: Turno | null;
  macchine: MacchinaOperatore[];
  /** Superamenti di soglia del giorno. */
  alert: Alert[];
}
