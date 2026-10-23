"""La linea come flusso di confezioni tra macchine in serie, separate da buffer.

A ogni passo ogni macchina, dalla prima all'ultima, lavora per il tempo in cui non è ferma. Quanto produce è il
minimo fra tre limiti:
    * la sua velocità effettiva (tempo ciclo ideale più un rallentamento casuale del 5-12%);
    * il materiale disponibile nel buffer a monte (la prima macchina ha materia prima illimitata);
    * lo spazio libero nel buffer a valle (l'ultima macchina scarica senza limiti).
Così le macchine più veloci restano a volte senza materiale o bloccate, e l'uscita della linea segue il ritmo della
macchina più lenta. Quel tempo non è un fermo con causale: si vede come calo delle prestazioni.
I pezzi scartati escono dal flusso; quelli buoni passano al buffer della macchina successiva.
Gli scenari, se presenti, modificano per alcuni giorni lo scarto, la velocità o i fermi di una macchina.
"""

import math
import random
from collections.abc import Iterator
from datetime import date, datetime, timedelta

from simulatore import eventi
from simulatore.calendario import CAMBIO_TURNO, FUSO, INIZIO_MANUTENZIONE, VENERDI, lavorativo, passi_del_giorno
from simulatore.macchina import DatiMacchina, StatoMacchina
from simulatore.scenari import DURATA_GUASTO_MINUTI, Effetto, Scenari

BUFFER_MINUTI = 10  # ogni buffer contiene circa 10 minuti di produzione della macchina più lenta
RALLENTAMENTO = (0.05, 0.12)
VARIAZIONE_ENERGIA = (0.97, 1.03)


class Linea:
    def __init__(self, macchine: list[DatiMacchina], rng: random.Random, scenari: Scenari | None = None):
        self.macchine = sorted(macchine, key=lambda m: m.ordine)
        self.rng = rng
        self.scenari = scenari
        self.stati = {m.codice: StatoMacchina() for m in self.macchine}
        self.capacita_buffer = min(m.capacita_conf_h for m in self.macchine) * BUFFER_MINUTI / 60
        # buffer[i] è il materiale in attesa davanti alla macchina i; si parte a metà, come una linea già avviata.
        self.buffer = [self.capacita_buffer / 2] * len(self.macchine)

    def passo(self, inizio: datetime, passo_s: int) -> list[dict]:
        """Simula un intervallo e restituisce una rilevazione per macchina."""
        giorno = inizio.astimezone(FUSO).date()
        effetti = {
            m.codice: self.scenari.effetto(m.codice, giorno) if self.scenari else Effetto() for m in self.macchine
        }
        self._fermi_da_calendario(inizio, effetti)
        rilevazioni = []
        for i, m in enumerate(self.macchine):
            stato = self.stati[m.codice]
            effetto = effetti[m.codice]
            t_fermo, causale = self._fermo_nel_passo(stato, i == 0, passo_s, effetto.mancanze_al_minuto)
            t_funz = passo_s - t_fermo

            rallentamento = self.rng.uniform(*RALLENTAMENTO) + effetto.rallentamento_extra
            velocita = t_funz / (m.tempo_ciclo_ideale_s * (1 + rallentamento)) + stato.resto
            disponibile = math.inf if i == 0 else self.buffer[i]
            spazio = math.inf if i == len(self.macchine) - 1 else self.capacita_buffer - self.buffer[i + 1]
            pezzi = int(min(velocita, disponibile, spazio))
            # Il resto si conserva solo se a limitare è stata la velocità della macchina.
            stato.resto = velocita - pezzi if velocita <= min(disponibile, spazio) else 0.0
            scarto = m.scarto_nominale if effetto.scarto is None else effetto.scarto
            scarti = self.rng.binomialvariate(pezzi, scarto) if pezzi else 0

            if i > 0:
                self.buffer[i] -= pezzi
            if i < len(self.macchine) - 1:
                self.buffer[i + 1] += pezzi - scarti

            kwh = (m.potenza_funz_kw * t_funz + m.potenza_fermo_kw * t_fermo) / 3600
            rilevazioni.append({
                "macchina": m.codice,
                "inizio": inizio.isoformat(),
                "durata_s": passo_s,
                "pezzi": pezzi,
                "scarti": scarti,
                "t_funz_s": t_funz,
                "t_fermo_s": t_fermo,
                "causale": causale,
                "kwh": round(kwh * self.rng.uniform(*VARIAZIONE_ENERGIA), 4),
                "tempo_ciclo_medio_s": round(t_funz / pezzi, 4) if pezzi else None,
            })
        return rilevazioni

    def fine_giornata(self) -> None:
        """A fine turno i fermi in corso si chiudono: la riparazione si completa fuori orario."""
        for stato in self.stati.values():
            stato.fermo_residuo_s, stato.causale = 0, None

    def _fermi_da_calendario(self, inizio: datetime, effetti: dict[str, Effetto]) -> None:
        ora = inizio.astimezone(FUSO).time()
        for codice, effetto in effetti.items():
            if effetto.guasto_alle == ora:
                self._avvia_fermo(codice, "guasto", self.rng.randint(*DURATA_GUASTO_MINUTI) * 60)
        if ora == CAMBIO_TURNO:
            for m in self.macchine:
                if m.codice in eventi.MACCHINE_CON_SETUP and not self.stati[m.codice].fermo_residuo_s:
                    self._avvia_fermo(m.codice, "setup", eventi.durata_casuale(self.rng, "setup"))
        if inizio.astimezone(FUSO).weekday() == VENERDI and ora == INIZIO_MANUTENZIONE:
            for m in self.macchine:
                self._avvia_fermo(m.codice, "manutenzione", 2 * 3600)

    def _avvia_fermo(self, codice: str, causale: str, durata_s: int) -> None:
        stato = self.stati[codice]
        stato.fermo_residuo_s, stato.causale = durata_s, causale

    def _fermo_nel_passo(
        self, stato: StatoMacchina, prima_macchina: bool, passo_s: int, mancanze_extra: float
    ) -> tuple[int, str | None]:
        if not stato.fermo_residuo_s:
            nuovo = eventi.fermo_casuale(self.rng, prima_macchina, passo_s, mancanze_extra)
            if nuovo is None:
                return 0, None
            stato.causale, stato.fermo_residuo_s = nuovo
        t_fermo = min(stato.fermo_residuo_s, passo_s)
        causale = stato.causale
        stato.fermo_residuo_s -= t_fermo
        if not stato.fermo_residuo_s:
            stato.causale = None
        return t_fermo, causale


def simula_storico(
    macchine: list[DatiMacchina], seme: int, da: date, fino_a: datetime, passo_s: int = 60,
    scenari: Scenari | None = None,
) -> Iterator[tuple[date, list[dict]]]:
    """Genera le rilevazioni di ogni giorno lavorativo da `da` fino all'istante `fino_a`, un giorno alla volta.

    Tutta la casualità passa da un unico generatore inizializzato con il seme: a parità di seme, periodo e
    anagrafica il risultato è sempre identico.
    """
    linea = Linea(macchine, random.Random(seme), scenari)
    giorno = da
    while giorno <= fino_a.astimezone(FUSO).date():
        if lavorativo(giorno):
            blocco = [r for inizio in passi_del_giorno(giorno, passo_s, fino_a) for r in linea.passo(inizio, passo_s)]
            linea.fine_giornata()
            if blocco:
                yield giorno, blocco
        giorno += timedelta(days=1)
