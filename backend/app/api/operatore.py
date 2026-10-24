"""Vista semplificata per l'operatore di linea."""

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.sessione import sessione
from app.schemi.operatore import StatoOperatore
from app.servizi import fermi, operatore
from app.servizi.calendario import FUSO

router = APIRouter(prefix="/operatore", tags=["operatore"])


def ora_attuale() -> datetime:
    """Istante della richiesta; dipendenza separata perché i test possano fissarlo."""
    return datetime.now(FUSO)


@router.get("/stato", summary="Stato della linea nel turno in corso", response_model=StatoOperatore)
def stato(adesso: datetime = Depends(ora_attuale), db: Session = Depends(sessione)):
    """Stato di ogni macchina dall'ultima rilevazione, produzione buona e scarto della linea dall'inizio del turno
    confrontati con l'obiettivo di turno, superamenti di soglia del giorno."""
    oggi = adesso.astimezone(FUSO).date()
    return {**operatore.stato(db, adesso), "alert": fermi.anomalie(db, oggi, oggi, tipo="soglia")}
