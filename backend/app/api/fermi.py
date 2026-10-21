"""Consultazione dei fermi e delle anomalie."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.sessione import sessione
from app.db.tabelle import Anomalia, CausaleFermo, Macchina
from app.schemi.fermi import AnomaliaOut, FermoOut

router = APIRouter(tags=["fermi e anomalie"])


def _filtri(db: Session, da: date, a: date, macchina: str | None):
    if da > a:
        raise HTTPException(status_code=422, detail="La data di inizio è successiva alla data di fine")
    filtro = (select(Anomalia, Macchina.codice).outerjoin(Macchina, Anomalia.macchina_id == Macchina.id)
              .where(Anomalia.data >= da, Anomalia.data <= a))
    if macchina:
        if db.scalar(select(Macchina.id).where(Macchina.codice == macchina)) is None:
            raise HTTPException(status_code=422, detail=f"Macchina '{macchina}' non trovata")
        filtro = filtro.where(Macchina.codice == macchina)
    return filtro


@router.get("/fermi", summary="Elenco dei fermi", response_model=list[FermoOut])
def elenco_fermi(
    da: date = Query(description="Primo giorno incluso"),
    a: date = Query(description="Ultimo giorno incluso"),
    macchina: str | None = Query(default=None, description="Codice macchina, es. M3; assente = tutte"),
    db: Session = Depends(sessione),
):
    """Un fermo è una sequenza di rilevazioni contigue della stessa macchina con la stessa causale. La durata ha la
    precisione dell'intervallo di campionamento (1 minuto nello storico, 5 secondi nel live)."""
    causali = {c.codice: c for c in db.scalars(select(CausaleFermo))}
    righe = db.execute(_filtri(db, da, a, macchina).where(Anomalia.tipo == "fermo")
                       .order_by(Anomalia.inizio, Macchina.ordine))
    return [
        FermoOut(
            macchina=codice, causale=f.causale_codice, descrizione_causale=causali[f.causale_codice].descrizione,
            pianificato=causali[f.causale_codice].pianificata, inizio=f.inizio, fine=f.fine,
            durata_s=round((f.fine - f.inizio).total_seconds()), costo_eur=float(f.valore or 0),
        )
        for f, codice in righe
    ]


@router.get("/anomalie", summary="Elenco delle anomalie", response_model=list[AnomaliaOut])
def elenco_anomalie(
    da: date = Query(description="Primo giorno incluso"),
    a: date = Query(description="Ultimo giorno incluso"),
    tipo: Literal["fermo", "soglia", "dato"] | None = Query(default=None, description="Assente = tutti i tipi"),
    macchina: str | None = Query(default=None, description="Codice macchina, es. M3; assente = tutte e la linea"),
    db: Session = Depends(sessione),
):
    """Fermi, superamenti di soglia dei KPI e dati sospetti (tempo di turno senza rilevazioni, prestazioni oltre il
    100%), dal più recente."""
    filtro = _filtri(db, da, a, macchina)
    if tipo:
        filtro = filtro.where(Anomalia.tipo == tipo)
    righe = db.execute(filtro.order_by(Anomalia.data.desc(), Anomalia.inizio.desc().nulls_last(), Anomalia.id))
    return [
        AnomaliaOut(
            tipo=x.tipo, data=x.data, macchina=codice, inizio=x.inizio, fine=x.fine, causale=x.causale_codice,
            kpi=x.kpi, valore=None if x.valore is None else float(x.valore),
            soglia=None if x.soglia is None else float(x.soglia), descrizione=x.descrizione,
        )
        for x, codice in righe
    ]
