"""Configurazione del generatore, letta dalle variabili d'ambiente (file .env).

Il generatore conosce solo l'indirizzo delle API: nessuna credenziale del database.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Impostazioni(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GEN_", env_file=".env", extra="ignore")

    api_url: str = "http://localhost:8000/api"
    modalita: str = "auto"  # auto | storico | live | csv
    giorni: int = 90
    intervallo_live_s: int = 5
    seme: int = 42
