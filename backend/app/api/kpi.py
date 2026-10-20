"""Indicatori: consultazione per periodo e ricalcolo su richiesta."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.sessione import sessione
from app.db.tabelle import Macchina
from app.schemi.kpi import RispostaKpi
from app.servizi import kpi, ricalcolo

router = APIRouter(prefix="/kpi", tags=["kpi"])


def _controlla_intervallo(da: date, a: date) -> None:
    if da > a:
        raise HTTPException(status_code=422, detail="La data di inizio è successiva alla data di fine")


@router.get("", summary="KPI per periodo", response_model=RispostaKpi)
def consulta(
    da: date = Query(description="Primo giorno incluso"),
    a: date = Query(description="Ultimo giorno incluso"),
    ambito: str = Query(default="linea", description="'linea' oppure il codice di una macchina (M1…M5)"),
    granularita: Literal["giorno", "settimana", "mese"] = Query(default="giorno"),
    db: Session = Depends(sessione),
):
    """Serie dei KPI per giorno, settimana o mese e totale dell'intervallo. I giorni senza turni o senza dati non
    compaiono nella serie (non sono punti a zero). Se un giorno passato è rimasto incompleto (ad esempio il
    generatore si è fermato prima della fine del turno) viene ricalcolato prima della lettura."""
    _controlla_intervallo(da, a)
    codici = set(db.scalars(select(Macchina.codice)))
    if ambito != "linea" and ambito not in codici:
        raise HTTPException(status_code=422, detail=f"Ambito '{ambito}' non valido: usare 'linea' o {', '.join(sorted(codici))}")
    return kpi.leggi(db, ambito, da, a, granularita)


class EsitoRicalcolo(BaseModel):
    giorni_ricalcolati: list[date]


@router.post("/ricalcola", summary="Ricalcola gli indicatori di un periodo", response_model=EsitoRicalcolo)
def ricalcola(
    da: date = Query(description="Primo giorno incluso"),
    a: date = Query(description="Ultimo giorno incluso"),
    db: Session = Depends(sessione),
):
    """Da usare dopo una modifica dei parametri economici: gli indicatori già memorizzati non cambiano da soli."""
    _controlla_intervallo(da, a)
    return EsitoRicalcolo(giorni_ricalcolati=ricalcolo.ricalcola(db, ricalcolo.giorni_con_dati(db, da, a)))
