"""API dei KPI per periodo, con due giornate del dataset di test (lunedì 12 e martedì 13 ottobre 2026)."""

import pytest

from dati.dataset_test import ATTESI_LINEA
from test_ricalcolo import rilevazioni_del_lunedi


def carica_due_giorni(client):
    lunedi = rilevazioni_del_lunedi()
    martedi = [r | {"inizio": r["inizio"].replace("2026-10-12", "2026-10-13")} for r in lunedi]
    assert client.post("/api/rilevazioni", json=lunedi + martedi).status_code == 200


def kpi(client, **parametri):
    risposta = client.get("/api/kpi", params={"da": "2026-10-01", "a": "2026-10-31"} | parametri)
    assert risposta.status_code == 200, risposta.json()
    return risposta.json()


def test_giorno_settimana_mese_e_totale(client):
    carica_due_giorni(client)

    giorni = kpi(client, granularita="giorno")["serie"]
    assert [p["periodo"] for p in giorni] == ["2026-10-12", "2026-10-13"]  # solo i giorni con dati
    assert giorni[0]["kpi"]["oee"] == pytest.approx(ATTESI_LINEA["oee"])

    settimana, = kpi(client, granularita="settimana")["serie"]
    assert settimana["periodo"] == "2026-W42"
    assert settimana["parziale"]  # mancano i dati da mercoledì a venerdì
    assert settimana["kpi"]["n_buoni"] == 2 * ATTESI_LINEA["n_buoni"]
    assert settimana["kpi"]["produzione_kg"] == pytest.approx(24500.0)  # 49.000 confezioni da 0,5 kg
    assert settimana["kpi"]["oee"] == pytest.approx(ATTESI_LINEA["oee"])

    risposta = kpi(client, granularita="mese", ambito="M3")
    assert [p["periodo"] for p in risposta["serie"]] == ["2026-10"]
    assert risposta["totale"]["kpi"]["costo_fermi_eur"] == pytest.approx(2 * 1690.0)


def test_parametri_non_validi(client):
    assert client.get("/api/kpi", params={"da": "2026-10-31", "a": "2026-10-01"}).status_code == 422
    errore = client.get("/api/kpi", params={"da": "2026-10-01", "a": "2026-10-31", "ambito": "M9"})
    assert errore.status_code == 422 and "M9" in errore.json()["detail"]
