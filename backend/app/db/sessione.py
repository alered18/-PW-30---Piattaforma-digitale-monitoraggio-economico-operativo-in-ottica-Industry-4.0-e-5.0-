"""Connessione al database e sessioni per le richieste."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import impostazioni


@lru_cache
def motore() -> Engine:
    # pool_pre_ping evita errori se il database è stato riavviato mentre il back-end era acceso.
    return create_engine(impostazioni().database_url, pool_pre_ping=True)


@lru_cache
def fabbrica_sessioni() -> sessionmaker[Session]:
    return sessionmaker(bind=motore())


def sessione() -> Iterator[Session]:
    """Dipendenza FastAPI: una sessione per richiesta, chiusa alla fine."""
    with fabbrica_sessioni()() as s:
        yield s
