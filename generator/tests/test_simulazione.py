"""Test della simulazione, senza back-end."""

from dataclasses import asdict
from datetime import date, datetime, timedelta

from config import Impostazioni
from main import live
from simulatore.calendario import FUSO
from simulatore.flusso import simula_storico
from simulatore.macchina import DatiMacchina
from simulatore.scenari import Scenari

# Stessa anagrafica del database: capacità (conf/h), potenza in funzione e a fermo (kW), scarto nominale.
MACCHINE = [
    DatiMacchina("M1", 1, 2400, 30, 3.0, 0.003),
    DatiMacchina("M2", 2, 2200, 90, 18.0, 0.010),
    DatiMacchina("M3", 3, 2000, 150, 105.0, 0.015),
    DatiMacchina("M4", 4, 2200, 25, 4.0, 0.008),
    DatiMacchina("M5", 5, 2600, 15, 1.5, 0.001),
]
FINE = datetime(2026, 10, 16, 22, 0, tzinfo=FUSO)  # venerdì


def storico(seme: int, giorni: int, scenari: Scenari | None = None) -> list[dict]:
    da = FINE.date().fromordinal(FINE.date().toordinal() - giorni)
    return [r for _, blocco in simula_storico(MACCHINE, seme, da, FINE, scenari=scenari) for r in blocco]


def test_dati_riproducibili_coerenti_e_solo_in_orario_di_turno():
    rilevazioni = storico(7, 7)
    assert rilevazioni == storico(7, 7) and rilevazioni != storico(8, 7)  # stesso seme, stessi dati
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


SCENARI = Scenari(FINE.date(), {"degrado_trafila", "mancanze_materiale", "guasto_grave"})


def test_scenari_riconoscibili_nei_dati():
    dati = storico(42, 90, SCENARI)

    def rilevazioni(macchina: str, da: date, a: date) -> list[dict]:
        return [r for r in dati if r["macchina"] == macchina and da <= datetime.fromisoformat(r["inizio"]).date() <= a]

    # Degrado della trafila: scarto crescente per tre settimane, poi normale dopo la manutenzione.
    inizio, fine = SCENARI.degrado
    assert (inizio, fine) == (date(2026, 8, 31), date(2026, 9, 18))  # tre settimane, dal lunedì al venerdì

    def scarto(da: date, a: date) -> float:
        m2 = rilevazioni("M2", da, a)
        return sum(r["scarti"] for r in m2) / sum(r["pezzi"] for r in m2)

    settimane = [scarto(inizio + timedelta(weeks=s), inizio + timedelta(weeks=s, days=4)) for s in range(3)]
    assert settimane == sorted(settimane) and settimane[2] > 0.04, settimane
    assert scarto(fine + timedelta(days=3), fine + timedelta(days=7)) < 0.015

    # Guasto grave dell'essiccatoio: 4-6 ore di fermo in un giorno e OEE di linea sotto soglia.
    giorno = SCENARI.giorno_guasto
    assert giorno == date(2026, 9, 30)  # mercoledì della settimana dopo le mancanze
    m3 = rilevazioni("M3", giorno, giorno)
    guasto = [r for r in m3 if r["causale"] == "guasto" and datetime.fromisoformat(r["inizio"]).hour >= 8]
    assert 4 * 60 <= len(guasto) <= 6 * 60 + 120  # 4-6 h, più un eventuale guasto casuale contiguo
    # OEE di linea come nel back-end: confezioni buone in uscita al ritmo della più lenta (1,8 s) sul tempo pianificato.
    m5 = rilevazioni("M5", giorno, giorno)
    oee_linea = sum(r["pezzi"] - r["scarti"] for r in m5) * 1.8 / sum(r["durata_s"] for r in m3)
    assert oee_linea < 0.65, oee_linea

    # Mancanze di materiale: per una settimana sono la prima causale di fermo dell'impastatrice.
    da, a = SCENARI.mancanze
    assert (da, a) == (date(2026, 9, 21), date(2026, 9, 25))
    # Qualunque sia il giorno di fine dello storico, i tre periodi restano separati e in giorni lavorativi.
    for giorni in range(7):
        s = Scenari(FINE.date() + timedelta(days=giorni), set())
        assert s.degrado[1] < s.mancanze[0] and s.mancanze[1] < s.giorno_guasto and s.giorno_guasto.weekday() < 5
    durata: dict[str, int] = {}
    for r in rilevazioni("M1", da, a):
        if r["causale"]:
            durata[r["causale"]] = durata.get(r["causale"], 0) + r["t_fermo_s"]
    assert max(durata, key=durata.get) == "mancanza_materiale", durata
