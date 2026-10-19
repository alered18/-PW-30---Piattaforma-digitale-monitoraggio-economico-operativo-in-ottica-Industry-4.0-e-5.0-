"""API dei dati di base, verificate sul database di test."""

import pytest


def test_macchine_nell_ordine_della_linea_con_i_parametri(client):
    macchine = client.get("/api/macchine").json()
    assert [m["codice"] for m in macchine] == ["M1", "M2", "M3", "M4", "M5"]
    assert macchine[2] == {
        "codice": "M3",
        "nome": "Essiccatoio",
        "ordine": 3,
        "capacita_conf_h": 2000.0,
        "tempo_ciclo_ideale_s": pytest.approx(1.8),
        "potenza_funz_kw": 150.0,
        "potenza_fermo_kw": 105.0,
        "costo_orario_eur": 45.0,
        "scarto_nominale": 0.015,
        "costo_scarto_eur_conf": 0.25,
    }


def test_causali_con_la_sola_manutenzione_pianificata(client):
    causali = client.get("/api/causali").json()
    assert len(causali) == 5
    assert [c["codice"] for c in causali if c["pianificata"]] == ["manutenzione"]


def test_modifica_di_un_parametro(client):
    assert client.put("/api/parametri/prezzo_energia", json={"valore": 0.25}).status_code == 200
    parametri = {p["chiave"]: p["valore"] for p in client.get("/api/parametri").json()}
    assert parametri["prezzo_energia"] == 0.25
    assert client.put("/api/parametri/inventato", json={"valore": 1}).status_code == 404
    assert client.put("/api/parametri/prezzo_energia", json={"valore": -1}).status_code == 422


def test_documentazione_elenca_gli_endpoint(client):
    percorsi = client.get("/api/openapi.json").json()["paths"]
    for percorso in ["/api/salute", "/api/macchine", "/api/causali", "/api/parametri", "/api/rilevazioni"]:
        assert percorso in percorsi
