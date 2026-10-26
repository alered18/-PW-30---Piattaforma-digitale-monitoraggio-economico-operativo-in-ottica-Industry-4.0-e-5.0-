"""Soglie dei KPI: stato nell'API dei KPI, alert registrati come anomalie e modifica delle soglie."""

import pytest

from app.servizi.soglie import RegolaSoglia, valuta
from test_ricalcolo import rilevazioni_del_lunedi

GIORNO = {"da": "2026-10-12", "a": "2026-10-12"}


def test_confronto_con_le_soglie():
    oee_minimo = RegolaSoglia("oee", "min", 0.65)
    assert valuta(0.60, oee_minimo) == "fuori_soglia"
    assert valuta(0.65, oee_minimo) == "ok"  # uguale alla soglia: non è un superamento
    assert valuta(0.649996, oee_minimo) == "ok"  # confrontato come memorizzato: 0,65000
    assert valuta(None, oee_minimo) == "nd"  # KPI non calcolabile: mai fuori soglia
    assert valuta(0.06, RegolaSoglia("tasso_scarto", "max", 0.05)) == "fuori_soglia"


def test_modifica_della_soglia_di_scarto_e_alert(client):
    assert client.post("/api/rilevazioni", json=rilevazioni_del_lunedi()).status_code == 200

    def linea(**altro):
        return client.get("/api/kpi", params=GIORNO | altro).json()["serie"][0]

    def alert_di_scarto():
        anomalie = client.get("/api/anomalie", params=GIORNO | {"tipo": "soglia"}).json()
        return [a for a in anomalie if a["kpi"] == "tasso_scarto" and a["macchina"] is None]

    scarto = linea()["kpi"]["tasso_scarto"]
    assert 0.005 < scarto < 0.05  # sotto la soglia di default del 5%
    assert linea()["stato_soglie"]["tasso_scarto"] == "ok" and alert_di_scarto() == []

    # Soglia abbassata sotto il valore del giorno: il KPI risulta fuori soglia e compare l'alert.
    risposta = client.put("/api/soglie", json=[{"kpi": "tasso_scarto", "ambito": "linea", "valore": 0.005}])
    assert risposta.status_code == 200
    assert linea()["stato_soglie"]["tasso_scarto"] == "fuori_soglia"
    [alert] = alert_di_scarto()
    assert (alert["valore"], alert["soglia"]) == (pytest.approx(scarto, abs=1e-4), 0.005)
    assert "sopra la soglia massima di 0,5%" in alert["descrizione"]

    # La soglia resta memorizzata e un nuovo ricalcolo del giorno la rispetta.
    soglia = next(s for s in client.get("/api/soglie").json() if s["kpi"] == "tasso_scarto" and s["ambito"] == "linea")
    assert soglia["valore"] == 0.005
    client.post("/api/kpi/ricalcola", params=GIORNO)
    assert len(alert_di_scarto()) == 1

    # Il costo dei fermi (€/giorno) si valuta per un giorno ma non per una settimana.
    assert "costo_fermi_eur" in linea()["stato_soglie"]
    assert "costo_fermi_eur" not in linea(granularita="settimana")["stato_soglie"]

    # Valori non ammessi: soglia inesistente o percentuale oltre il 100%.
    assert client.put("/api/soglie", json=[{"kpi": "kwh", "ambito": "linea", "valore": 1}]).status_code == 422
    assert client.put("/api/soglie", json=[{"kpi": "oee", "ambito": "linea", "valore": 65}]).status_code == 422
