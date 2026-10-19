"""Configurazione comune dei test.

I test che usano il database lavorano su un database separato (pw30_test, creato al primo avvio del container)
e vi ricreano lo schema da zero con gli stessi script di database/init usati da Docker Compose.
Richiedono il servizio db avviato: docker compose up -d db
"""

import os
from pathlib import Path

import psycopg
import pytest

RADICE = Path(__file__).resolve().parents[2]
SCRIPT_SCHEMA = [RADICE / "database" / "init" / "01_schema.sql", RADICE / "database" / "init" / "02_dati_iniziali.sql"]


def _url_database_test() -> str:
    """Indirizzo del database di test: variabile d'ambiente oppure file .env nella radice del progetto."""
    url = os.environ.get("DATABASE_URL_TEST")
    if not url and (RADICE / ".env").exists():
        for riga in (RADICE / ".env").read_text(encoding="utf-8").splitlines():
            if riga.startswith("DATABASE_URL_TEST="):
                url = riga.split("=", 1)[1].strip()
    if not url:
        pytest.skip("DATABASE_URL_TEST non configurato")
    # Protezione: i test cancellano e ricreano lo schema, quindi devono puntare solo a un database di test.
    if not url.rsplit("/", 1)[-1].split("?")[0].endswith("_test"):
        pytest.fail(f"DATABASE_URL_TEST deve indicare un database il cui nome finisce in _test: {url}")
    # psycopg vuole l'indirizzo senza l'indicazione del driver usata da SQLAlchemy.
    return url.replace("postgresql+psycopg://", "postgresql://")


@pytest.fixture
def db():
    """Connessione a un database di test con schema e dati iniziali appena ricreati."""
    try:
        conn = psycopg.connect(_url_database_test(), autocommit=True)
    except psycopg.OperationalError as errore:
        pytest.skip(f"database di test non raggiungibile: {errore}")
    with conn:
        conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        for script in SCRIPT_SCHEMA:
            conn.execute(script.read_text(encoding="utf-8"))
        yield conn
