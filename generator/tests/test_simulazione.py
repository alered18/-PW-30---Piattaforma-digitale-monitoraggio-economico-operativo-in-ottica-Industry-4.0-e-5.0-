"""Test della simulazione, senza back-end."""

from datetime import date, datetime

from client_api import ClientApi
from main import ripresa
from simulatore.calendario import FUSO
from simulatore.flusso import simula_storico
from simulatore.macchina import DatiMacchina

# Stessa anagrafica del database: capacità (conf/h), potenza in funzione e a fermo (kW), scarto nominale.
MACCHINE = [
    DatiMacchina("M1", 1, 2400, 30, 3.0, 0.003),
    DatiMacchina("M2", 2, 2200, 90, 18.0, 0.010),
    DatiMacchina("M3", 3, 2000, 150, 105.0, 0.015),
    DatiMacchina("M4", 4, 2200, 25, 4.0, 0.008),
    DatiMacchina("M5", 5, 2600, 15, 1.5, 0.001),
]
FINE = datetime(2026, 10, 16, 22, 0, tzinfo=FUSO)  # venerdì


def storico(seme: int, giorni: int) -> list[dict]:
    da = FINE.date().fromordinal(FINE.date().toordinal() - giorni)
    return [r for _, blocco in simula_storico(MACCHINE, seme, da, FINE) for r in blocco]


def test_stesso_seme_stessi_dati():
    assert storico(7, 7) == storico(7, 7)
    assert storico(7, 7) != storico(8, 7)


def test_rilevazioni_coerenti_e_solo_in_orario_di_turno():
    rilevazioni = storico(1, 7)
    giorni = {datetime.fromisoformat(r["inizio"]).date() for r in rilevazioni}
    assert giorni == {date(2026, 10, d) for d in (9, 12, 13, 14, 15, 16)}  # dal venerdì precedente, niente weekend
    for r in rilevazioni:
        ora = datetime.fromisoformat(r["inizio"]).time()
        assert 6 <= ora.hour < 22
        assert r["t_funz_s"] + r["t_fermo_s"] == r["durata_s"]
        assert 0 <= r["scarti"] <= r["pezzi"]
        assert (r["t_fermo_s"] > 0) == (r["causale"] is not None)
        assert r["pezzi"] == 0 or r["t_funz_s"] > 0
    assert any(r["causale"] == "manutenzione" for r in rilevazioni)  # il venerdì sera


def test_novanta_giorni_plausibili():
    # Uscita della linea = confezioni buone dell'ultima macchina, al ritmo della più lenta (1,8 s a confezione).
    rilevazioni = storico(42, 90)
    m5 = [r for r in rilevazioni if r["macchina"] == "M5"]
    m3 = [r for r in rilevazioni if r["macchina"] == "M3"]
    buone = sum(r["pezzi"] - r["scarti"] for r in m5)
    pianificato_s = sum(r["durata_s"] for r in m3 if r["causale"] != "manutenzione")
    scarti = sum(r["scarti"] for r in rilevazioni)
    oee_linea = buone * 1.8 / pianificato_s
    assert 0.60 <= oee_linea <= 0.85, oee_linea
    assert 0.02 <= scarti / (buone + scarti) <= 0.05


def test_modalita_auto_riprende_dopo_l_ultima_rilevazione():
    assert ripresa([{"macchina": "M1", "ultima": None}]) is None  # database vuoto: si genera lo storico
    ultime = [
        {"macchina": "M1", "ultima": {"inizio": "2026-10-16T21:58:00+02:00", "durata_s": 60}},
        {"macchina": "M2", "ultima": {"inizio": "2026-10-16T21:59:00+02:00", "durata_s": 60}},
    ]
    assert ripresa(ultime) == datetime(2026, 10, 16, 22, 0, tzinfo=FUSO)


def test_backend_spento_segnalato():
    # Nessun servizio in ascolto su questa porta: il generatore rinuncia invece di scrivere dati.
    assert ClientApi("http://127.0.0.1:9/api").attendi(tentativi=1, attesa_s=0) is False
