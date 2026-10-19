"""Configurazione del back-end, letta dalle variabili d'ambiente.

In Docker Compose le variabili arrivano dal file .env della radice del progetto. Per avviare il back-end
fuori da Docker va impostata DATABASE_URL verso il database esposto sul PC, ad esempio
postgresql+psycopg://utente:password@localhost:5432/pw30. Non c'è un valore predefinito, così nessuna
credenziale compare nel codice: se la variabile manca, l'avvio si ferma con un errore che lo dice.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Impostazioni(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str


@lru_cache
def impostazioni() -> Impostazioni:
    return Impostazioni()
