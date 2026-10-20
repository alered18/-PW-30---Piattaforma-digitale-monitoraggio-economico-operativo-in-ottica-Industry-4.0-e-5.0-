"""Ricezione e consultazione delle rilevazioni."""

from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.sessione import sessione
from app.db.tabelle import Macchina, Rilevazione
from app.schemi.rilevazioni import (
    EsitoIngestione,
    PaginaRilevazioni,
    RilevazioneIn,
    RilevazioneOut,
    UltimaRilevazione,
)
from app.servizi import ingestione, ricalcolo
from app.servizi.calendario import FUSO

router = APIRouter(prefix="/rilevazioni", tags=["rilevazioni"])

MASSIMO_PER_BLOCCO = 10_000


@router.post(
    "",
    summary="Riceve un blocco di rilevazioni",
    response_model=EsitoIngestione,
    responses={422: {"model": EsitoIngestione, "description": "Blocco rifiutato: almeno una rilevazione non valida"}},
)
def ricevi(rilevazioni: list[RilevazioneIn], db: Session = Depends(sessione)):
    """Il blocco è accettato o rifiutato per intero: se anche una sola rilevazione non è valida non si memorizza
    nulla e la risposta elenca tutte le righe da correggere con i motivi. Le rilevazioni già presenti (stessa
    macchina e stesso inizio) sono ignorate e contate tra i duplicati, così reinviare un blocco non fa danni.
    Dopo la memorizzazione si ricalcolano produzione giornaliera e indicatori dei giorni toccati."""
    if len(rilevazioni) > MASSIMO_PER_BLOCCO:
        raise HTTPException(status_code=422, detail=f"Al massimo {MASSIMO_PER_BLOCCO} rilevazioni per blocco")
    controllo = ingestione.controlla(db, rilevazioni)
    if controllo.scartate:
        esito = EsitoIngestione(
            ricevute=len(rilevazioni), memorizzate=0, duplicate=controllo.duplicate,
            scartate=controllo.scartate, giorni_toccati=[],
        )
        return JSONResponse(status_code=422, content=esito.model_dump(mode="json"))
    memorizzate, giorni = ingestione.memorizza(db, controllo.valide)
    # I KPI dei giorni toccati si aggiornano subito, così la dashboard vede i dati nuovi.
    ricalcolo.ricalcola(db, giorni)
    return EsitoIngestione(
        ricevute=len(rilevazioni),
        memorizzate=memorizzate,
        duplicate=controllo.duplicate + len(controllo.valide) - memorizzate,
        scartate=[],
        giorni_toccati=giorni,
    )


def _uscita(r: Rilevazione, codice: str) -> RilevazioneOut:
    return RilevazioneOut(
        macchina=codice, inizio=r.inizio, durata_s=r.durata_s, pezzi=r.pezzi, scarti=r.scarti,
        t_funz_s=r.t_funz_s, t_fermo_s=r.t_fermo_s, causale=r.causale_codice, kwh=float(r.kwh),
        tempo_ciclo_medio_s=None if r.tempo_ciclo_medio_s is None else float(r.tempo_ciclo_medio_s),
        fonte=r.fonte,
    )


@router.get("", summary="Consulta le rilevazioni", response_model=PaginaRilevazioni)
def consulta(
    macchina: str | None = Query(default=None, description="Codice macchina, es. M3"),
    da: date | None = Query(default=None, description="Primo giorno incluso"),
    a: date | None = Query(default=None, description="Ultimo giorno incluso"),
    pagina: int = Query(default=1, ge=1),
    dimensione: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(sessione),
):
    if da and a and da > a:
        raise HTTPException(status_code=422, detail="La data di inizio è successiva alla data di fine")
    filtro = select(Rilevazione, Macchina.codice).join(Macchina)
    if macchina:
        filtro = filtro.where(Macchina.codice == macchina)
    if da:
        filtro = filtro.where(Rilevazione.inizio >= datetime.combine(da, time(), tzinfo=FUSO))
    if a:
        filtro = filtro.where(Rilevazione.inizio < datetime.combine(a + timedelta(days=1), time(), tzinfo=FUSO))
    totale = db.scalar(select(func.count()).select_from(filtro.subquery()))
    righe = db.execute(
        filtro.order_by(Rilevazione.inizio, Macchina.ordine).offset((pagina - 1) * dimensione).limit(dimensione)
    )
    return PaginaRilevazioni(
        totale=totale, pagina=pagina, dimensione=dimensione,
        elementi=[_uscita(r, codice) for r, codice in righe],
    )


@router.get("/ultime", summary="Ultima rilevazione di ogni macchina", response_model=list[UltimaRilevazione])
def ultime(db: Session = Depends(sessione)):
    """Serve al generatore per sapere da dove riprendere e alla vista operatore per lo stato delle macchine."""
    risultato = []
    for m in db.scalars(select(Macchina).order_by(Macchina.ordine)):
        r = db.scalars(
            select(Rilevazione).where(Rilevazione.macchina_id == m.id).order_by(Rilevazione.inizio.desc()).limit(1)
        ).first()
        risultato.append(UltimaRilevazione(macchina=m.codice, ultima=_uscita(r, m.codice) if r else None))
    return risultato
