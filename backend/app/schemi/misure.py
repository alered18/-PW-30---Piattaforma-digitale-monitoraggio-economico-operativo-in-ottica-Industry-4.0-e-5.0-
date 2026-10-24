from datetime import datetime

from pydantic import BaseModel, Field


class Tabella(BaseModel):
    tabella: str
    righe: int
    byte_dati: int = Field(description="Solo le righe")
    byte_totali: int = Field(description="Righe, indici e dati fuori riga (TOAST)")
    byte_per_riga: float | None = Field(description="Byte totali / righe")


class Rilevazione(BaseModel):
    byte_json: float | None = Field(description="Media sulle ultime 1000 rilevazioni nel formato inviato alle API")
    byte_tupla: float | None = Field(description="Media della riga memorizzata, senza indici")


class Campionamento(BaseModel):
    durata_s: int = Field(description="Durata dell'intervallo di una rilevazione: 60 nello storico, 5 nel live")
    rilevazioni: int


class Tempi(BaseModel):
    n: int
    media: float
    mediana: float
    massimo: float
    ultimo: float
    byte_medi: int | None = Field(default=None, description="Dimensione media della risposta")


class Misure(BaseModel):
    misurato_il: datetime
    database_byte: int
    tabelle: list[Tabella]
    rilevazione: Rilevazione
    campionamento: list[Campionamento]
    ricalcolo_giorno_ms: Tempi | None = Field(description="Ricalcolo di un giorno (produzione, KPI, fermi, alert)")
    richieste_ms: dict[str, Tempi] = Field(description="Per metodo e percorso; per i KPI anche per granularità")
