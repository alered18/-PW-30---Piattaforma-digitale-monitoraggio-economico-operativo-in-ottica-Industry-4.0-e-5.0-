"""Ricezione e consultazione delle rilevazioni sul database di test."""


def rilevazione(macchina="M3", inizio="2026-10-19T08:00:00+02:00", **altro):
    return {"macchina": macchina, "inizio": inizio, "durata_s": 60, "pezzi": 31, "scarti": 1,
            "t_funz_s": 60, "t_fermo_s": 0, "causale": None, "kwh": 2.5} | altro


BLOCCO = [
    rilevazione(),
    rilevazione(inizio="2026-10-19T08:01:00+02:00", pezzi=10, t_funz_s=20, t_fermo_s=40, causale="guasto"),
    rilevazione(macchina="M1"),
]


def test_blocco_valido_memorizzato_una_sola_volta(client):
    esito = client.post("/api/rilevazioni", json=BLOCCO)
    assert esito.status_code == 200
    assert esito.json() == {"ricevute": 3, "memorizzate": 3, "duplicate": 0, "scartate": [],
                            "giorni_toccati": ["2026-10-19"]}
    pagina = client.get("/api/rilevazioni", params={"macchina": "M3", "da": "2026-10-19", "a": "2026-10-19"}).json()
    assert pagina["totale"] == 2
    assert pagina["elementi"][1]["causale"] == "guasto"

    # Lo stesso blocco inviato di nuovo (ad esempio dopo un errore di rete) non duplica i dati.
    di_nuovo = client.post("/api/rilevazioni", json=BLOCCO).json()
    assert di_nuovo["memorizzate"] == 0 and di_nuovo["duplicate"] == 3

    ultime = {u["macchina"]: u["ultima"] for u in client.get("/api/rilevazioni/ultime").json()}
    assert ultime["M3"]["inizio"] == "2026-10-19T08:01:00+02:00"
    assert ultime["M2"] is None


ERRATE = [
    (rilevazione(scarti=40), "gli scarti non possono superare i pezzi prodotti"),
    (rilevazione(macchina="M9"), "macchina 'M9' inesistente"),
    (rilevazione(inizio="2026-10-19T23:00:00+02:00"), "fuori dall'orario di turno"),
    (rilevazione(pezzi=-1), "pezzi non può essere negativo"),
    (rilevazione(t_funz_s=50), "deve essere uguale alla durata"),
    (rilevazione(pezzi=0, scarti=0, t_funz_s=0, t_fermo_s=60), "un fermo deve avere una causale"),
    (rilevazione(pezzi=0, scarti=0, t_funz_s=0, t_fermo_s=60, causale="pausa"), "causale 'pausa' non ammessa"),
    (rilevazione(inizio="2026-10-19T08:00:30+02:00"), "si sovrappone"),  # alla rilevazione già memorizzata
]


def test_blocco_con_una_riga_errata_rifiutato_per_intero(client):
    client.post("/api/rilevazioni", json=[rilevazione()])
    for errata, motivo in ERRATE:
        esito = client.post("/api/rilevazioni", json=[rilevazione(macchina="M1"), errata])
        assert esito.status_code == 422, motivo
        scartata, = esito.json()["scartate"]
        assert scartata["indice"] == 1
        assert any(motivo in m for m in scartata["motivi"]), scartata["motivi"]
    assert client.get("/api/rilevazioni").json()["totale"] == 1  # nessuna riga dei blocchi rifiutati
