"""Configurazione del generatore, letta dalle variabili d'ambiente (file .env).

Il generatore conosce solo l'indirizzo delle API: nessuna credenziale del database.
"""

from datetime import datetime

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Impostazioni(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GEN_", env_file=".env", extra="ignore", env_ignore_empty=True)

    api_url: str = "http://localhost:8010/api"
    modalita: str = "auto"  # auto | storico | live | csv
    giorni: int = 90
    # Deve dividere 60: così i passi cadono sugli orari di apertura, cambio turno e manutenzione.
    intervallo_live_s: int = Field(default=5, gt=0)
    seme: int = 42
    # Fine dello storico; se assente è l'istante di avvio. Fissarla rende lo storico identico tra un avvio e l'altro.
    data_fine: datetime | None = None

    @field_validator("intervallo_live_s")
    @classmethod
    def _divide_il_minuto(cls, valore: int) -> int:
        if 60 % valore:
            raise ValueError("l'intervallo live deve dividere 60 secondi (1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60)")
        return valore
