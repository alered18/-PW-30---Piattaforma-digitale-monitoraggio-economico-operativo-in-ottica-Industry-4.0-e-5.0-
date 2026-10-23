import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'cruscotto' },
  {
    path: 'cruscotto',
    title: 'Cruscotto — Monitoraggio produzione',
    loadComponent: () => import('./pagine/cruscotto/cruscotto').then((m) => m.Cruscotto),
  },
  {
    path: 'soglie',
    title: 'Soglie — Monitoraggio produzione',
    loadComponent: () => import('./pagine/soglie/soglie').then((m) => m.Soglie),
  },
  { path: '**', redirectTo: 'cruscotto' },
];
