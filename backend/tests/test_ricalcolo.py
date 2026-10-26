"""Dalle rilevazioni agli indicatori memorizzati, con la giornata del dataset di test."""

from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.servizi.calendario import FUSO
from app.servizi.ricalcolo import ricalcola
from conftest import _url_database_test

from dati.dataset_test import ATTESI_LINEA, ATTESI_M3

# Per ogni macchina: ore di funzionamento e di fermo, confezioni, scarti, potenza in funzione e a fermo (kW).
# Sono gli stessi numeri del dataset di test: la macchina gira dalle 6:00 e poi resta ferma per guasto fino alle 22:00.
GIORNATA = {
    "M1": (15.0, 1.0, 25600, 100, 30, 3),
    "M2": (14.5, 1.5, 25500, 300, 90, 18),
    "M3": (14.0, 2.0, 25200, 400, 150, 105),
    "M4": (15.0, 1.0, 24800, 200, 25, 4),
    "M5": (15.5, 0.5, 24600, 100, 15, 1.5),
}


def rilevazioni_del_lunedi():
    righe = []
    for codice, (funz_h, fermo_h, pezzi, scarti, p_funz, p_fermo) in GIORNATA.items():
        ore, minuti = divmod(round((6 + funz_h) * 60), 60)
        righe += [
            {"macchina": codice, "inizio": "2026-10-12T06:00:00+02:00", "durata_s": round(funz_h * 3600),
             "pezzi": pezzi, "scarti": scarti, "t_funz_s": round(funz_h * 3600), "t_fermo_s": 0,
             "kwh": p_funz * funz_h},
            {"macchina": codice, "inizio": f"2026-10-12T{ore:02d}:{minuti:02d}:00+02:00",
             "durata_s": round(fermo_h * 3600), "pezzi": 0, "scarti": 0, "t_funz_s": 0,
             "t_fermo_s": round(fermo_h * 3600), "causale": "guasto", "kwh": p_fermo * fermo_h},
        ]
    return righe


def indicatori(db):
    righe = db.execute(
        """SELECT coalesce(m.codice, 'linea'), i.oee, i.disponibilita, i.costo_fermi_eur, i.costo_energia_eur,
                  i.costo_totale_eur, i.parziale
           FROM indicatore i LEFT JOIN macchina m ON m.id = i.macchina_id WHERE i.data = '2026-10-12'"""
    ).fetchall()
    return {r[0]: [float(v) if not isinstance(v, bool) else v for v in r[1:]] for r in righe}


def test_rilevazioni_diventano_indicatori_e_ricalcolo(client, db):
    esito = client.post("/api/rilevazioni", json=rilevazioni_del_lunedi())
    assert esito.status_code == 200, esito.json()

    valori = indicatori(db)
    assert len(valori) == 6  # 5 macchine + linea
    oee, disponibilita, costo_fermi, _, costo_totale, parziale = valori["linea"]
    assert oee == pytest.approx(ATTESI_LINEA["oee"], abs=1e-5)
    assert disponibilita == pytest.approx(ATTESI_LINEA["disponibilita"], abs=1e-5)
    assert costo_fermi == pytest.approx(ATTESI_LINEA["costo_fermi_eur"])
    assert costo_totale == pytest.approx(ATTESI_LINEA["costo_totale_eur"], abs=0.01)
    assert not parziale
    assert valori["M3"][0] == pytest.approx(ATTESI_M3["oee"], abs=1e-5)

    assert client.post("/api/kpi/ricalcola", params={"da": "2026-10-12", "a": "2026-10-12"}).status_code == 200
    assert indicatori(db) == valori

    # Con un nuovo prezzo dell'energia il ricalcolo aggiorna il costo energetico del giorno.
    assert valori["linea"][3] == pytest.approx(941.45)  # 4.707,25 kWh × 0,20 €
    assert client.put("/api/parametri/prezzo_energia", json={"valore": 0.40}).status_code == 200
    esito = client.post("/api/kpi/ricalcola", params={"da": "2026-10-01", "a": "2026-10-31"}).json()
    assert esito == {"giorni_ricalcolati": ["2026-10-12"]}
    assert indicatori(db)["linea"][3] == pytest.approx(1882.90)


def test_giorno_in_corso_parziale_fino_all_ultima_rilevazione(client, db):
    # Un'ora di lavoro di M3 (6:00-7:00) e il ricalcolo fatto alle 10:00 dello stesso giorno: il giorno è parziale
    # e il tempo disponibile arriva solo fino all'ultima rilevazione, così l'OEE non è penalizzato dal futuro.
    client.post("/api/rilevazioni", json=[{"macchina": "M3", "inizio": "2026-10-12T06:00:00+02:00", "durata_s": 3600,
                                           "pezzi": 2000, "scarti": 0, "t_funz_s": 3600, "t_fermo_s": 0, "kwh": 150}])
    motore = create_engine(_url_database_test().replace("postgresql://", "postgresql+psycopg://"))
    with Session(motore) as sessione:
        ricalcola(sessione, [date(2026, 10, 12)], adesso=datetime(2026, 10, 12, 10, 0, tzinfo=FUSO))
    motore.dispose()
    t_disp, parziale = db.execute(
        """SELECT p.t_disp_s, p.parziale FROM produzione_giornaliera p JOIN macchina m ON m.id = p.macchina_id
           WHERE p.data = '2026-10-12' AND m.codice = 'M3'"""
    ).fetchone()
    assert (t_disp, parziale) == (3600, True)
    assert indicatori(db)["M3"][0] == pytest.approx(1.0)
