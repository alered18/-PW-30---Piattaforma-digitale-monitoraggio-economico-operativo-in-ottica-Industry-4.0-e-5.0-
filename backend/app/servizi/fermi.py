"""Fermi ricavati dalle rilevazioni.

Ogni rilevazione dice per quanti secondi la macchina è stata ferma e per quale causale. Un fermo è una sequenza di
rilevazioni contigue della stessa macchina, tutte con tempo di fermo e con la stessa causale: si uniscono in un
evento con inizio, fine, durata e costo. Gli eventi sono memorizzati come anomalie di tipo "fermo" e si ricostruiscono
a ogni ricalcolo del giorno, quindi tempi dei KPI ed elenco dei fermi vengono sempre dalle stesse rilevazioni.

Precisione: il fermo inizia all'inizio della prima rilevazione e dura la somma dei secondi di fermo; non si può
essere più precisi dell'intervallo di campionamento (1 minuto nello storico, 5 secondi nel live).
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.tabelle import Anomalia, CausaleFermo, Macchina, Rilevazione
from app.kpi.formule import DatiMacchina, ParametriEconomici, costo_fermo
from app.servizi.calendario import FUSO


@dataclass
class Fermo:
    macchina_id: int
    causale: str
    inizio: datetime
    durata_s: int
    fine_ultima_rilevazione: datetime  # serve solo a capire se la rilevazione successiva è contigua

    @property
    def fine(self) -> datetime:
        return self.inizio + timedelta(seconds=self.durata_s)


def unisci(rilevazioni: list[tuple[int, datetime, int, int, str]]) -> list[Fermo]:
    """Unisce le rilevazioni di fermo (macchina, inizio, durata, secondi di fermo, causale), ordinate per macchina e
    inizio, in eventi di fermo."""
    fermi: list[Fermo] = []
    for macchina_id, inizio, durata_s, t_fermo_s, causale in rilevazioni:
        ultimo = fermi[-1] if fermi else None
        contiguo = (ultimo is not None and ultimo.macchina_id == macchina_id and ultimo.causale == causale
                    and ultimo.fine_ultima_rilevazione == inizio)
        if contiguo:
            ultimo.durata_s += t_fermo_s
            ultimo.fine_ultima_rilevazione = inizio + timedelta(seconds=durata_s)
        else:
            fermi.append(Fermo(macchina_id, causale, inizio, t_fermo_s, inizio + timedelta(seconds=durata_s)))
    return fermi


def ricostruisci(
    db: Session,
    giorno: date,
    macchine: list[Macchina],
    dati: list[DatiMacchina],
    parametri: ParametriEconomici,
    capacita_linea_conf_h: float,
) -> None:
    """Riscrive le anomalie di tipo fermo del giorno. Il costo (in `valore`) è quello dei fermi non pianificati:
    la manutenzione programmata è un fermo previsto e non ha costo di fermo."""
    da = datetime.combine(giorno, time(), tzinfo=FUSO)
    righe = db.execute(
        select(Rilevazione.macchina_id, Rilevazione.inizio, Rilevazione.durata_s, Rilevazione.t_fermo_s,
               Rilevazione.causale_codice)
        .where(Rilevazione.inizio >= da, Rilevazione.inizio < da + timedelta(days=1), Rilevazione.t_fermo_s > 0)
        .order_by(Rilevazione.macchina_id, Rilevazione.inizio)
    ).all()
    causali = {c.codice: c for c in db.scalars(select(CausaleFermo))}
    per_id = {m.id: (m, d) for m, d in zip(macchine, dati)}

    db.execute(delete(Anomalia).where(Anomalia.data == giorno, Anomalia.tipo == "fermo"))
    for f in unisci([tuple(r) for r in righe]):
        macchina, dati_macchina = per_id[f.macchina_id]
        causale = causali[f.causale]
        costo = 0.0 if causale.pianificata else costo_fermo(f.durata_s, dati_macchina, parametri,
                                                                  capacita_linea_conf_h)
        db.add(Anomalia(
            tipo="fermo", data=giorno, macchina_id=f.macchina_id, inizio=f.inizio, fine=f.fine,
            causale_codice=f.causale, valore=round(costo, 4),
            descrizione=f"{macchina.codice}: {causale.descrizione.lower()} di {_durata(f.durata_s)}",
        ))


def _durata(secondi: int) -> str:
    ore, resto = divmod(secondi, 3600)
    minuti, sec = divmod(resto, 60)
    if ore:
        return f"{ore} h {minuti} min" if minuti else f"{ore} h"
    return f"{minuti} min" if not sec else f"{minuti} min {sec} s"
