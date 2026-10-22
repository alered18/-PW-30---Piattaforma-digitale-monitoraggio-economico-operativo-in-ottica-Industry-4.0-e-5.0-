from typing import Literal

from pydantic import BaseModel, Field


class SogliaCompleta(BaseModel):
    kpi: str = Field(examples=["tasso_scarto"])
    nome: str = Field(examples=["Incidenza degli scarti"])
    ambito: Literal["linea", "macchina"] = Field(description="linea, oppure ciascuna macchina")
    verso: Literal["min", "max"] = Field(description="min: fuori soglia se inferiore; max: fuori soglia se superiore")
    valore: float = Field(description="Le percentuali sono frazioni (0,05 = 5%)")


class SogliaModifica(BaseModel):
    kpi: str = Field(examples=["tasso_scarto"])
    ambito: Literal["linea", "macchina"]
    # Il limite superiore corrisponde alla precisione della colonna nel database (numeric(12, 4)).
    valore: float = Field(ge=0, lt=100_000_000, examples=[0.02])
