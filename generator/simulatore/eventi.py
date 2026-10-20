"""Fermi delle macchine: eventi casuali e fermi da calendario.

Frequenze e durate sono ipotesi plausibili per una linea di pasta secca:
    guasto               circa 1 ogni 3 giorni lavorativi per macchina, 30-120 minuti
    micro-fermata        10-30 per turno per macchina, 1-5 minuti
    mancanza materiale   circa 1 a settimana, solo sull'impastatrice (prima macchina), 15-45 minuti
    setup                cambio formato ogni giorno alle 14:00 su trafila e confezionatrice, 20-40 minuti
    manutenzione         programmata il venerdì dalle 20:00 alle 22:00, a linea ferma
"""

import random

MINUTI_GIORNATA = 16 * 60

# Probabilità che un fermo inizi in un minuto di funzionamento.
PROBABILITA_AL_MINUTO = {
    "guasto": 1 / (3 * MINUTI_GIORNATA),
    "micro_fermata": 20 / (8 * 60),
    "mancanza_materiale": 1 / (5 * MINUTI_GIORNATA),
}
DURATA_MINUTI = {
    "guasto": (30, 120),
    "micro_fermata": (1, 5),
    "mancanza_materiale": (15, 45),
    "setup": (20, 40),
}
MACCHINE_CON_SETUP = {"M2", "M4"}


def fermo_casuale(rng: random.Random, prima_macchina: bool, passo_s: int) -> tuple[str, int] | None:
    """Estrae l'eventuale fermo che inizia in questo passo; restituisce (causale, durata in secondi)."""
    for causale, probabilita in PROBABILITA_AL_MINUTO.items():
        if causale == "mancanza_materiale" and not prima_macchina:
            continue
        if rng.random() < probabilita * passo_s / 60:
            return causale, durata_casuale(rng, causale)
    return None


def durata_casuale(rng: random.Random, causale: str) -> int:
    minimo, massimo = DURATA_MINUTI[causale]
    return rng.randint(minimo, massimo) * 60
