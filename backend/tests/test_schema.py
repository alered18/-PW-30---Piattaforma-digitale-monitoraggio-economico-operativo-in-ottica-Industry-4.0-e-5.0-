"""Verifiche sullo schema del database e sui dati iniziali."""

import psycopg
import pytest

# Capacità (conf/h), potenza in funzione e a fermo (kW), costo orario (€/h), scarto nominale, costo di uno scarto (€).
MACCHINE_ATTESE = {
    "M1": (2400, 30, 3.0, 25, 0.003, 0.25),
    "M2": (2200, 90, 18.0, 40, 0.010, 0.25),
    "M3": (2000, 150, 105.0, 45, 0.015, 0.25),
    "M4": (2200, 25, 4.0, 35, 0.008, 0.29),
    "M5": (2600, 15, 1.5, 20, 0.001, 0.29),
}


def test_dati_iniziali(db):
    righe = db.execute(
        """SELECT codice, capacita_conf_h, potenza_funz_kw, potenza_fermo_kw, costo_orario_eur,
                  scarto_nominale, costo_scarto_eur_conf FROM macchina ORDER BY ordine"""
    ).fetchall()
    assert [r[0] for r in righe] == ["M1", "M2", "M3", "M4", "M5"]
    for codice, *valori in righe:
        assert tuple(float(v) for v in valori) == pytest.approx(MACCHINE_ATTESE[codice]), codice
    assert db.execute("SELECT count(*) FROM causale_fermo").fetchone()[0] == 5
    assert db.execute("SELECT count(*) FROM parametro").fetchone()[0] == 8
    assert db.execute("SELECT count(*) FROM soglia").fetchone()[0] == 8


@pytest.mark.parametrize(
    "valori",
    [
        pytest.param("40, 41, 60, 0, NULL", id="scarti oltre i pezzi"),
        pytest.param("40, 0, 50, 0, NULL", id="tempi che non sommano alla durata"),
        pytest.param("40, 0, 30, 30, NULL", id="fermo senza causale"),
    ],
)
def test_il_database_rifiuta_rilevazioni_incoerenti(db, valori):
    with pytest.raises(psycopg.errors.CheckViolation):
        db.execute(
            f"""INSERT INTO rilevazione (macchina_id, inizio, durata_s, pezzi, scarti, t_funz_s, t_fermo_s,
                                         causale_codice, kwh)
                SELECT id, '2026-10-19 08:00+02', 60, {valori}, 0.5 FROM macchina WHERE codice = 'M1'"""
        )
