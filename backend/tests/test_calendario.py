from datetime import date, datetime

from app.servizi.calendario import FUSO, in_turno, secondi_disponibili

LUNEDI = date(2026, 10, 19)


def test_calendario_dei_turni():
    # Due turni dal lunedì al venerdì (6-22): 80 ore a settimana, nessun turno il sabato.
    settimana = sum(secondi_disponibili(date(2026, 10, giorno)) for giorno in range(19, 26))
    assert settimana == 80 * 3600
    assert secondi_disponibili(date(2026, 10, 24)) == 0
    # Giorno in corso: conta solo il tempo trascorso dalle 6.
    assert secondi_disponibili(LUNEDI, datetime(2026, 10, 19, 10, 0, tzinfo=FUSO)) == 4 * 3600
    # Un intervallo è in turno solo se finisce entro le 22.
    assert in_turno(datetime(2026, 10, 19, 6, 0, tzinfo=FUSO), 60)
    assert not in_turno(datetime(2026, 10, 19, 21, 59, 30, tzinfo=FUSO), 60)
    assert not in_turno(datetime(2026, 10, 24, 10, 0, tzinfo=FUSO), 60)  # sabato
