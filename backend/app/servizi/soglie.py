"""Soglie dei KPI e alert.

Ogni soglia riguarda un KPI per la linea o per le macchine e ha un verso: "min" (fuori soglia se il valore è
inferiore, ad esempio l'OEE) o "max" (fuori soglia se è superiore, ad esempio lo scarto). La stessa funzione `valuta`
serve sia all'API dei KPI, che indica lo stato di ogni valore a qualunque granularità, sia al ricalcolo, che registra
i superamenti giornalieri come anomalie di tipo "soglia" (gli alert).
"""

from dataclasses import dataclass
from datetime import date
from typing import Literal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.tabelle import Anomalia, Indicatore, Macchina, Soglia

Stato = Literal["ok", "fuori_soglia", "nd"]

# Nome leggibile e formato dei KPI che possono avere una soglia.
KPI_CON_SOGLIA: dict[str, tuple[str, str]] = {
    "oee": ("OEE", "percentuale"),
    "disponibilita": ("Disponibilità", "percentuale"),
    "tasso_scarto": ("Incidenza degli scarti", "percentuale"),
    "saturazione": ("Saturazione", "percentuale"),
    "kwh_conf": ("Consumo per confezione", "kwh_conf"),
    "costo_fermi_eur": ("Costo dei fermi", "euro"),
}

# KPI che sono somme di un giorno (€/giorno): la soglia ha senso solo a granularità giorno, non su una settimana.
KPI_GIORNALIERI = {"costo_fermi_eur"}

# Decimali con cui i KPI sono memorizzati negli indicatori (le percentuali ne hanno 5): il valore si arrotonda prima
# del confronto, così ricalcolo, rivalutazione dopo una modifica e API dei KPI danno sempre lo stesso esito.
DECIMALI = {"kwh_conf": 6, "costo_fermi_eur": 2}


@dataclass(frozen=True)
class RegolaSoglia:
    kpi: str
    verso: Literal["min", "max"]
    valore: float


def valuta(valore: float | None, regola: RegolaSoglia) -> Stato:
    """Stato di un valore rispetto alla soglia; un KPI non calcolabile non è mai fuori soglia."""
    if valore is None:
        return "nd"
    valore = round(valore, DECIMALI.get(regola.kpi, 5))
    fuori = valore < regola.valore if regola.verso == "min" else valore > regola.valore
    return "fuori_soglia" if fuori else "ok"


def regole(db: Session, ambito: str) -> list[RegolaSoglia]:
    """Soglie per la linea (`ambito` = 'linea') o per le macchine (qualunque codice macchina)."""
    tipo = "linea" if ambito == "linea" else "macchina"
    return [RegolaSoglia(s.kpi, s.verso, float(s.valore))
            for s in db.scalars(select(Soglia).where(Soglia.ambito == tipo).order_by(Soglia.id))]


def stati(valori: dict, regole_ambito: list[RegolaSoglia], un_giorno: bool) -> dict[str, Stato]:
    """Stato dei KPI che hanno una soglia; i KPI giornalieri si valutano solo se il periodo è un giorno."""
    return {r.kpi: valuta(valori.get(r.kpi), r) for r in regole_ambito if un_giorno or r.kpi not in KPI_GIORNALIERI}


def ricostruisci(db: Session, giorno: date, indicatori: list[tuple[Macchina | None, dict]]) -> None:
    """Riscrive gli alert del giorno a partire dai KPI giornalieri di linea (macchina None) e macchine."""
    db.execute(delete(Anomalia).where(Anomalia.data == giorno, Anomalia.tipo == "soglia"))
    per_tipo = {tipo: regole(db, tipo) for tipo in ("linea", "macchina")}
    for macchina, valori in indicatori:
        for regola in per_tipo["linea" if macchina is None else "macchina"]:
            valore = valori.get(regola.kpi)
            if valuta(valore, regola) != "fuori_soglia":
                continue
            nome, formato = KPI_CON_SOGLIA.get(regola.kpi, (regola.kpi, ""))
            confronto = "sotto la soglia minima" if regola.verso == "min" else "sopra la soglia massima"
            db.add(Anomalia(
                tipo="soglia", data=giorno, macchina_id=macchina.id if macchina else None, kpi=regola.kpi,
                valore=round(valore, 4), soglia=regola.valore,
                descrizione=f"{macchina.codice if macchina else 'Linea'}: {nome} {_formatta(valore, formato)} "
                            f"{confronto} di {_formatta(regola.valore, formato)}",
            ))


def rivaluta_tutto(db: Session) -> None:
    """Dopo una modifica delle soglie: ricostruisce gli alert di tutti i giorni dagli indicatori memorizzati."""
    macchine = {m.id: m for m in db.scalars(select(Macchina))}
    per_giorno: dict[date, list[tuple[Macchina | None, dict]]] = {}
    for i in db.scalars(select(Indicatore)):
        valori = {kpi: None if getattr(i, kpi) is None else float(getattr(i, kpi)) for kpi in KPI_CON_SOGLIA}
        per_giorno.setdefault(i.data, []).append((macchine.get(i.macchina_id), valori))
    for giorno, indicatori in per_giorno.items():
        ricostruisci(db, giorno, indicatori)


def _formatta(valore: float, formato: str) -> str:
    """Numeri all'italiana per le descrizioni degli alert: 58,2% · 0,261 kWh/conf · 2.731,40 €."""
    def italiano(testo: str) -> str:
        return testo.replace(",", "§").replace(".", ",").replace("§", ".")

    if formato == "percentuale":
        return italiano(f"{valore * 100:.1f}%")
    if formato == "euro":
        return italiano(f"{valore:,.2f} €")
    if formato == "kwh_conf":
        return italiano(f"{valore:.3f} kWh/conf")
    return italiano(f"{valore:,.2f}")
