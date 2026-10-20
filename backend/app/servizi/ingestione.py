"""Ricezione delle rilevazioni: controlli di coerenza e memorizzazione.

I controlli sono gli stessi per i blocchi inviati dal generatore e per le righe importate da CSV. Ogni riga
non valida riceve l'elenco completo dei motivi, in italiano, così chi invia i dati capisce cosa correggere.
"""

from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.tabelle import CausaleFermo, Macchina, Rilevazione
from app.schemi.rilevazioni import RigaScartata, RilevazioneIn
from app.servizi.calendario import SECONDI_GIORNATA, giorno_di, in_turno


@dataclass
class Controllo:
    """Rilevazioni valide pronte da memorizzare e righe scartate con i motivi."""

    valide: list[tuple[int, RilevazioneIn]]  # (indice nel blocco, rilevazione)
    duplicate: int
    scartate: list[RigaScartata]


def _motivi_della_riga(r: RilevazioneIn, macchine: dict[str, int], causali: set[str]) -> list[str]:
    motivi = []
    if r.macchina not in macchine:
        motivi.append(f"macchina '{r.macchina}' inesistente")
    if r.inizio.tzinfo is None:
        motivi.append("l'inizio deve indicare il fuso orario (es. +02:00)")
    if not 0 < r.durata_s <= SECONDI_GIORNATA:
        motivi.append("la durata deve essere maggiore di zero e non superare le 16 ore di turno")
    for campo in ("pezzi", "scarti", "t_funz_s", "t_fermo_s", "kwh"):
        if getattr(r, campo) < 0:
            motivi.append(f"{campo} non può essere negativo")
    if r.scarti > r.pezzi:
        motivi.append("gli scarti non possono superare i pezzi prodotti")
    if r.t_funz_s + r.t_fermo_s != r.durata_s:
        motivi.append("tempo di funzionamento + tempo di fermo deve essere uguale alla durata")
    if r.pezzi > 0 and r.t_funz_s == 0:
        motivi.append("una macchina che non ha funzionato non può aver prodotto pezzi")
    if r.t_fermo_s > 0 and r.causale is None:
        motivi.append("un fermo deve avere una causale")
    if r.t_fermo_s == 0 and r.causale is not None:
        motivi.append("la causale si indica solo se c'è un fermo")
    if r.causale is not None and r.causale not in causali:
        motivi.append(f"causale '{r.causale}' non ammessa (ammesse: {', '.join(sorted(causali))})")
    if r.tempo_ciclo_medio_s is not None and r.tempo_ciclo_medio_s <= 0:
        motivi.append("il tempo ciclo medio deve essere maggiore di zero")
    if r.inizio.tzinfo is not None and 0 < r.durata_s <= SECONDI_GIORNATA and not in_turno(r.inizio, r.durata_s):
        motivi.append("l'intervallo è fuori dall'orario di turno (06:00-22:00, lunedì-venerdì)")
    return motivi


def controlla(db: Session, rilevazioni: list[RilevazioneIn]) -> Controllo:
    """Verifica un blocco di rilevazioni rispetto alle regole e ai dati già memorizzati.

    Una rilevazione con la stessa macchina e lo stesso inizio di una già presente è un duplicato (ad esempio un
    blocco reinviato) e viene ignorata. Un intervallo che si sovrappone a un altro della stessa macchina con un
    inizio diverso è invece un errore: lo stesso tempo verrebbe contato due volte.
    """
    macchine = dict(db.execute(select(Macchina.codice, Macchina.id)).all())
    causali = set(db.scalars(select(CausaleFermo.codice)))

    scartate: list[RigaScartata] = []
    candidate: list[tuple[int, RilevazioneIn]] = []
    for indice, r in enumerate(rilevazioni):
        motivi = _motivi_della_riga(r, macchine, causali)
        if motivi:
            scartate.append(RigaScartata(indice=indice, macchina=r.macchina, inizio=r.inizio, motivi=motivi))
        else:
            candidate.append((indice, r))

    # Per ogni macchina gli intervalli occupati, ordinati per inizio: con la ricerca binaria basta confrontare una
    # rilevazione con l'intervallo che la precede e con quello che la segue (un blocco di storico ne ha migliaia).
    occupati = {codice: sorted(intervalli) for codice, intervalli in _intervalli_esistenti(db, candidate, macchine).items()}
    valide: list[tuple[int, RilevazioneIn]] = []
    duplicate = 0
    for indice, r in sorted(candidate, key=lambda c: (c[1].macchina, c[1].inizio)):
        fine = r.inizio + timedelta(seconds=r.durata_s)
        intervalli = occupati.setdefault(r.macchina, [])
        posizione = bisect_left(intervalli, (r.inizio,))
        if posizione < len(intervalli) and intervalli[posizione][0] == r.inizio:
            duplicate += 1
            continue
        precedente_sovrapposto = posizione > 0 and intervalli[posizione - 1][1] > r.inizio
        successivo_sovrapposto = posizione < len(intervalli) and intervalli[posizione][0] < fine
        if precedente_sovrapposto or successivo_sovrapposto:
            scartate.append(RigaScartata(
                indice=indice, macchina=r.macchina, inizio=r.inizio,
                motivi=["l'intervallo si sovrappone a un'altra rilevazione della stessa macchina"],
            ))
            continue
        intervalli.insert(posizione, (r.inizio, fine))
        valide.append((indice, r))

    scartate.sort(key=lambda s: s.indice)
    valide.sort(key=lambda v: v[0])
    return Controllo(valide=valide, duplicate=duplicate, scartate=scartate)


def _intervalli_esistenti(
    db: Session, candidate: list[tuple[int, RilevazioneIn]], macchine: dict[str, int]
) -> dict[str, list[tuple[datetime, datetime]]]:
    """Intervalli già memorizzati che potrebbero sovrapporsi alle rilevazioni candidate, per macchina.

    Le rilevazioni stanno tutte dentro una giornata di turno, quindi basta cercare a partire da un giorno prima
    dell'inizio più vecchio del blocco.
    """
    risultato: dict[str, list[tuple[datetime, datetime]]] = defaultdict(list)
    if not candidate:
        return risultato
    codici = {r.macchina for _, r in candidate}
    da = min(r.inizio for _, r in candidate) - timedelta(days=1)
    a = max(r.inizio + timedelta(seconds=r.durata_s) for _, r in candidate)
    per_id = {macchine[c]: c for c in codici}
    righe = db.execute(
        select(Rilevazione.macchina_id, Rilevazione.inizio, Rilevazione.durata_s).where(
            Rilevazione.macchina_id.in_(per_id), Rilevazione.inizio >= da, Rilevazione.inizio < a
        )
    )
    for macchina_id, inizio, durata_s in righe:
        risultato[per_id[macchina_id]].append((inizio, inizio + timedelta(seconds=durata_s)))
    return risultato


def memorizza(db: Session, valide: list[tuple[int, RilevazioneIn]], fonte: str = "generatore") -> tuple[int, list[date]]:
    """Inserisce le rilevazioni valide; restituisce quante sono state memorizzate e i giorni toccati."""
    if not valide:
        return 0, []
    macchine = dict(db.execute(select(Macchina.codice, Macchina.id)).all())
    righe = [
        {
            "macchina_id": macchine[r.macchina],
            "inizio": r.inizio,
            "durata_s": r.durata_s,
            "pezzi": r.pezzi,
            "scarti": r.scarti,
            "t_funz_s": r.t_funz_s,
            "t_fermo_s": r.t_fermo_s,
            "causale_codice": r.causale,
            "kwh": r.kwh,
            "tempo_ciclo_medio_s": r.tempo_ciclo_medio_s,
            "fonte": fonte,
        }
        for _, r in valide
    ]
    # Inserimento con executemany del driver psycopg, che invia tutte le righe in sequenza senza attendere la
    # risposta a ognuna (pipeline): un giorno di storico (4.800 righe) richiede una frazione di secondo.
    # Se un'altra richiesta ha appena inserito la stessa rilevazione, il vincolo unico la fa ignorare e non è contata.
    colonne = list(righe[0])
    istruzione = (
        f"INSERT INTO rilevazione ({', '.join(colonne)}) VALUES ({', '.join(['%s'] * len(colonne))}) "
        "ON CONFLICT ON CONSTRAINT rilevazione_unica DO NOTHING"
    )
    with db.connection().connection.cursor() as cursore:
        cursore.executemany(istruzione, [tuple(r[c] for c in colonne) for r in righe])
        memorizzate = cursore.rowcount
    db.commit()
    giorni = sorted({giorno_di(r.inizio) for _, r in valide})
    return memorizzate, giorni
