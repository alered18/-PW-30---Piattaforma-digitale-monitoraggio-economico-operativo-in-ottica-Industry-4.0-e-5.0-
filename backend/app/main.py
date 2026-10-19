"""Punto di ingresso del back-end.

Per ora espone solo il controllo di vita usato da Docker Compose; i router delle altre aree
(anagrafica, rilevazioni, KPI, soglie, operatore) saranno registrati qui.
"""

from fastapi import FastAPI

app = FastAPI(
    title="PW 30 — Monitoraggio produzione",
    description="API per rilevazioni, indicatori economico-operativi e alert del pastificio simulato.",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)


@app.get("/api/salute", tags=["sistema"], summary="Controllo di vita del back-end")
def salute() -> dict[str, str]:
    return {"stato": "ok"}
