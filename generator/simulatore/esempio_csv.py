"""File CSV di esempio nel formato di import del back-end.

Contiene i primi 20 minuti di una giornata simulata (lunedì 12 gennaio 2026, fuori dallo storico generato di
default) per le 5 macchine, cioè 100 righe valide, seguite da 3 righe volutamente non valide per mostrare come
l'import le scarta e ne spiega il motivo.
"""

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

from simulatore.calendario import APERTURA, FUSO
from simulatore.flusso import Linea
from simulatore.macchina import DatiMacchina

COLONNE = ["macchina", "inizio", "durata_s", "pezzi", "scarti", "t_funz_s", "t_fermo_s", "causale", "kwh",
           "tempo_ciclo_medio_s"]
INIZIO = datetime.combine(datetime(2026, 1, 12).date(), APERTURA, tzinfo=FUSO)
MINUTI = 20


def righe_esempio(macchine: list[DatiMacchina], seme: int) -> list[dict]:
    linea = Linea(macchine, random.Random(seme))
    valide = [r for minuto in range(MINUTI) for r in linea.passo(INIZIO + timedelta(minutes=minuto), 60)]
    dopo = (INIZIO + timedelta(minutes=MINUTI)).isoformat()
    modello = {**valide[0], "inizio": dopo, "pezzi": 30, "scarti": 0, "t_funz_s": 60, "t_fermo_s": 0,
               "causale": None, "kwh": 0.5}
    non_valide = [
        {**modello, "macchina": "M9"},  # macchina inesistente
        {**modello, "macchina": "M2", "scarti": 31},  # più scarti che pezzi
        {**modello, "macchina": "M3", "kwh": "0,5"},  # decimali con la virgola
    ]
    return valide + non_valide


def scrivi(percorso: Path, righe: list[dict]) -> None:
    percorso.parent.mkdir(parents=True, exist_ok=True)
    with percorso.open("w", encoding="utf-8", newline="") as file:
        scrittore = csv.DictWriter(file, fieldnames=COLONNE, lineterminator="\n")
        scrittore.writeheader()
        scrittore.writerows(righe)  # None diventa una cella vuota
