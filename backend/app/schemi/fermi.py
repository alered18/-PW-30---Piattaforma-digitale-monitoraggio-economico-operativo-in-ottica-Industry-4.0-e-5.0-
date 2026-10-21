from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class FermoOut(BaseModel):
    macchina: str = Field(examples=["M3"])
    causale: str = Field(examples=["guasto"])
    descrizione_causale: str
    pianificato: bool = Field(description="True per la manutenzione programmata, che non ha costo di fermo")
    inizio: datetime
    fine: datetime
    durata_s: int
    costo_eur: float = Field(description="Costo orario della macchina ferma più, per il collo di bottiglia, il "
                                         "valore della produzione persa; 0 per i fermi pianificati")


class AnomaliaOut(BaseModel):
    tipo: Literal["fermo", "soglia", "dato"]
    data: date
    macchina: str | None = Field(description="Codice della macchina; null se riferita alla linea")
    inizio: datetime | None
    fine: datetime | None
    causale: str | None
    kpi: str | None
    valore: float | None = Field(description="Fermo: costo in euro; soglia: valore del KPI; dato: minuti scoperti")
    soglia: float | None
    descrizione: str
