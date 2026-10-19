from pydantic import BaseModel, ConfigDict, Field


class Schema(BaseModel):
    # Permette di costruire le risposte direttamente dagli oggetti letti dal database.
    model_config = ConfigDict(from_attributes=True)


class LineaOut(Schema):
    codice: str
    nome: str


class MacchinaOut(Schema):
    codice: str = Field(examples=["M3"])
    nome: str = Field(examples=["Essiccatoio"])
    ordine: int = Field(description="Posizione nella linea (1 = prima macchina)")
    capacita_conf_h: float = Field(description="Capacità ideale in confezioni all'ora")
    tempo_ciclo_ideale_s: float = Field(description="Secondi per confezione alla capacità ideale")
    potenza_funz_kw: float
    potenza_fermo_kw: float
    costo_orario_eur: float
    scarto_nominale: float = Field(description="Frazione di scarto attesa (0,01 = 1%)")
    costo_scarto_eur_conf: float


class CausaleOut(Schema):
    codice: str = Field(examples=["guasto"])
    descrizione: str
    pianificata: bool = Field(description="True per la manutenzione programmata")


class ParametroOut(Schema):
    chiave: str = Field(examples=["prezzo_energia"])
    valore: float
    unita: str
    descrizione: str


class ParametroModifica(BaseModel):
    # Il limite superiore corrisponde alla precisione della colonna nel database (numeric(12, 4)).
    valore: float = Field(ge=0, lt=100_000_000, description="Nuovo valore; i KPI già calcolati cambiano solo dopo un ricalcolo")
