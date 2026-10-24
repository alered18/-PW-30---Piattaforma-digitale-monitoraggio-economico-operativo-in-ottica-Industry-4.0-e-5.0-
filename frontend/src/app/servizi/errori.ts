import { HttpErrorResponse } from '@angular/common/http';

/** Messaggio leggibile da un errore dell'API: il dettaglio del back-end se c'è, altrimenti lo stato HTTP. */
export function messaggio(e: HttpErrorResponse): string {
  const dettaglio = e.error?.detail;
  if (typeof dettaglio === 'string') return dettaglio;
  if (Array.isArray(dettaglio) && dettaglio[0]?.msg) return dettaglio[0].msg;
  return e.status === 0 ? 'il back-end non risponde' : `errore ${e.status}`;
}
