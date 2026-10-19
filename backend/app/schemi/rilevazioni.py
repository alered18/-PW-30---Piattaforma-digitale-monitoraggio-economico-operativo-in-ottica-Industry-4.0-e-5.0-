from datetime import date, datetime

from pydantic import BaseModel, Field, field_serializer

from app.servizi.calendario import FUSO


class RilevazioneIn(BaseModel):
    """Una rilevazione inviata dal generatore: un intervallo di funzionamento di una macchina.

    I controlli di coerenza (valori negativi, scarti oltre i pezzi, tempi, causali, orario di turno) sono fatti
    dal servizio di ingestione, così i messaggi d'errore sono gli stessi per le API e per l'import da CSV.
    """

    macchina: str = Field(examples=["M3"])
    inizio: datetime = Field(examples=["2026-10-19T08:15:00+02:00"], description="Con fuso orario")
    durata_s: int = Field(examples=[60])
    pezzi: int = Field(examples=[31], description="Confezioni prodotte nell'intervallo, buone e scartate")
    scarti: int = Field(examples=[1])
    t_funz_s: int = Field(examples=[60])
    t_fermo_s: int = Field(examples=[0])
    causale: str | None = Field(default=None, examples=[None], description="Obbligatoria se t_fermo_s > 0")
    kwh: float = Field(examples=[2.51], allow_inf_nan=False)
    tempo_ciclo_medio_s: float | None = Field(default=None, examples=[1.93], allow_inf_nan=False)


class RigaScartata(BaseModel):
    indice: int = Field(description="Posizione della rilevazione nel blocco inviato, da 0")
    macchina: str | None
    inizio: datetime | None
    motivi: list[str]


class EsitoIngestione(BaseModel):
    ricevute: int
    memorizzate: int
    duplicate: int = Field(description="Rilevazioni già presenti (stessa macchina e stesso inizio), ignorate")
    scartate: list[RigaScartata]
    giorni_toccati: list[date]


class RilevazioneOut(BaseModel):
    macchina: str
    inizio: datetime
    durata_s: int
    pezzi: int
    scarti: int
    t_funz_s: int
    t_fermo_s: int
    causale: str | None
    kwh: float
    tempo_ciclo_medio_s: float | None
    fonte: str

    @field_serializer("inizio")
    def _ora_di_roma(self, valore: datetime) -> str:
        return valore.astimezone(FUSO).isoformat()


class PaginaRilevazioni(BaseModel):
    totale: int
    pagina: int
    dimensione: int
    elementi: list[RilevazioneOut]


class UltimaRilevazione(BaseModel):
    macchina: str
    ultima: RilevazioneOut | None
