"""Dati di base: linea, macchine, causali di fermo e parametri economici."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.sessione import sessione
from app.db.tabelle import CausaleFermo, Linea, Macchina, Parametro
from app.schemi.anagrafica import CausaleOut, LineaOut, MacchinaOut, ParametroModifica, ParametroOut

router = APIRouter(tags=["anagrafica"])


@router.get("/linee", summary="Linee di produzione", response_model=list[LineaOut])
def elenca_linee(db: Session = Depends(sessione)):
    return db.scalars(select(Linea).order_by(Linea.codice)).all()


@router.get("/macchine", summary="Macchine nell'ordine della linea", response_model=list[MacchinaOut])
def elenca_macchine(db: Session = Depends(sessione)):
    return db.scalars(select(Macchina).order_by(Macchina.linea_id, Macchina.ordine)).all()


@router.get("/causali", summary="Causali di fermo ammesse", response_model=list[CausaleOut])
def elenca_causali(db: Session = Depends(sessione)):
    return db.scalars(select(CausaleFermo).order_by(CausaleFermo.codice)).all()


@router.get("/parametri", summary="Parametri economici e operativi", response_model=list[ParametroOut])
def elenca_parametri(db: Session = Depends(sessione)):
    return db.scalars(select(Parametro).order_by(Parametro.chiave)).all()


@router.put("/parametri/{chiave}", summary="Modifica un parametro", response_model=ParametroOut)
def modifica_parametro(chiave: str, modifica: ParametroModifica, db: Session = Depends(sessione)):
    parametro = db.get(Parametro, chiave)
    if parametro is None:
        raise HTTPException(status_code=404, detail=f"Parametro '{chiave}' inesistente")
    parametro.valore = Decimal(str(modifica.valore))
    db.commit()
    return parametro
