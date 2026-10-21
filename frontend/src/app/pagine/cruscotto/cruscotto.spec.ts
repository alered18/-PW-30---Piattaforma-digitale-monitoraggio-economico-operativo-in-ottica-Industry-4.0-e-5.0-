import { registerLocaleData } from '@angular/common';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import localeIt from '@angular/common/locales/it';
import { Component, input, LOCALE_ID } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideNativeDateAdapter } from '@angular/material/core';
import { GraficoAndamento } from '../../componenti/grafico-andamento/grafico-andamento';
import { GraficoPareto } from '../../componenti/grafico-pareto/grafico-pareto';
import { PuntoKpi, RispostaKpi, ValoriKpi } from '../../modelli/kpi';
import { Cruscotto } from './cruscotto';

registerLocaleData(localeIt);

// Il DOM dei test non sa disegnare: al posto dei grafici dei segnaposto con gli stessi input.
@Component({ selector: 'app-grafico-andamento', template: '' })
class GraficoFinto {
  readonly grafico = input();
  readonly serie = input();
  readonly granularita = input();
}

@Component({ selector: 'app-grafico-pareto', template: '' })
class ParetoFinto {
  readonly causali = input();
  readonly errore = input();
}

const KPI: ValoriKpi = {
  n_tot: 22800, n_buoni: 21950, n_scarti: 850, produzione_kg: 10975, produttivita_conf_h: 1371.9,
  disponibilita: 0.88, prestazioni: 0.85, qualita: 0.9627, oee: 0.725, tasso_scarto: 0.0373,
  kwh: 4521.6, kwh_conf: 0.206, costo_fermi_eur: 1933.4, co2_kg: 1265.9, co2_kg_conf: 0.0577,
  saturazione: null, // non calcolabile: la card deve mostrare "n.d."
  costo_macchina_eur: 3200, costo_energia_eur: 904.3, costo_materia_eur: 5700, costo_totale_eur: 10096.7,
  costo_unitario_eur: 0.46, costo_scarti_eur: 212.5, prestazioni_limitate: false,
};
const GIORNO: PuntoKpi = { periodo: '2026-10-16', da: '2026-10-16', a: '2026-10-16', parziale: false, kpi: KPI };

describe('Cruscotto', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [Cruscotto],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideNativeDateAdapter(),
        { provide: LOCALE_ID, useValue: 'it-IT' }],
    });
    TestBed.overrideComponent(Cruscotto, {
      remove: { imports: [GraficoAndamento, GraficoPareto] },
      add: { imports: [GraficoFinto, ParetoFinto] },
    });
    http = TestBed.inject(HttpTestingController);
  });

  async function apri() {
    // whenStable() attenderebbe le richieste ancora aperte: tick() le fa solo partire, così il test può rispondere.
    const fixture = TestBed.createComponent(Cruscotto);
    TestBed.tick();
    http.expectOne('/api/macchine').flush([{ codice: 'M3', nome: 'Essiccatoio', ordine: 3 }]);
    http.expectOne((r) => r.url === '/api/fermi/ripartizione').flush([]);
    return fixture;
  }

  function card(fixture: { nativeElement: HTMLElement }, nome: string): string | undefined {
    const tutte = Array.from(fixture.nativeElement.querySelectorAll('.indicatore'));
    const trovata = tutte.find((c) => c.querySelector('.nome')?.textContent?.trim() === nome);
    return trovata?.querySelector('.valore')?.textContent?.replace(/\s+/g, ' ').trim();
  }

  it('mostra i KPI del periodo in formato italiano e "n.d." per quelli non calcolabili', async () => {
    const fixture = await apri();
    const richiesta = http.expectOne((r) => r.url === '/api/kpi');
    expect(richiesta.request.params.get('ambito')).toBe('linea');
    const risposta: RispostaKpi = {
      ambito: 'linea', granularita: 'giorno', da: '2026-10-16', a: '2026-10-16', serie: [GIORNO], totale: GIORNO,
    };
    richiesta.flush(risposta);
    await fixture.whenStable();
    fixture.detectChanges();

    expect(card(fixture, 'OEE')).toBe('72,5%');
    expect(card(fixture, 'Confezioni buone')).toBe('21.950 conf');
    expect(card(fixture, 'Consumo per confezione')).toBe('0,206 kWh/conf');
    expect(card(fixture, 'Costo stimato dei fermi')).toBe('1.933,40 €');
    expect(card(fixture, 'Saturazione')).toBe('n.d.');
    expect(fixture.nativeElement.textContent).toContain('dal 16/10/2026 al 16/10/2026 · Linea');
  });

  it('richiede di nuovo i KPI quando cambiano granularità e ambito', async () => {
    const fixture = await apri();
    http.expectOne((r) => r.url === '/api/kpi').flush({ ambito: 'linea', granularita: 'giorno', da: '2026-10-16',
      a: '2026-10-16', serie: [], totale: null });
    await fixture.whenStable();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Nessun dato nel periodo selezionato');

    const pagina = fixture.componentInstance as unknown as { cambiaGranularita(g: string): void; cambiaAmbito(a: string): void };
    pagina.cambiaGranularita('settimana');
    pagina.cambiaAmbito('M3');
    TestBed.tick();
    const richiesta = http.expectOne((r) => r.url === '/api/kpi');
    expect(richiesta.request.params.get('granularita')).toBe('settimana');
    expect(richiesta.request.params.get('ambito')).toBe('M3');
  });
});
