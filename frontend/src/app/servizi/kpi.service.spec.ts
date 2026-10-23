import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ApplicationRef } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { AGGIORNAMENTO_MS, KpiService } from './kpi.service';

describe('KpiService', () => {
  let http: HttpTestingController;
  let servizio: KpiService;

  // Orologio simulato: solo data e timer periodici, il resto di Angular usa quelli veri.
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] });
    vi.setSystemTime(new Date(2026, 9, 16, 10, 0));
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    http = TestBed.inject(HttpTestingController);
    servizio = TestBed.inject(KpiService);
  });

  afterEach(() => vi.useRealTimers());

  // Fa partire la richiesta, risponde e attende che la risposta sia registrata (finché è in corso, reload() non fa nulla).
  async function rispondi(): Promise<void> {
    TestBed.tick();
    http.match('/api/macchine').forEach((r) => r.flush([]));
    http.expectOne((r) => r.url === '/api/kpi').flush({ serie: [], totale: null });
    http.match((r) => r.url === '/api/fermi/ripartizione' || r.url === '/api/anomalie').forEach((r) => r.flush([]));
    await TestBed.inject(ApplicationRef).whenStable();
  }

  it('rilegge KPI, fermi e alert ogni 10 secondi solo se il periodo comprende oggi', async () => {
    await rispondi(); // di default gli ultimi 30 giorni, quindi anche oggi
    vi.advanceTimersByTime(AGGIORNAMENTO_MS);
    await rispondi();

    servizio.aggiorna({ da: new Date(2026, 8, 1), a: new Date(2026, 8, 30) }); // settembre: dati che non cambiano
    await rispondi();
    vi.advanceTimersByTime(3 * AGGIORNAMENTO_MS);
    TestBed.tick();
    http.expectNone((r) => ['/api/kpi', '/api/fermi/ripartizione', '/api/anomalie'].includes(r.url));
  });
});
