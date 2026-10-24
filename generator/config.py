"""Configurazione del generatore, letta dalle variabili d'ambiente (file .env).

Il generatore conosce solo l'indirizzo delle API: nessuna credenziale del database.
"""

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from simulatore.scenari import NOMI, nomi_da_configurazione


class Impostazioni(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GEN_", env_file=".env", extra="ignore", env_ignore_empty=True)

    api_url: str = "http://localhost:8010/api"
    modalita: Literal["auto", "storico", "live", "csv"] = "auto"
    giorni: int = 90
    # Deve dividere 60: così i passi cadono sugli orari di apertura, cambio turno e manutenzione.
    intervallo_live_s: int = Field(default=5, gt=0)
    seme: int = 42
    # Fine dello storico; se assente è l'istante di avvio. Fissarla rende lo storico identico tra un avvio e l'altro.
    data_fine: datetime | None = None
    # Scenari dello storico separati da virgole (degrado_trafila, mancanze_materiale, guasto_grave) oppure "nessuno".
    scenari: str = "degrado_trafila,mancanze_materiale,guasto_grave"
    # File scritto dalla modalità csv; il percorso predefinito vale avviando il generatore dalla sua cartella.
    file_csv: str = "../database/esempi/rilevazioni_esempio.csv"

    @field_validator("intervallo_live_s")
    @classmethod
    def _divide_il_minuto(cls, valore: int) -> int:
        if 60 % valore:
            raise ValueError("l'intervallo live deve dividere 60 secondi (1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30, 60)")
        return valore

    @field_validator("scenari")
    @classmethod
    def _scenari_validi(cls, valore: str) -> str:
        if nomi_da_configurazione(valore) - set(NOMI):
            raise ValueError(f"scenari validi: {', '.join(NOMI)} oppure nessuno")
        return valore
