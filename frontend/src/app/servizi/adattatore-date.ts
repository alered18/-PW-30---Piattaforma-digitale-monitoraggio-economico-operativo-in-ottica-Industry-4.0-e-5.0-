import { Injectable } from '@angular/core';
import { NativeDateAdapter } from '@angular/material/core';

/**
 * L'adattatore standard legge le date scritte a mano con il formato americano: 07/10/2026 diventerebbe il 10 luglio.
 * Qui si legge sempre giorno/mese/anno, come sono mostrate nei campi. Una data inesistente (31/02) non è valida.
 */
@Injectable()
export class AdattatoreDateItaliano extends NativeDateAdapter {
  override parse(valore: unknown): Date | null {
    if (typeof valore !== 'string') return super.parse(valore);
    const testo = valore.trim();
    if (!testo) return null;
    const parti = /^(\d{1,2})[/.-](\d{1,2})[/.-]([1-9]\d{3})$/.exec(testo);
    if (!parti) return this.invalid();
    const [giorno, mese, anno] = parti.slice(1).map(Number);
    const data = new Date(anno, mese - 1, giorno);
    return data.getMonth() === mese - 1 ? data : this.invalid();
  }
}
