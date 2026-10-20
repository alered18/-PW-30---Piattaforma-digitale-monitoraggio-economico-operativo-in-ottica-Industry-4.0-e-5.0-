"""Test della simulazione, senza back-end."""

from dataclasses import asdict
from datetime import date, datetime, timedelta

from client_api import ClientApi
from config import Impostazioni
from main import live, ripresa
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


class ClientFinto:
    """Al posto del back-end: restituisce l'anagrafica e conserva i blocchi ricevuti."""

    def __init__(self):
        self.blocchi = []

    def macchine(self):
        return [asdict(m) for m in MACCHINE]

    def invia(self, blocco):
        self.blocchi.append(blocco)
        return {"memorizzate": len(blocco), "duplicate": 0}


def esegui_live(da: datetime, minuti: int) -> list[list[dict]]:
    # Orologio simulato: "dormire" sposta solo l'ora corrente, così il test dura un istante.
    orologio = [da]
    client = ClientFinto()
    live(client, Impostazioni(intervallo_live_s=5), fino_a=da + timedelta(minutes=minuti),
         adesso=lambda: orologio[0], dormi=lambda s: orologio.__setitem__(0, orologio[0] + timedelta(seconds=s)))
    return client.blocchi


def test_live_un_blocco_ogni_5_secondi_solo_in_orario_di_turno():
    blocchi = esegui_live(datetime(2026, 10, 16, 10, 0, 2, tzinfo=FUSO), 1)  # parte dal passo allineato 10:00:00
    assert len(blocchi) == 12 and all(len(b) == 5 for b in blocchi)
    assert blocchi[0][0]["inizio"] == "2026-10-16T10:00:00+02:00" and blocchi[0][0]["durata_s"] == 5
    # A cavallo della chiusura delle 22:00 si inviano solo i passi che finiscono entro l'orario di turno.
    assert len(esegui_live(datetime(2026, 10, 16, 21, 59, 30, tzinfo=FUSO), 1)) == 6
