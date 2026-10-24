"""Punto di ingresso del back-end: crea l'applicazione FastAPI e registra i router sotto il prefisso /api."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api import anagrafica, fermi, kpi, operatore, rilevazioni, sistema, soglie
from app.schemi.errori import messaggio

app = FastAPI(
    title="PW 30 — Monitoraggio produzione",
    description="API per rilevazioni, indicatori economico-operativi e alert del pastificio simulato.",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.include_router(sistema.router, prefix="/api")
app.include_router(anagrafica.router, prefix="/api")
app.include_router(rilevazioni.router, prefix="/api")
app.include_router(kpi.router, prefix="/api")
app.include_router(fermi.router, prefix="/api")
app.include_router(soglie.router, prefix="/api")
app.include_router(operatore.router, prefix="/api")


@app.exception_handler(RequestValidationError)
def richiesta_non_valida(_: Request, errore: RequestValidationError) -> JSONResponse:
    """Errori di formato (campo mancante, testo al posto di un numero...) con un messaggio in italiano."""
    dettagli = [
        {"campo": ".".join(str(p) for p in e["loc"] if p != "body"), "errore": messaggio(e)}
        for e in errore.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": "Richiesta non valida", "errori": dettagli})
