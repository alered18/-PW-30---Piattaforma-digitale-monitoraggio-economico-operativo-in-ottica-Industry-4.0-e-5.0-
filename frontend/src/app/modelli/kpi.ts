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
}

export interface RispostaKpi {
  ambito: string;
  granularita: Granularita;
  da: string;
  a: string;
  serie: PuntoKpi[];
  totale: PuntoKpi | null;
}

export interface Macchina {
  codice: string;
  nome: string;
  ordine: number;
}
