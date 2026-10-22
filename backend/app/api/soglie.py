"""Soglie dei KPI: consultazione e modifica."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.sessione import sessione
from app.db.tabelle import Soglia
from app.schemi.soglie import SogliaCompleta, SogliaModifica
from app.servizi import soglie

router = APIRouter(prefix="/soglie", tags=["soglie"])


def _elenco(db: Session) -> list[SogliaCompleta]:
    return [
        SogliaCompleta(kpi=s.kpi, nome=soglie.KPI_CON_SOGLIA[s.kpi][0], ambito=s.ambito, verso=s.verso,
                       valore=float(s.valore))
        for s in db.scalars(select(Soglia).order_by(Soglia.id))
    ]


@router.get("", summary="Soglie dei KPI", response_model=list[SogliaCompleta])
def elenca(db: Session = Depends(sessione)):
    return _elenco(db)


@router.put("", summary="Modifica le soglie", response_model=list[SogliaCompleta])
def modifica(modifiche: list[SogliaModifica], db: Session = Depends(sessione)):
    """Aggiorna il valore delle soglie indicate (il verso dipende dal KPI e non si modifica) e rivaluta gli alert di
    tutti i giorni memorizzati: alla consultazione successiva KPI e alert riflettono le nuove soglie."""
    for m in modifiche:
        soglia = db.scalars(select(Soglia).where(Soglia.kpi == m.kpi, Soglia.ambito == m.ambito)).one_or_none()
        if soglia is None:
            raise HTTPException(status_code=422, detail=f"Nessuna soglia per '{m.kpi}' ({m.ambito})")
        if soglie.KPI_CON_SOGLIA[m.kpi][1] == "percentuale" and m.valore > 1:
            raise HTTPException(status_code=422, detail=f"La soglia di '{m.kpi}' è una frazione fra 0 e 1")
        soglia.valore = Decimal(str(m.valore))
    soglie.rivaluta_tutto(db)
    db.commit()
    return _elenco(db)
