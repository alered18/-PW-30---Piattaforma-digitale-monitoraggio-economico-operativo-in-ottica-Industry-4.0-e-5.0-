"""Dati e stato di una macchina durante la simulazione."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DatiMacchina:
    """Caratteristiche della macchina, lette dall'anagrafica del back-end."""

    codice: str
    ordine: int
    capacita_conf_h: float
    potenza_funz_kw: float
    potenza_fermo_kw: float
    scarto_nominale: float

    @property
    def tempo_ciclo_ideale_s(self) -> float:
        return 3600 / self.capacita_conf_h

    @classmethod
    def da_api(cls, dati: dict) -> "DatiMacchina":
        return cls(
            codice=dati["codice"],
            ordine=dati["ordine"],
            capacita_conf_h=dati["capacita_conf_h"],
            potenza_funz_kw=dati["potenza_funz_kw"],
            potenza_fermo_kw=dati["potenza_fermo_kw"],
            scarto_nominale=dati["scarto_nominale"],
        )


@dataclass
class StatoMacchina:
    """Ciò che la macchina "ricorda" da un passo all'altro."""

    fermo_residuo_s: int = 0  # secondi che mancano alla fine del fermo in corso
    causale: str | None = None
    # Frazione di confezione già lavorata ma non ancora completata: evita di perdere i decimali a ogni passo.
    resto: float = 0.0
