"""API dei dati di base, verificate sul database di test."""

import pytest


def test_linee(client):
    risposta = client.get("/api/linee")
    assert risposta.status_code == 200
    assert risposta.json() == [{"codice": "L1", "nome": "Linea pasta corta"}]


def test_macchine_nell_ordine_della_linea_con_i_parametri(client):
    risposta = client.get("/api/macchine")
    assert risposta.status_code == 200
    macchine = risposta.json()
    assert [m["codice"] for m in macchine] == ["M1", "M2", "M3", "M4", "M5"]
    essiccatoio = macchine[2]
    assert essiccatoio == {
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
    for macchina in macchine:
        assert all(valore is not None for valore in macchina.values()), macchina


def test_causali(client):
    causali = client.get("/api/causali").json()
    assert {c["codice"] for c in causali} == {"guasto", "setup", "mancanza_materiale", "manutenzione", "micro_fermata"}
    assert [c["codice"] for c in causali if c["pianificata"]] == ["manutenzione"]


def test_parametri(client):
    parametri = {p["chiave"]: p for p in client.get("/api/parametri").json()}
    assert parametri["prezzo_energia"] == {
        "chiave": "prezzo_energia",
        "valore": 0.2,
        "unita": "€/kWh",
        "descrizione": "Prezzo dell'energia elettrica per un'utenza non domestica",
    }


def test_modifica_di_un_parametro_resta_memorizzata(client):
    risposta = client.put("/api/parametri/prezzo_energia", json={"valore": 0.25})
    assert risposta.status_code == 200
    assert risposta.json()["valore"] == 0.25
    parametri = {p["chiave"]: p["valore"] for p in client.get("/api/parametri").json()}
    assert parametri["prezzo_energia"] == 0.25


def test_modifica_di_un_parametro_inesistente(client):
    risposta = client.put("/api/parametri/inventato", json={"valore": 1})
    assert risposta.status_code == 404


@pytest.mark.parametrize("valore", [-1, 100_000_000])
def test_modifica_con_valore_fuori_intervallo_rifiutata(client, valore):
    assert client.put("/api/parametri/prezzo_energia", json={"valore": valore}).status_code == 422


def test_documentazione_elenca_gli_endpoint(client):
    percorsi = client.get("/api/openapi.json").json()["paths"]
    for percorso in ["/api/salute", "/api/linee", "/api/macchine", "/api/causali", "/api/parametri"]:
        assert percorso in percorsi
