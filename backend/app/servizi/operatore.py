"""Vista operatore: stato attuale delle macchine e avanzamento del turno in corso."""

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.tabelle import CausaleFermo, Macchina, Parametro, Rilevazione
from app.kpi.formule import capacita_linea, kpi_linea, obiettivo_turno, rapporto
from app.servizi.calendario import DURATA_TURNO, turno_di
from app.servizi.ricalcolo import dati_macchina, grandezze, parametri_economici, somme_rilevazioni

# Il generatore live invia dati ogni pochi secondi: oltre questo ritardo lo stato mostrato non è più quello attuale.
RITARDO_MASSIMO = timedelta(minutes=2)


def _ultime_rilevazioni(db: Session, da: datetime, a: datetime) -> dict[int, Rilevazione]:
    """L'ultima rilevazione di ogni macchina iniziata in [da, a)."""
    ultime = (select(Rilevazione.macchina_id, func.max(Rilevazione.inizio).label("inizio"))
              .where(Rilevazione.inizio >= da, Rilevazione.inizio < a)
              .group_by(Rilevazione.macchina_id).subquery())
    righe = db.scalars(select(Rilevazione).join(
        ultime, (Rilevazione.macchina_id == ultime.c.macchina_id) & (Rilevazione.inizio == ultime.c.inizio)))
    return {r.macchina_id: r for r in righe}


def stato(db: Session, adesso: datetime) -> dict:
    macchine = list(db.scalars(select(Macchina).order_by(Macchina.ordine)))
    causali = {c.codice: c.descrizione for c in db.scalars(select(CausaleFermo))}
    turno = turno_di(adesso)
    ultime = _ultime_rilevazioni(db, *turno) if turno else {}

    stati = []
    for m in macchine:
        r = ultime.get(m.id)
        fine = r.inizio + timedelta(seconds=r.durata_s) if r else None
        if r is None or adesso - fine > RITARDO_MASSIMO:
            valore, causale = "senza_dati", None
        elif r.t_fermo_s > 0 and r.causale_codice:
            # Nell'ultimo intervallo (5 secondi nel live) la macchina è stata ferma: si mostra ferma con la causale.
            valore, causale = "ferma", r.causale_codice
        else:
            valore, causale = "in_funzione", None
        stati.append({"codice": m.codice, "nome": m.nome, "stato": valore, "causale": causale,
                      "descrizione_causale": causali.get(causale), "ultima_rilevazione": fine})

    return {"aggiornato_il": adesso, "turno": _avanzamento(db, macchine, *turno) if turno else None,
            "macchine": stati}


def _avanzamento(db: Session, macchine: list[Macchina], inizio: datetime, fine: datetime) -> dict:
    """Produzione e scarto di linea dall'inizio del turno, con le stesse formule dei KPI giornalieri."""
    somme = somme_rilevazioni(db, inizio, fine)
    # Come per il giorno in corso, il tempo disponibile arriva fin dove arrivano i dati.
    ultima = max((s["fine"] for s in somme.values()), default=inizio)
    t_disp = int((min(ultima, fine) - inizio).total_seconds())
    basi = {m.codice: grandezze(somme.get(m.id, {}), t_disp) for m in macchine}
    dati = [dati_macchina(m) for m in macchine]
    k = kpi_linea(basi, dati, parametri_economici(db))
    quota = float(db.scalar(select(Parametro.valore).where(Parametro.chiave == "quota_obiettivo_turno")))
    obiettivo = round(obiettivo_turno(capacita_linea(dati), DURATA_TURNO.total_seconds() / 3600, quota))
    return {"inizio": inizio, "fine": fine, "n_buoni": k.n_buoni, "n_scarti": k.n_scarti,
            "tasso_scarto": k.tasso_scarto, "obiettivo": obiettivo, "avanzamento": rapporto(k.n_buoni, obiettivo)}
