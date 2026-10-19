"""Calendario dei turni della linea.

Due turni consecutivi da 8 ore, 06:00-14:00 e 14:00-22:00, dal lunedì al venerdì, nel fuso orario di Roma.
Sabato e domenica non hanno tempo disponibile; le festività non sono considerate.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("Europe/Rome")
INIZIO_TURNI = time(6, 0)
FINE_TURNI = time(22, 0)
GIORNI_LAVORATIVI = range(0, 5)  # lunedì = 0 ... venerdì = 4
SECONDI_GIORNATA = 16 * 3600


def giorno_di(istante: datetime) -> date:
    """Giorno di calendario (ora di Roma) a cui appartiene un istante."""
    return istante.astimezone(FUSO).date()


def lavorativo(giorno: date) -> bool:
    return giorno.weekday() in GIORNI_LAVORATIVI


def apertura(giorno: date) -> datetime:
    return datetime.combine(giorno, INIZIO_TURNI, tzinfo=FUSO)


def chiusura(giorno: date) -> datetime:
    return datetime.combine(giorno, FINE_TURNI, tzinfo=FUSO)


def in_turno(inizio: datetime, durata_s: int) -> bool:
    """True se l'intervallo [inizio, inizio + durata] sta tutto dentro l'orario di turno di un giorno lavorativo."""
    giorno = giorno_di(inizio)
    fine = inizio + timedelta(seconds=durata_s)
    return lavorativo(giorno) and apertura(giorno) <= inizio and fine <= chiusura(giorno)


def secondi_disponibili(giorno: date, fino_a: datetime | None = None) -> int:
    """Tempo disponibile di una macchina in un giorno, in secondi.

    Senza `fino_a` è l'intera giornata di turno (16 h nei giorni lavorativi, 0 negli altri). Con `fino_a` conta
    solo il tempo di turno trascorso fino a quell'istante: serve per il giorno in corso, i cui KPI sono parziali.
    """
    if not lavorativo(giorno):
        return 0
    if fino_a is None:
        return SECONDI_GIORNATA
    limite = min(max(fino_a.astimezone(FUSO), apertura(giorno)), chiusura(giorno))
    return int((limite - apertura(giorno)).total_seconds())
