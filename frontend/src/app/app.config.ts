import { registerLocaleData } from '@angular/common';
import { provideHttpClient, withFetch } from '@angular/common/http';
import localeIt from '@angular/common/locales/it';
import { ApplicationConfig, LOCALE_ID, provideBrowserGlobalErrorListeners } from '@angular/core';
import { DateAdapter, MAT_DATE_LOCALE, provideNativeDateAdapter } from '@angular/material/core';
import { provideRouter } from '@angular/router';
import { provideEchartsCore } from 'ngx-echarts';
import { routes } from './app.routes';
import { AdattatoreDateItaliano } from './servizi/adattatore-date';

// Numeri, valute e date in formato italiano (1.234,5 · 20/10/2026), calendario che inizia di lunedì.
registerLocaleData(localeIt);

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    provideHttpClient(withFetch()),
    provideNativeDateAdapter(),
    // Dopo provideNativeDateAdapter, che fornisce i formati: l'ultimo DateAdapter dichiarato è quello usato.
    { provide: DateAdapter, useClass: AdattatoreDateItaliano },
    { provide: LOCALE_ID, useValue: 'it-IT' },
    { provide: MAT_DATE_LOCALE, useValue: 'it-IT' },
    // ECharts si carica a parte, solo quando serve il primo grafico.
    provideEchartsCore({ echarts: () => import('./componenti/grafico-andamento/echarts').then((m) => m.default) }),
  ],
};
