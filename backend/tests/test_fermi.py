"""Fermi ricavati dalle rilevazioni: unione, costo e consultazione."""

import pytest

GIORNO = "2026-10-12"


def minuto(macchina: str, ora: str, t_fermo_s: int = 0, causale: str | None = None) -> dict:
    pezzi = 30 if t_fermo_s < 60 else 0  # un minuto tutto di fermo non produce nulla
    return {"macchina": macchina, "inizio": f"{GIORNO}T{ora}:00+02:00", "durata_s": 60, "pezzi": pezzi, "scarti": 0,
            "t_funz_s": 60 - t_fermo_s, "t_fermo_s": t_fermo_s, "causale": causale, "kwh": 1.0}


def test_rilevazioni_contigue_con_la_stessa_causale_diventano_un_fermo(client):
    rilevazioni = [
        # M3: guasto per 3 minuti e 20 secondi, un minuto di lavoro, poi 2 minuti di setup.
        minuto("M3", "10:00", 60, "guasto"), minuto("M3", "10:01", 60, "guasto"), minuto("M3", "10:02", 60, "guasto"),
        minuto("M3", "10:03", 20, "guasto"), minuto("M3", "10:04"),
        minuto("M3", "10:05", 60, "setup"), minuto("M3", "10:06", 60, "setup"),
        # M2: manutenzione programmata (fermo pianificato, senza costo), poi un guasto che finisce proprio quando
        # inizia quello di M3: stessa causale ma macchine diverse, quindi fermi distinti.
        minuto("M2", "09:58", 60, "manutenzione"), minuto("M2", "09:59", 60, "guasto"),
    ]
    assert client.post("/api/rilevazioni", json=rilevazioni).status_code == 200

    fermi = client.get("/api/fermi", params={"da": GIORNO, "a": GIORNO}).json()
    m3 = [(f["causale"], f["inizio"], f["durata_s"]) for f in fermi if f["macchina"] == "M3"]
    assert m3 == [("guasto", "2026-10-12T08:00:00Z", 200), ("setup", "2026-10-12T08:05:00Z", 120)]
    m2 = [(f["causale"], f["pianificato"], f["durata_s"]) for f in fermi if f["macchina"] == "M2"]
    assert m2 == [("manutenzione", True, 60), ("guasto", False, 60)]
    assert next(f for f in fermi if f["causale"] == "manutenzione")["costo_eur"] == 0

    # Il costo dei singoli fermi somma al costo dei fermi della macchina nei KPI del giorno.
    kpi_m3 = client.get("/api/kpi", params={"da": GIORNO, "a": GIORNO, "ambito": "M3"}).json()["totale"]["kpi"]
    assert sum(f["costo_eur"] for f in fermi if f["macchina"] == "M3") == pytest.approx(kpi_m3["costo_fermi_eur"],
                                                                                       abs=0.001)

    # Ricalcolare il giorno non duplica i fermi.
    client.post("/api/kpi/ricalcola", params={"da": GIORNO, "a": GIORNO})
    assert client.get("/api/fermi", params={"da": GIORNO, "a": GIORNO}).json() == fermi
    # Ripartizione per causale (Pareto): stessi totali dell'elenco, dalla causale con più tempo di fermo.
    ripartizione = client.get("/api/fermi/ripartizione", params={"da": GIORNO, "a": GIORNO}).json()
    assert [(r["causale"], r["n_fermi"], r["durata_s"]) for r in ripartizione] == [
        ("guasto", 2, 260), ("setup", 1, 120), ("manutenzione", 1, 60)]
    assert sum(r["costo_eur"] for r in ripartizione) == pytest.approx(sum(f["costo_eur"] for f in fermi), abs=0.01)
    solo_m2 = client.get("/api/fermi/ripartizione", params={"da": GIORNO, "a": GIORNO, "ambito": "M2"}).json()
    assert [r["causale"] for r in solo_m2] == ["guasto", "manutenzione"]  # a pari durata, in ordine di codice

    anomalie = client.get("/api/anomalie", params={"da": GIORNO, "a": GIORNO, "tipo": "fermo", "macchina": "M3"})
    assert [a["descrizione"] for a in anomalie.json()] == ["M3: setup / cambio formato di 2 min",
                                                           "M3: guasto di 3 min 20 s"]
