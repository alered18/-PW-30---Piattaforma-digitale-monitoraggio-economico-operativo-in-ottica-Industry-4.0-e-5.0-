"""Indicatori: ricalcolo su richiesta."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.sessione import sessione
from app.servizi import ricalcolo

router = APIRouter(prefix="/kpi", tags=["kpi"])


class EsitoRicalcolo(BaseModel):
    giorni_ricalcolati: list[date]


@router.post("/ricalcola", summary="Ricalcola gli indicatori di un periodo", response_model=EsitoRicalcolo)
def ricalcola(
    da: date = Query(description="Primo giorno incluso"),
    a: date = Query(description="Ultimo giorno incluso"),
    db: Session = Depends(sessione),
):
    """Da usare dopo una modifica dei parametri economici: gli indicatori già memorizzati non cambiano da soli."""
    if da > a:
        raise HTTPException(status_code=422, detail="La data di inizio è successiva alla data di fine")
    return EsitoRicalcolo(giorni_ricalcolati=ricalcolo.ricalcola(db, ricalcolo.giorni_con_dati(db, da, a)))
