import { TestBed } from '@angular/core/testing';
import { DateAdapter } from '@angular/material/core';
import { appConfig } from '../app.config';

describe('AdattatoreDateItaliano', () => {
  it('legge le date scritte a mano come giorno/mese/anno', () => {
    TestBed.configureTestingModule({ providers: appConfig.providers });
    const adattatore = TestBed.inject(DateAdapter<Date>);

    expect(adattatore.parse('07/10/2026', null)).toEqual(new Date(2026, 9, 7));
    expect(adattatore.parse('30/9/2026', null)).toEqual(new Date(2026, 8, 30));
    expect(adattatore.isValid(adattatore.parse('31/02/2026', null)!)).toBe(false);
    expect(adattatore.isValid(adattatore.parse('07/10/0026', null)!)).toBe(false);
    expect(adattatore.parse('  ', null)).toBeNull();
  });
});
