import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { App } from './app';

describe('App', () => {
  it('mostra il titolo e il menu nella barra in alto', async () => {
    TestBed.configureTestingModule({ imports: [App], providers: [provideRouter([])] });
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const barra = (fixture.nativeElement as HTMLElement).querySelector('mat-toolbar')?.textContent;
    expect(barra).toContain('Monitoraggio produzione');
    expect(barra).toContain('Cruscotto');
  });
});
