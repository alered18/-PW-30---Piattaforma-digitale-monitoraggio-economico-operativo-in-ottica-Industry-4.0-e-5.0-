export interface RigaScartata {
  /** Numero di riga nel file; l'intestazione è la riga 1. */
  riga: number;
  macchina: string | null;
  inizio: string | null;
  motivi: string[];
}

export interface EsitoImport {
  /** Righe di dati lette dal file, intestazione esclusa. */
  righe: number;
  memorizzate: number;
  /** Righe già presenti (stessa macchina e stesso inizio), ignorate. */
  duplicate: number;
  scartate: RigaScartata[];
  giorni_toccati: string[];
}
