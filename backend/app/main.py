"""Punto di ingresso del back-end: crea l'applicazione FastAPI e registra i router sotto il prefisso /api."""

from fastapi import FastAPI

from app.api import anagrafica, sistema

app = FastAPI(
    title="PW 30 — Monitoraggio produzione",
    description="API per rilevazioni, indicatori economico-operativi e alert del pastificio simulato.",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.include_router(sistema.router, prefix="/api")
app.include_router(anagrafica.router, prefix="/api")
