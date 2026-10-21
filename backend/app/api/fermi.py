"""Consultazione dei fermi e delle anomalie."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.sessione import sessione
from app.db.tabelle import Anomalia, CausaleFermo, Macchina
from app.schemi.fermi import AnomaliaOut, CausaleRipartita, FermoOut

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


@router.get("/fermi/ripartizione", summary="Fermi per causale", response_model=list[CausaleRipartita])
def ripartizione_fermi(
    da: date = Query(description="Primo giorno incluso"),
    a: date = Query(description="Ultimo giorno incluso"),
    ambito: str = Query(default="linea", description="'linea' (tutte le macchine) oppure il codice di una macchina"),
    db: Session = Depends(sessione),
):
    """Numero, durata e costo dei fermi di ogni causale nel periodo, dalla causale con più tempo di fermo: sono i dati
    del diagramma di Pareto. I totali coincidono con la somma dell'elenco dei fermi con gli stessi filtri."""
    filtro = _filtri(db, da, a, None if ambito == "linea" else ambito).where(Anomalia.tipo == "fermo").subquery()
    durata = func.sum(func.extract("epoch", filtro.c.fine - filtro.c.inizio))
    righe = db.execute(
        select(CausaleFermo, func.count(), durata, func.sum(filtro.c.valore))
        .join(filtro, filtro.c.causale_codice == CausaleFermo.codice)
        .group_by(CausaleFermo.codice)
        .order_by(durata.desc(), CausaleFermo.codice)
    )
    return [
        CausaleRipartita(causale=c.codice, descrizione_causale=c.descrizione, pianificato=c.pianificata, n_fermi=n,
                         durata_s=round(secondi), costo_eur=round(float(costo or 0), 2))
        for c, n, secondi, costo in righe
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
