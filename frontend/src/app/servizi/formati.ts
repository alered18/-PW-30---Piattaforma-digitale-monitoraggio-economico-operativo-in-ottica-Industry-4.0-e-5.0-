import { formatCurrency, formatDate, formatNumber, formatPercent } from '@angular/common';
import { Granularita, PuntoKpi } from '../modelli/kpi';

const LOCALE = 'it-IT';

/** Valore mostrato quando un indicatore non è calcolabile (ad esempio un rapporto con denominatore zero). */
export const ND = 'n.d.';

export type Formato = 'intero' | 'decimale' | 'percentuale' | 'euro';

export function formatta(valore: number | null | undefined, formato: Formato): string {
  if (valore === null || valore === undefined || !Number.isFinite(valore)) {
    return ND;
  }
  switch (formato) {
    case 'intero':
      return formatNumber(valore, LOCALE, '1.0-0');
    case 'decimale':
      return formatNumber(valore, LOCALE, '1.3-3');
    case 'percentuale':
      return formatPercent(valore, LOCALE, '1.1-1');
    case 'euro':
      return formatCurrency(valore, LOCALE, '€', 'EUR', '1.2-2');
  }
}

/** Data in formato ISO (aaaa-mm-gg) nel fuso del browser, come la vuole l'API. */
export function dataIso(data: Date): string {
  return formatDate(data, 'yyyy-MM-dd', LOCALE);
}

export function dataBreve(iso: string): string {
  return formatDate(iso, 'dd/MM/yyyy', LOCALE);
}

/** Etichetta leggibile di un periodo della serie: "lun 12/10/2026", "12/10 – 18/10/2026", "ottobre 2026". */
export function etichettaPeriodo(punto: PuntoKpi, granularita: Granularita): string {
  switch (granularita) {
    case 'giorno':
      return formatDate(punto.da, 'EEE dd/MM/yyyy', LOCALE);
    case 'settimana':
      return `${formatDate(punto.da, 'dd/MM', LOCALE)} – ${dataBreve(punto.a)}`;
    case 'mese':
      return formatDate(punto.da, 'MMMM yyyy', LOCALE);
  }
}
