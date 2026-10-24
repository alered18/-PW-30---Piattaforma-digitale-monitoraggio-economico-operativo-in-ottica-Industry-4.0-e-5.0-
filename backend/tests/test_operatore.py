"""Vista operatore: stato delle macchine, avanzamento del turno, obiettivo."""

from datetime import datetime

import pytest

from app.api.operatore import ora_attuale
from app.main import app
from app.servizi.calendario import FUSO

GIORNO = "2026-10-12"  # lunedì


def minuto(macchina: str, ora: str, pezzi: int = 30, scarti: int = 0, causale: str | None = None) -> dict:
    t_fermo_s = 60 if causale else 0
    return {"macchina": macchina, "inizio": f"{GIORNO}T{ora}:00+02:00", "durata_s": 60,
            "pezzi": 0 if causale else pezzi, "scarti": scarti, "t_funz_s": 60 - t_fermo_s, "t_fermo_s": t_fermo_s,
            "causale": causale, "kwh": 1.0}


def stato_alle(client, ora: str) -> dict:
    app.dependency_overrides[ora_attuale] = lambda: datetime.fromisoformat(f"{GIORNO}T{ora}:00+02:00")
    return client.get("/api/operatore/stato").json()


def test_stato_delle_macchine_e_avanzamento_del_turno(client):
    rilevazioni = [minuto(m, ora) for m in ("M1", "M2", "M4") for ora in ("14:00", "14:01")]
    # M3 in guasto nell'ultimo minuto; M5 (uscita della linea) con 2 scarti; i dati del primo turno non contano.
    rilevazioni += [minuto("M3", "14:00"), minuto("M3", "14:01", causale="guasto"),
                    minuto("M5", "14:00", scarti=2), minuto("M5", "14:01"), minuto("M5", "13:59")]
    assert client.post("/api/rilevazioni", json=rilevazioni).status_code == 200

    stato = stato_alle(client, "14:02")
    assert [(m["codice"], m["stato"], m["causale"]) for m in stato["macchine"]] == [
        ("M1", "in_funzione", None), ("M2", "in_funzione", None), ("M3", "ferma", "guasto"),
        ("M4", "in_funzione", None), ("M5", "in_funzione", None)]
    assert stato["macchine"][2]["descrizione_causale"] == "Guasto"

    turno = stato["turno"]
    assert (turno["inizio"], turno["fine"]) == ("2026-10-12T14:00:00+02:00", "2026-10-12T22:00:00+02:00")
    # Obiettivo = capacità del collo di bottiglia (M3, 2000 conf/h) × 8 h × 75%.
    assert turno["obiettivo"] == 12000
    # Buone = uscita di M5 nel turno (60 - 2 scarti); scarti = somma di tutte le macchine.
    assert (turno["n_buoni"], turno["n_scarti"]) == (58, 2)
    assert turno["tasso_scarto"] == pytest.approx(2 / 60)
    assert turno["avanzamento"] == pytest.approx(58 / 12000)
    # Con così pochi pezzi l'OEE è sotto soglia: gli alert del giorno sono compresi.
    assert stato["alert"] and {a["tipo"] for a in stato["alert"]} == {"soglia"}

    # Senza dati da più di 2 minuti lo stato non è più attuale; dopo le 22 non c'è un turno in corso.
    assert {m["stato"] for m in stato_alle(client, "14:10")["macchine"]} == {"senza_dati"}
    sera = stato_alle(client, "22:30")
    assert sera["turno"] is None and {m["stato"] for m in sera["macchine"]} == {"senza_dati"}
