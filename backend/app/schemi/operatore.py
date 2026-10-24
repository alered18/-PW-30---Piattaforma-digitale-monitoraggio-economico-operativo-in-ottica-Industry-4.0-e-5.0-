from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemi.fermi import AnomaliaOut


class StatoMacchina(BaseModel):
    codice: str = Field(examples=["M3"])
    nome: str
    stato: Literal["in_funzione", "ferma", "senza_dati"] = Field(
        description="Dall'ultima rilevazione del turno; senza_dati se non ne arrivano da più di 2 minuti")
    causale: str | None = Field(description="Codice della causale se la macchina è ferma", examples=["guasto"])
    descrizione_causale: str | None
    ultima_rilevazione: datetime | None = Field(description="Fine dell'ultima rilevazione ricevuta nel turno")


class Turno(BaseModel):
    inizio: datetime
    fine: datetime
    n_buoni: int = Field(description="Confezioni buone uscite dalla linea (ultima macchina) dall'inizio del turno")
    n_scarti: int = Field(description="Confezioni scartate da tutte le macchine dall'inizio del turno")
    tasso_scarto: float | None
    obiettivo: int = Field(description="Confezioni buone attese nel turno: capacità di linea × 8 h × quota obiettivo")
    avanzamento: float | None = Field(description="Confezioni buone / obiettivo (può superare 1); null se l'obiettivo è 0")


class StatoOperatore(BaseModel):
    aggiornato_il: datetime
    turno: Turno | None = Field(description="Null fuori dall'orario di turno")
    macchine: list[StatoMacchina]
    alert: list[AnomaliaOut] = Field(description="Superamenti di soglia del giorno, dal più recente")
