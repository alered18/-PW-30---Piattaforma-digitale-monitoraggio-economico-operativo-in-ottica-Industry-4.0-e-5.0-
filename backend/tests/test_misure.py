"""Misure del sistema per il capitolo di architettura dei calcolatori."""

GIORNO = "2026-10-12"


def test_misure_di_spazio_e_di_tempo(client):
    rilevazioni = [{"macchina": m, "inizio": f"{GIORNO}T08:0{i}:00+02:00", "durata_s": 60, "pezzi": 30, "scarti": 1,
                    "t_funz_s": 60, "t_fermo_s": 0, "kwh": 1.25} for m in ("M1", "M2") for i in range(3)]
    assert client.post("/api/rilevazioni", json=rilevazioni).status_code == 200
    client.get("/api/kpi", params={"da": GIORNO, "a": GIORNO, "granularita": "settimana"})

    misure = client.get("/api/sistema/misure").json()
    rilevazione = next(t for t in misure["tabelle"] if t["tabella"] == "rilevazione")
    assert rilevazione["righe"] == 6 and rilevazione["byte_totali"] >= rilevazione["byte_dati"] > 0
    assert misure["database_byte"] > rilevazione["byte_totali"]
    # Una rilevazione occupa circa 200 byte in JSON e un centinaio come riga del database.
    assert 150 < misure["rilevazione"]["byte_json"] < 300
    assert 50 < misure["rilevazione"]["byte_tupla"] < 200
    assert misure["campionamento"] == [{"durata_s": 60, "rilevazioni": 6}]
    # Tempi: ricalcolo del giorno e risposte delle API, i KPI separati per granularità.
    assert misure["ricalcolo_giorno_ms"]["n"] >= 1
    assert misure["richieste_ms"]["POST /api/rilevazioni"]["media"] > 0
    assert misure["richieste_ms"]["GET /api/kpi?granularita=settimana"]["byte_medi"] > 0
