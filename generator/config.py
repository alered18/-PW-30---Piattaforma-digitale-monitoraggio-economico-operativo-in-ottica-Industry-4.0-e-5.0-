"""Configurazione del generatore, letta dalle variabili d'ambiente (file .env).

Il generatore conosce solo l'indirizzo delle API: nessuna credenziale del database.
"""

from datetime import datetime

from pydantic_settings import BaseSettings, SettingsConfigDict


class Impostazioni(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GEN_", env_file=".env", extra="ignore", env_ignore_empty=True)

    api_url: str = "http://localhost:8010/api"
    modalita: str = "auto"  # auto | storico | live | csv
    giorni: int = 90
    intervallo_live_s: int = 5
    seme: int = 42
    # Fine dello storico; se assente è l'istante di avvio. Fissarla rende lo storico identico tra un avvio e l'altro.
    data_fine: datetime | None = None
