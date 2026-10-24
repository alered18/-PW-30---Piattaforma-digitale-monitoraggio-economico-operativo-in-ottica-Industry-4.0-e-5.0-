"""Import di rilevazioni da file CSV.

Formato: testo UTF-8, valori separati da virgola, decimali con il punto, una rilevazione per riga e un'intestazione
con queste colonne (in qualunque ordine), le stesse dell'API:

    macchina,inizio,durata_s,pezzi,scarti,t_funz_s,t_fermo_s,causale,kwh,tempo_ciclo_medio_s
    M1,2026-01-12T06:00:00+01:00,60,38,0,60,0,,0.51,1.5789

`causale` e `tempo_ciclo_medio_s` possono restare vuote. A differenza dei blocchi inviati dal generatore, che sono
accettati o rifiutati per intero, l'import memorizza le righe valide e restituisce le altre con il numero di riga e
i motivi: chi carica un file vede subito quali righe correggere.
"""

import csv
import io

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.schemi.errori import messaggio
from app.schemi.rilevazioni import RigaCsvScartata, RilevazioneIn
from app.servizi import ingestione, ricalcolo

COLONNE = ("macchina", "inizio", "durata_s", "pezzi", "scarti", "t_funz_s", "t_fermo_s", "causale", "kwh",
           "tempo_ciclo_medio_s")
MASSIMO_RIGHE = 10_000
MASSIMO_BYTE = 5_000_000  # circa 40.000 righe: il limite delle righe scatta prima


class FileNonValido(ValueError):
    """Il file non si può importare (codifica, intestazione, dimensione): nessuna riga viene memorizzata."""


def _motivi_di_formato(errore: ValidationError) -> list[str]:
    motivi = []
    for e in errore.errors():
        testo = messaggio(e)
        if e["type"] == "float_parsing":
            testo += " (per i decimali si usa il punto)"
        motivi.append(f"{e['loc'][0]}: {testo}")
    return motivi


def leggi(contenuto: bytes) -> tuple[list[tuple[int, str, RilevazioneIn]], list[RigaCsvScartata]]:
    """Righe lette dal file: (numero di riga, inizio come scritto, rilevazione) per quelle ben formate, scartate le
    altre."""
    if len(contenuto) > MASSIMO_BYTE:
        raise FileNonValido(f"Il file supera i {MASSIMO_BYTE // 1_000_000} MB")
    try:
        testo = contenuto.decode("utf-8-sig")  # -sig: accetta anche il BOM che Excel aggiunge salvando in UTF-8
    except UnicodeDecodeError:
        raise FileNonValido("Il file deve essere un testo in codifica UTF-8") from None
    lettore = csv.DictReader(io.StringIO(testo))
    intestazione = [c.strip() for c in lettore.fieldnames or []]
    if not intestazione:
        raise FileNonValido("Il file è vuoto")
    if len(intestazione) == 1 and ";" in intestazione[0]:
        # Excel con le impostazioni italiane salva i CSV con il punto e virgola.
        raise FileNonValido("I valori devono essere separati da virgole, non da punti e virgola")
    ripetute = sorted({c for c in intestazione if intestazione.count(c) > 1})
    if ripetute:
        raise FileNonValido(f"Intestazione non valida: colonne ripetute {', '.join(ripetute)}")
    mancanti = [c for c in COLONNE if c not in intestazione]
    in_piu = [c for c in intestazione if c not in COLONNE]
    if mancanti or in_piu:
        dettagli = ([f"mancano {', '.join(mancanti)}"] if mancanti else []) + \
                   ([f"colonne non previste: {', '.join(in_piu)}"] if in_piu else [])
        raise FileNonValido(f"Intestazione non valida ({'; '.join(dettagli)}). Colonne attese: {','.join(COLONNE)}")
    lettore.fieldnames = intestazione

    lette: list[tuple[int, str, RilevazioneIn]] = []
    scartate: list[RigaCsvScartata] = []
    for valori in lettore:
        if len(lette) + len(scartate) >= MASSIMO_RIGHE:
            raise FileNonValido(f"Al massimo {MASSIMO_RIGHE} righe per file")
        riga = lettore.line_num
        macchina, inizio = valori.get("macchina"), valori.get("inizio")
        # DictReader mette i valori in più sotto la chiave None e lascia a None le colonne senza valore.
        if None in valori or any(v is None for v in valori.values()):
            scartate.append(RigaCsvScartata(riga=riga, macchina=macchina, inizio=inizio,
                                            motivi=[f"la riga deve avere {len(COLONNE)} valori separati da virgola"]))
            continue
        campi = {c: v.strip() or None for c, v in valori.items()}  # una cella vuota è un valore assente
        try:
            lette.append((riga, inizio, RilevazioneIn.model_validate(campi)))
        except ValidationError as errore:
            scartate.append(RigaCsvScartata(riga=riga, macchina=macchina, inizio=inizio,
                                            motivi=_motivi_di_formato(errore)))
    return lette, scartate


def importa(db: Session, contenuto: bytes) -> dict:
    """Legge il file, applica gli stessi controlli dei blocchi del generatore e memorizza le righe valide."""
    lette, scartate = leggi(contenuto)
    righe = len(lette) + len(scartate)
    controllo = ingestione.controlla(db, [r for _, _, r in lette])
    # Gli indici del controllo si riferiscono all'elenco delle righe lette: si riportano ai numeri di riga del file.
    for s in controllo.scartate:
        riga, inizio, r = lette[s.indice]
        scartate.append(RigaCsvScartata(riga=riga, macchina=r.macchina, inizio=inizio, motivi=s.motivi))
    memorizzate, giorni = ingestione.memorizza(db, controllo.valide, fonte="csv")
    ricalcolo.ricalcola(db, giorni)
    return {
        "righe": righe,
        "memorizzate": memorizzate,
        "duplicate": controllo.duplicate + len(controllo.valide) - memorizzate,
        "scartate": sorted(scartate, key=lambda s: s.riga),
        "giorni_toccati": giorni,
    }
