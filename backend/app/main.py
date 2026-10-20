"""Punto di ingresso del back-end: crea l'applicazione FastAPI e registra i router sotto il prefisso /api."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api import anagrafica, kpi, rilevazioni, sistema

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


# Traduzione dei tipi di errore più frequenti; per gli altri resta il messaggio originale.
MESSAGGI = {
    "missing": "campo obbligatorio mancante",
    "int_parsing": "deve essere un numero intero",
    "int_from_float": "deve essere un numero intero",
    "float_parsing": "deve essere un numero",
    "finite_number": "deve essere un numero finito",
    "datetime_parsing": "data e ora non valide (formato atteso: 2026-10-19T08:00:00+02:00)",
    "datetime_from_date_parsing": "data e ora non valide (formato atteso: 2026-10-19T08:00:00+02:00)",
    "date_parsing": "data non valida (formato atteso: 2026-10-19)",
    "date_from_datetime_parsing": "data non valida (formato atteso: 2026-10-19)",
    "string_type": "deve essere un testo",
    "list_type": "deve essere un elenco",
    "greater_than_equal": "valore troppo piccolo",
    "less_than": "valore troppo grande",
    "less_than_equal": "valore troppo grande",
}


@app.exception_handler(RequestValidationError)
def richiesta_non_valida(_: Request, errore: RequestValidationError) -> JSONResponse:
    """Errori di formato (campo mancante, testo al posto di un numero...) con un messaggio in italiano."""
    dettagli = [
        {"campo": ".".join(str(p) for p in e["loc"] if p != "body"), "errore": MESSAGGI.get(e["type"], e["msg"])}
        for e in errore.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": "Richiesta non valida", "errori": dettagli})
