"""Misure del sistema: tempi di risposta, tempi di ricalcolo, spazio occupato nel database.

I tempi sono tenuti in memoria (gli ultimi valori di ogni tipo) e scritti nel log del back-end; si azzerano al
riavvio. Le dimensioni si leggono da PostgreSQL al momento della richiesta.
"""

import json
import logging
import statistics
from collections import defaultdict, deque
from datetime import date, datetime

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db.tabelle import Macchina, Rilevazione

log = logging.getLogger("misure")

ULTIME = 100  # valori conservati per ogni tipo di richiesta e per i ricalcoli
TABELLE = ("rilevazione", "produzione_giornaliera", "indicatore", "anomalia", "soglia", "parametro", "macchina",
           "causale_fermo", "linea")
CAMPIONE = 1000  # rilevazioni usate per stimare la dimensione media in JSON

_richieste: dict[str, deque[tuple[float, int]]] = defaultdict(lambda: deque(maxlen=ULTIME))
_ricalcoli: deque[tuple[date, float]] = deque(maxlen=ULTIME)


def registra_richiesta(chiave: str, durata_ms: float, byte_risposta: int) -> None:
    _richieste[chiave].append((durata_ms, byte_risposta))
    log.info("%s %.1f ms, %d byte", chiave, durata_ms, byte_risposta)


def registra_ricalcolo(giorno: date, durata_ms: float) -> None:
    _ricalcoli.append((giorno, durata_ms))
    log.info("ricalcolo del %s: %.1f ms", giorno, durata_ms)


def _statistiche(valori: list[float]) -> dict:
    return {"n": len(valori), "media": round(statistics.fmean(valori), 1), "mediana": round(statistics.median(valori), 1),
            "massimo": round(max(valori), 1), "ultimo": round(valori[-1], 1)}


def _tabelle(db: Session) -> list[dict]:
    risultato = []
    for nome in TABELLE:  # nomi fissi, non input dell'utente
        righe = db.scalar(text(f"SELECT count(*) FROM {nome}"))
        dati, totale = db.execute(text(
            "SELECT pg_relation_size(:t), pg_total_relation_size(:t)"), {"t": nome}).one()
        risultato.append({"tabella": nome, "righe": righe, "byte_dati": dati, "byte_totali": totale,
                          "byte_per_riga": round(totale / righe, 1) if righe else None})
    return risultato


def _rilevazione_media(db: Session) -> dict:
    """Dimensione media di una rilevazione: nel formato JSON con cui arriva e come riga memorizzata."""
    ultime = db.execute(select(Rilevazione, Macchina.codice).join(Macchina)
                        .order_by(Rilevazione.inizio.desc()).limit(CAMPIONE)).all()
    # Stesso formato inviato dal generatore (chiavi e valori come nell'API, senza spazi).
    json_byte = [len(json.dumps({
        "macchina": codice, "inizio": r.inizio.isoformat(), "durata_s": r.durata_s, "pezzi": r.pezzi,
        "scarti": r.scarti, "t_funz_s": r.t_funz_s, "t_fermo_s": r.t_fermo_s, "causale": r.causale_codice,
        "kwh": float(r.kwh), "tempo_ciclo_medio_s": None if r.tempo_ciclo_medio_s is None else float(r.tempo_ciclo_medio_s),
    }, separators=(",", ":")).encode()) for r, codice in ultime]
    # pg_column_size di una riga intera: byte della tupla su disco, senza intestazione di pagina e indici.
    tupla = db.scalar(text("SELECT avg(pg_column_size(r.*)) FROM rilevazione r"))
    return {"byte_json": round(statistics.fmean(json_byte), 1) if json_byte else None,
            "byte_tupla": None if tupla is None else round(float(tupla), 1)}


def leggi(db: Session) -> dict:
    # Copie delle code: le richieste in corso su altri thread possono aggiungere valori mentre si calcolano le medie.
    ricalcoli = list(_ricalcoli)
    richieste = {chiave: list(v) for chiave, v in list(_richieste.items())}
    intervalli = db.execute(select(Rilevazione.durata_s, func.count()).group_by(Rilevazione.durata_s)
                            .order_by(Rilevazione.durata_s)).all()
    return {
        "misurato_il": datetime.now().astimezone(),
        "database_byte": db.scalar(text("SELECT pg_database_size(current_database())")),
        "tabelle": _tabelle(db),
        "rilevazione": _rilevazione_media(db),
        # Quante rilevazioni per durata dell'intervallo: 60 s nello storico, 5 s nel live (frequenza di campionamento).
        "campionamento": [{"durata_s": d, "rilevazioni": n} for d, n in intervalli],
        "ricalcolo_giorno_ms": _statistiche([ms for _, ms in ricalcoli]) if ricalcoli else None,
        "richieste_ms": {chiave: _statistiche([ms for ms, _ in v]) | {"byte_medi": round(statistics.fmean(b for _, b in v))}
                         for chiave, v in sorted(richieste.items())},
    }
