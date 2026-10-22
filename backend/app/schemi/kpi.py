from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class ValoriKpi(BaseModel):
    """Valori dei KPI. Le percentuali sono frazioni (0,75 = 75%); null = non calcolabile ("n.d.")."""

    n_tot: int = Field(description="Confezioni prodotte, buone e scartate")
    n_buoni: int
    n_scarti: int
    produzione_kg: float
    produttivita_conf_h: float | None = Field(description="Confezioni buone per ora pianificata")
    disponibilita: float | None
    prestazioni: float | None
    qualita: float | None
    oee: float | None = Field(description="Efficienza complessiva: disponibilità × prestazioni × qualità")
    tasso_scarto: float | None
    kwh: float
    kwh_conf: float | None
    costo_fermi_eur: float
    co2_kg: float
    co2_kg_conf: float | None
    saturazione: float | None
    costo_macchina_eur: float
    costo_energia_eur: float
    costo_materia_eur: float
    costo_totale_eur: float
    costo_unitario_eur: float | None
    costo_scarti_eur: float
    prestazioni_limitate: bool = Field(description="Prestazioni calcolate oltre il 100% e limitate: dato da verificare")


class SogliaOut(BaseModel):
    kpi: str = Field(examples=["oee"])
    verso: Literal["min", "max"] = Field(description="min: fuori soglia se inferiore; max: fuori soglia se superiore")
    valore: float


class PuntoKpi(BaseModel):
    periodo: str = Field(examples=["2026-W42"], description="Giorno (2026-10-12), settimana ISO (2026-W42) o mese (2026-10)")
    da: date
    a: date
    parziale: bool = Field(description="Periodo incompleto: giorno in corso, dati mancanti o tagliato dall'intervallo")
    kpi: ValoriKpi
    stato_soglie: dict[str, Literal["ok", "fuori_soglia", "nd"]] = Field(
        description="Stato dei KPI che hanno una soglia; il costo dei fermi (€/giorno) solo per periodi di un giorno",
        examples=[{"oee": "fuori_soglia", "tasso_scarto": "ok"}])


class RispostaKpi(BaseModel):
    ambito: str
    granularita: Literal["giorno", "settimana", "mese"]
    da: date
    a: date
    soglie: list[SogliaOut] = Field(description="Soglie che valgono per l'ambito richiesto")
    serie: list[PuntoKpi]
    totale: PuntoKpi | None = Field(description="KPI dell'intero intervallo richiesto; null se non ci sono dati")
