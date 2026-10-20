"""Orario di lavoro della linea: due turni consecutivi 06:00-22:00, dal lunedì al venerdì, ora di Roma."""

from collections.abc import Iterator
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("Europe/Rome")
APERTURA = time(6, 0)
CHIUSURA = time(22, 0)
CAMBIO_TURNO = time(14, 0)
INIZIO_MANUTENZIONE = time(20, 0)  # venerdì
VENERDI = 4


def lavorativo(giorno: date) -> bool:
    return giorno.weekday() < 5


def passi_del_giorno(giorno: date, passo_s: int, fino_a: datetime | None = None) -> Iterator[datetime]:
    """Istanti di inizio dei passi di simulazione di una giornata di turno, fino alle 22:00 o a `fino_a`."""
    istante = datetime.combine(giorno, APERTURA, tzinfo=FUSO)
    chiusura = datetime.combine(giorno, CHIUSURA, tzinfo=FUSO)
    limite = min(chiusura, fino_a) if fino_a else chiusura
    while istante + timedelta(seconds=passo_s) <= limite:
        yield istante
        istante += timedelta(seconds=passo_s)
