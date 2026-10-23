"""Scenari riconoscibili nello storico, posizionati rispetto alla sua data di fine.

    degrado_trafila      tre settimane, da 6 a 3 settimane prima della fine: lo scarto della trafila sale ogni giorno
                         dall'1% a circa il 6% e la macchina rallenta; dopo la manutenzione del venerdì torna normale.
    mancanze_materiale   la settimana successiva: mancanze di materiale ripetute ogni giorno sull'impastatrice.
    guasto_grave         il mercoledì della settimana dopo le mancanze (12-18 giorni prima della fine): guasto di
                         4-6 ore dell'essiccatoio a partire dalle 8:00.

I periodi non si sovrappongono, così ogni scenario si riconosce da solo nei grafici.
"""

from dataclasses import dataclass
from datetime import date, time, timedelta

from simulatore.calendario import VENERDI
from simulatore.eventi import MINUTI_GIORNATA

NOMI = ("degrado_trafila", "mancanze_materiale", "guasto_grave")

TRAFILA, ESSICCATOIO, IMPASTATRICE = "M2", "M3", "M1"
SCARTO_DEGRADO = (0.01, 0.06)  # scarto della trafila il primo e l'ultimo giorno del degrado
RALLENTAMENTO_DEGRADO = 0.08  # rallentamento aggiuntivo della trafila l'ultimo giorno del degrado
MANCANZE_AL_GIORNO = 6  # frequenza media durante la settimana delle mancanze (normalmente circa 1 a settimana)
INIZIO_GUASTO = time(8, 0)
DURATA_GUASTO_MINUTI = (4 * 60, 6 * 60)


@dataclass(frozen=True)
class Effetto:
    """Come uno scenario modifica una macchina in un giorno; i valori di default lasciano la macchina com'è."""

    scarto: float | None = None  # al posto dello scarto nominale
    rallentamento_extra: float = 0.0  # si aggiunge al rallentamento casuale del 5-12%
    mancanze_al_minuto: float = 0.0  # probabilità aggiuntiva che inizi una mancanza di materiale
    guasto_alle: time | None = None  # inizio di un guasto lungo


class Scenari:
    def __init__(self, fine: date, attivi: set[str]):
        sconosciuti = attivi - set(NOMI)
        if sconosciuti:
            raise ValueError(f"Scenari sconosciuti: {', '.join(sorted(sconosciuti))} (validi: {', '.join(NOMI)})")
        self.attivi = attivi
        # Tutte le date derivano dal lunedì della settimana della fine: così i periodi restano separati qualunque sia
        # il giorno della settimana in cui finisce lo storico.
        lunedi_finale = fine - timedelta(days=fine.weekday())
        # Settimana delle mancanze: la terza prima di quella della fine; il degrado la precede e finisce di venerdì.
        self.mancanze = (lunedi_finale - timedelta(weeks=3), lunedi_finale - timedelta(weeks=3, days=-4))
        fine_degrado = self.mancanze[0] - timedelta(days=7 - VENERDI)
        self.degrado = (fine_degrado - timedelta(days=18), fine_degrado)
        self.giorno_guasto = self.mancanze[0] + timedelta(weeks=1, days=2)

    def effetto(self, codice: str, giorno: date) -> Effetto:
        if "degrado_trafila" in self.attivi and codice == TRAFILA and self.degrado[0] <= giorno <= self.degrado[1]:
            avanzamento = (giorno - self.degrado[0]).days / (self.degrado[1] - self.degrado[0]).days
            minimo, massimo = SCARTO_DEGRADO
            return Effetto(scarto=minimo + (massimo - minimo) * avanzamento,
                           rallentamento_extra=RALLENTAMENTO_DEGRADO * avanzamento)
        if "mancanze_materiale" in self.attivi and codice == IMPASTATRICE and \
                self.mancanze[0] <= giorno <= self.mancanze[1]:
            return Effetto(mancanze_al_minuto=MANCANZE_AL_GIORNO / MINUTI_GIORNATA)
        if "guasto_grave" in self.attivi and codice == ESSICCATOIO and giorno == self.giorno_guasto:
            return Effetto(guasto_alle=INIZIO_GUASTO)
        return Effetto()

    def descrizione(self, nome: str) -> str:
        """Dove cade lo scenario, per il log del generatore."""
        formato = "%d/%m/%Y"
        if nome == "degrado_trafila":
            return f"trafila dal {self.degrado[0]:{formato}} al {self.degrado[1]:{formato}}"
        if nome == "mancanze_materiale":
            return f"impastatrice dal {self.mancanze[0]:{formato}} al {self.mancanze[1]:{formato}}"
        return f"essiccatoio il {self.giorno_guasto:{formato}} dalle {INIZIO_GUASTO:%H:%M}"

    def primo_giorno(self, nome: str) -> date:
        return {"degrado_trafila": self.degrado[0], "mancanze_materiale": self.mancanze[0]}.get(nome, self.giorno_guasto)


def nomi_da_configurazione(testo: str) -> set[str]:
    """Nomi da un elenco separato da virgole, ad esempio "guasto_grave,degrado_trafila"; "nessuno" li esclude."""
    return {n.strip() for n in testo.split(",") if n.strip()} - {"nessuno"}
