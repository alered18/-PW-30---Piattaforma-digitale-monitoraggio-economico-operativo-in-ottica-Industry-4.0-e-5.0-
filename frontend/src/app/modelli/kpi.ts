/** Tipi delle risposte del back-end. Le percentuali sono frazioni (0.75 = 75%); null = non calcolabile. */

export type Granularita = 'giorno' | 'settimana' | 'mese';

export interface ValoriKpi {
  n_tot: number;
  n_buoni: number;
  n_scarti: number;
  produzione_kg: number;
  produttivita_conf_h: number | null;
  disponibilita: number | null;
  prestazioni: number | null;
  qualita: number | null;
  oee: number | null;
  tasso_scarto: number | null;
  kwh: number;
  kwh_conf: number | null;
  costo_fermi_eur: number;
  co2_kg: number;
  co2_kg_conf: number | null;
  saturazione: number | null;
  costo_macchina_eur: number;
  costo_energia_eur: number;
  costo_materia_eur: number;
  costo_totale_eur: number;
  costo_unitario_eur: number | null;
  costo_scarti_eur: number;
  prestazioni_limitate: boolean;
}

export interface PuntoKpi {
  /** Giorno (2026-10-12), settimana ISO (2026-W42) o mese (2026-10). */
  periodo: string;
  da: string;
  a: string;
  /** Periodo incompleto: giorno in corso, dati mancanti o tagliato dall'intervallo. */
  parziale: boolean;
  kpi: ValoriKpi;
  /** Stato dei KPI che hanno una soglia; il costo dei fermi (€/giorno) compare solo nei periodi di un giorno. */
  stato_soglie: Partial<Record<keyof ValoriKpi, StatoSoglia>>;
}

/** 'nd': KPI non calcolabile, mai considerato fuori soglia. */
export type StatoSoglia = 'ok' | 'fuori_soglia' | 'nd';

/** min: fuori soglia se il valore è inferiore; max: fuori soglia se è superiore. */
export type Verso = 'min' | 'max';

export interface SogliaKpi {
  kpi: keyof ValoriKpi;
  verso: Verso;
  valore: number;
}

/** Soglia completa, come la restituisce /api/soglie. */
export interface Soglia extends SogliaKpi {
  nome: string;
  ambito: 'linea' | 'macchina';
}

/** Superamento di una soglia registrato per un giorno (anomalia di tipo "soglia"). */
export interface Alert {
  data: string;
  /** Codice della macchina; null se riferito alla linea. */
  macchina: string | null;
  kpi: keyof ValoriKpi;
  valore: number;
  soglia: number;
  descrizione: string;
}

export interface RispostaKpi {
  ambito: string;
  granularita: Granularita;
  da: string;
  a: string;
  /** Soglie che valgono per l'ambito richiesto. */
  soglie: SogliaKpi[];
  serie: PuntoKpi[];
  totale: PuntoKpi | null;
}

export interface Macchina {
  codice: string;
  nome: string;
  ordine: number;
}

/** Fermi di una causale nel periodo (dati del diagramma di Pareto). */
export interface CausaleRipartita {
  causale: string;
  descrizione_causale: string;
  /** Manutenzione programmata: fermo previsto, senza costo. */
  pianificato: boolean;
  n_fermi: number;
  durata_s: number;
  costo_eur: number;
}
