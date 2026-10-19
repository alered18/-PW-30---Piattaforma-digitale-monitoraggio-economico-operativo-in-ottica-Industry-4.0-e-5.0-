"""Verifiche sullo schema del database e sui dati iniziali."""

from datetime import datetime, timedelta, timezone

import psycopg
import pytest

INIZIO = datetime(2026, 10, 19, 8, 0, tzinfo=timezone.utc)


def inserisci_rilevazione(db, **valori):
    """Inserisce una rilevazione su M1; i campi non indicati hanno valori validi di un minuto senza fermi."""
    riga = dict(inizio=INIZIO, durata_s=60, pezzi=40, scarti=0, t_funz_s=60, t_fermo_s=0,
                causale_codice=None, kwh=0.5) | valori
    db.execute(
        """
        INSERT INTO rilevazione (macchina_id, inizio, durata_s, pezzi, scarti, t_funz_s, t_fermo_s, causale_codice, kwh)
        SELECT id, %(inizio)s, %(durata_s)s, %(pezzi)s, %(scarti)s, %(t_funz_s)s, %(t_fermo_s)s, %(causale_codice)s, %(kwh)s
        FROM macchina WHERE codice = 'M1'
        """,
        riga,
    )


def test_una_linea_e_cinque_macchine_in_ordine(db):
    assert db.execute("SELECT count(*) FROM linea").fetchone()[0] == 1
    macchine = db.execute("SELECT codice, nome FROM macchina ORDER BY ordine").fetchall()
    assert [codice for codice, _ in macchine] == ["M1", "M2", "M3", "M4", "M5"]
    assert macchine[2][1] == "Essiccatoio"


# Capacità (conf/h), potenza in funzione e a fermo (kW), costo orario (€/h), scarto nominale, costo di uno scarto (€).
MACCHINE_ATTESE = {
    "M1": (2400, 30, 3.0, 25, 0.003, 0.25),
    "M2": (2200, 90, 18.0, 40, 0.010, 0.25),
    "M3": (2000, 150, 105.0, 45, 0.015, 0.25),
    "M4": (2200, 25, 4.0, 35, 0.008, 0.29),
    "M5": (2600, 15, 1.5, 20, 0.001, 0.29),
}


def test_parametri_delle_macchine(db):
    righe = db.execute(
        """SELECT codice, capacita_conf_h, potenza_funz_kw, potenza_fermo_kw, costo_orario_eur,
                  scarto_nominale, costo_scarto_eur_conf, tempo_ciclo_ideale_s FROM macchina"""
    ).fetchall()
    for codice, *valori, tempo_ciclo in righe:
        assert tuple(float(v) for v in valori) == pytest.approx(MACCHINE_ATTESE[codice]), codice
        assert float(tempo_ciclo) == pytest.approx(3600 / MACCHINE_ATTESE[codice][0], abs=1e-6)
    assert len(righe) == 5


def test_essiccatoio_collo_di_bottiglia(db):
    assert db.execute("SELECT codice FROM macchina ORDER BY capacita_conf_h LIMIT 1").fetchone()[0] == "M3"


def test_causali_e_solo_la_manutenzione_pianificata(db):
    causali = dict(db.execute("SELECT codice, pianificata FROM causale_fermo").fetchall())
    assert set(causali) == {"guasto", "setup", "mancanza_materiale", "manutenzione", "micro_fermata"}
    assert [codice for codice, pianificata in causali.items() if pianificata] == ["manutenzione"]


def test_parametri_economici_e_soglie(db):
    parametri = dict(db.execute("SELECT chiave, valore FROM parametro").fetchall())
    assert float(parametri["prezzo_energia"]) == 0.20
    assert float(parametri["margine_conf"]) == 0.40
    assert float(parametri["fattore_co2"]) == 0.27
    soglia_scarto = db.execute(
        "SELECT verso, valore FROM soglia WHERE kpi = 'tasso_scarto' AND ambito = 'linea'"
    ).fetchone()
    assert soglia_scarto[0] == "max" and float(soglia_scarto[1]) == 0.05
    assert db.execute("SELECT count(*) FROM soglia").fetchone()[0] == 8


def test_rilevazione_valida_accettata(db):
    inserisci_rilevazione(db)
    inserisci_rilevazione(db, inizio=INIZIO + timedelta(minutes=1), t_funz_s=45, t_fermo_s=15,
                          causale_codice="micro_fermata", pezzi=28)
    assert db.execute("SELECT count(*) FROM rilevazione").fetchone()[0] == 2


@pytest.mark.parametrize(
    "valori",
    [
        pytest.param({"scarti": 41}, id="scarti oltre i pezzi"),
        pytest.param({"pezzi": -1}, id="pezzi negativi"),
        pytest.param({"t_funz_s": 50}, id="tempi che non sommano alla durata"),
        pytest.param({"t_funz_s": 30, "t_fermo_s": 30}, id="fermo senza causale"),
        pytest.param({"causale_codice": "guasto"}, id="causale senza fermo"),
        pytest.param({"t_funz_s": 0, "t_fermo_s": 60, "causale_codice": "pausa"}, id="causale non in elenco"),
    ],
)
def test_rilevazione_incoerente_rifiutata(db, valori):
    with pytest.raises((psycopg.errors.CheckViolation, psycopg.errors.ForeignKeyViolation)):
        inserisci_rilevazione(db, **valori)


def test_rilevazione_duplicata_rifiutata(db):
    inserisci_rilevazione(db)
    with pytest.raises(psycopg.errors.UniqueViolation):
        inserisci_rilevazione(db)


def test_indicatore_riferito_a_un_solo_ambito(db):
    inserisci = """
        INSERT INTO indicatore (data, linea_id, macchina_id, n_tot, n_buoni, n_scarti, kwh, costo_fermi_eur,
                                co2_kg, costo_macchina_eur, costo_energia_eur, costo_materia_eur, costo_totale_eur)
        VALUES ('2026-10-19', %s, %s, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    """
    db.execute(inserisci, (1, None))
    with pytest.raises(psycopg.errors.UniqueViolation):
        db.execute(inserisci, (1, None))  # la linea ha già il suo indicatore per quel giorno
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute(inserisci, (None, None))


def test_indicatore_frazioni_tra_zero_e_uno(db):
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute(
            """INSERT INTO indicatore (data, linea_id, n_tot, n_buoni, n_scarti, oee, kwh, costo_fermi_eur, co2_kg,
                                       costo_macchina_eur, costo_energia_eur, costo_materia_eur, costo_totale_eur)
               VALUES ('2026-10-19', 1, 0, 0, 0, 1.2, 0, 0, 0, 0, 0, 0, 0)"""
        )
