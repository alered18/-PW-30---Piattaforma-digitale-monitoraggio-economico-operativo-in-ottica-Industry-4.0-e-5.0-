from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.sessione import sessione
from app.schemi.misure import Misure
from app.servizi import misure

router = APIRouter(tags=["sistema"])


@router.get("/salute", summary="Controllo di vita del back-end")
def salute() -> dict[str, str]:
    return {"stato": "ok"}


@router.get("/sistema/misure", summary="Misure del sistema", response_model=Misure)
def leggi_misure(db: Session = Depends(sessione)):
    """Spazio occupato dal database e da ogni tabella, dimensione media di una rilevazione (in JSON e su disco),
    rilevazioni per intervallo di campionamento, tempi di ricalcolo di un giorno e tempi di risposta delle API
    (ultimi 100 valori di ogni tipo, dall'avvio del back-end). Tempi in millisecondi."""
    return misure.leggi(db)
