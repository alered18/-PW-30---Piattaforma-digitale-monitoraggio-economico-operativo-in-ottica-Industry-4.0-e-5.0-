from datetime import date, datetime

from app.servizi.calendario import FUSO, in_turno, secondi_disponibili

LUNEDI = date(2026, 10, 19)


def test_settimana_di_80_ore_e_sabato_senza_turni():
    settimana = sum(secondi_disponibili(date(2026, 10, giorno)) for giorno in range(19, 26))
    assert settimana == 80 * 3600
    assert secondi_disponibili(date(2026, 10, 24)) == 0


def test_giorno_in_corso_conta_solo_il_tempo_trascorso():
    assert secondi_disponibili(LUNEDI, datetime(2026, 10, 19, 10, 0, tzinfo=FUSO)) == 4 * 3600


def test_orario_di_turno():
    assert in_turno(datetime(2026, 10, 19, 6, 0, tzinfo=FUSO), 60)
    assert not in_turno(datetime(2026, 10, 19, 21, 59, 30, tzinfo=FUSO), 60)  # finisce dopo le 22
    assert not in_turno(datetime(2026, 10, 24, 10, 0, tzinfo=FUSO), 60)  # sabato
