"""Ricalcolo giornaliero: dalle rilevazioni di un giorno alla produzione giornaliera, agli indicatori, ai fermi, agli
alert delle soglie e alle anomalie di dato.

Il ricalcolo di un giorno è idempotente: cancella e riscrive le righe di quel giorno, quindi ripeterlo con gli
stessi dati dà sempre lo stesso risultato. Viene eseguito dopo ogni blocco di rilevazioni ricevuto e su richiesta,
ad esempio dopo una modifica dei parametri economici.
"""

import time as orologio
from dataclasses import asdict
from datetime import date, datetime, time, timedelta

from sqlalchemy import case, delete, func, select
from sqlalchemy.orm import Session

from app.db.tabelle import (
    Anomalia,
    CausaleFermo,
    Indicatore,
    Linea,
    Macchina,
    Parametro,
    ProduzioneGiornaliera,
    Rilevazione,
)
from app.kpi.formule import (
    DatiMacchina,
    GrandezzeBase,
    Kpi,
    ParametriEconomici,
    capacita_linea,
    kpi_linea,
    kpi_macchina,
)
from app.servizi import fermi, misure, soglie
from app.servizi.calendario import FUSO, chiusura, giorno_di, secondi_disponibili

# Sotto il minuto un buco tra le rilevazioni è solo un arrotondamento, non un dato mancante.
SCOPERTO_MINIMO_S = 60


def parametri_economici(db: Session) -> ParametriEconomici:
    valori = {chiave: float(valore) for chiave, valore in db.execute(select(Parametro.chiave, Parametro.valore))}
    return ParametriEconomici(
        prezzo_energia=valori["prezzo_energia"],
        costo_materia_conf=valori["costo_materia_conf"],
        costo_imballo_conf=valori["costo_imballo_conf"],
        margine_conf=valori["margine_conf"],
        fattore_co2=valori["fattore_co2"],
    )


def dati_macchina(m: Macchina) -> DatiMacchina:
    return DatiMacchina(m.codice, m.ordine, float(m.capacita_conf_h), float(m.costo_orario_eur),
                        float(m.costo_scarto_eur_conf))


def somme_rilevazioni(db: Session, da: datetime, a: datetime) -> dict[int, dict]:
    """Somme per macchina delle rilevazioni iniziate in [da, a), separando fermi pianificati e non pianificati."""
    fermo_pianificato = case((CausaleFermo.pianificata, Rilevazione.t_fermo_s), else_=0)
    fermo_non_pianificato = case((CausaleFermo.pianificata, 0), else_=Rilevazione.t_fermo_s)
    righe = db.execute(
        select(
            Rilevazione.macchina_id,
            func.sum(Rilevazione.durata_s).label("coperto_s"),
            func.sum(fermo_pianificato).label("t_man_s"),
            func.sum(fermo_non_pianificato).label("t_fermo_s"),
            func.sum(Rilevazione.t_funz_s).label("t_funz_s"),
            func.sum(Rilevazione.pezzi).label("n_tot"),
            func.sum(Rilevazione.scarti).label("n_scarti"),
            func.sum(Rilevazione.kwh).label("kwh"),
            func.max(Rilevazione.inizio + func.make_interval(0, 0, 0, 0, 0, 0, Rilevazione.durata_s)).label("fine"),
        )
        .outerjoin(CausaleFermo, Rilevazione.causale_codice == CausaleFermo.codice)
        .where(Rilevazione.inizio >= da, Rilevazione.inizio < a)
        .group_by(Rilevazione.macchina_id)
    )
    return {r.macchina_id: r._asdict() for r in righe}


def grandezze(somme: dict, t_disp_s: int) -> GrandezzeBase:
    """Grandezze di base di una macchina dalle sue somme (vuote se non ha rilevazioni) e dal tempo disponibile."""
    return GrandezzeBase(
        t_disp_s=t_disp_s,
        t_man_s=int(somme.get("t_man_s") or 0),
        t_fermo_s=int(somme.get("t_fermo_s") or 0),
        t_funz_s=int(somme.get("t_funz_s") or 0),
        n_tot=int(somme.get("n_tot") or 0),
        n_scarti=int(somme.get("n_scarti") or 0),
        kwh=float(somme.get("kwh") or 0),
    )


def ricalcola_giorno(db: Session, giorno: date, adesso: datetime | None = None) -> bool:
    """Ricalcola un giorno. Restituisce False se quel giorno non ha rilevazioni (nulla da calcolare)."""
    adesso = adesso or datetime.now(FUSO)
    # Un ricalcolo alla volta per lo stesso giorno (generatore, lettura dei KPI, import): il lock del database
    # dura fino alla fine della transazione e fa attendere le altre richieste invece di farle collidere.
    db.execute(select(func.pg_advisory_xact_lock(giorno.toordinal())))
    mezzanotte = datetime.combine(giorno, time(), tzinfo=FUSO)
    somme = somme_rilevazioni(db, mezzanotte, mezzanotte + timedelta(days=1))
    if not somme:
        return False

    macchine = list(db.scalars(select(Macchina).order_by(Macchina.ordine)))
    dati_macchine = [dati_macchina(m) for m in macchine]
    capacita = capacita_linea(dati_macchine)
    linea = db.scalars(select(Linea)).one()
    parametri = parametri_economici(db)
    # Giorno in corso: il tempo disponibile arriva solo fin dove arrivano i dati e i KPI sono parziali.
    parziale = giorno == giorno_di(adesso) and adesso < chiusura(giorno)
    ultima = max(s["fine"] for s in somme.values())
    t_disp = secondi_disponibili(giorno, ultima if parziale else None)

    basi: dict[str, GrandezzeBase] = {}
    valori: list[tuple[Macchina | None, dict]] = []
    db.execute(delete(ProduzioneGiornaliera).where(ProduzioneGiornaliera.data == giorno))
    db.execute(delete(Indicatore).where(Indicatore.data == giorno))
    db.execute(delete(Anomalia).where(Anomalia.data == giorno, Anomalia.tipo == "dato"))
    for m, dati in zip(macchine, dati_macchine):
        s = somme.get(m.id, {})
        base = grandezze(s, t_disp)
        basi[m.codice] = base
        db.add(ProduzioneGiornaliera(
            data=giorno, macchina_id=m.id, t_disp_s=base.t_disp_s, t_man_s=base.t_man_s, t_fermo_s=base.t_fermo_s,
            t_funz_s=base.t_funz_s, n_tot=base.n_tot, n_scarti=base.n_scarti, kwh=base.kwh,
            ultima_rilevazione=s.get("fine"), parziale=parziale,
        ))
        k = kpi_macchina(base, dati, parametri, capacita)
        db.add(_indicatore(giorno, k, parziale, macchina_id=m.id))
        valori.append((m, asdict(k)))
        _anomalie_di_dato(db, giorno, m, k, t_disp - int(s.get("coperto_s") or 0))

    k_linea = kpi_linea(basi, dati_macchine, parametri)
    db.add(_indicatore(giorno, k_linea, parziale, linea_id=linea.id))
    valori.append((None, asdict(k_linea)))
    fermi.ricostruisci(db, giorno, macchine, dati_macchine, parametri, capacita)
    soglie.ricostruisci(db, giorno, valori)
    return True


def _indicatore(giorno: date, k: Kpi, parziale: bool, linea_id: int | None = None,
                macchina_id: int | None = None) -> Indicatore:
    return Indicatore(
        data=giorno, linea_id=linea_id, macchina_id=macchina_id, n_tot=k.n_tot, n_buoni=k.n_buoni,
        n_scarti=k.n_scarti, produttivita_conf_h=k.produttivita_conf_h, disponibilita=k.disponibilita,
        prestazioni=k.prestazioni, qualita=k.qualita, oee=k.oee, tasso_scarto=k.tasso_scarto, kwh=k.kwh,
        kwh_conf=k.kwh_conf, costo_fermi_eur=k.costo_fermi_eur, co2_kg=k.co2_kg, co2_kg_conf=k.co2_kg_conf,
        saturazione=k.saturazione, costo_macchina_eur=k.costo_macchina_eur, costo_energia_eur=k.costo_energia_eur,
        costo_materia_eur=k.costo_materia_eur, costo_totale_eur=k.costo_totale_eur,
        costo_unitario_eur=k.costo_unitario_eur, costo_scarti_eur=k.costo_scarti_eur, parziale=parziale,
    )


def _anomalie_di_dato(db: Session, giorno: date, m: Macchina, k: Kpi, scoperto_s: int) -> None:
    """Dati sospetti che spiegano un KPI strano: prestazioni impossibili o tempo di turno senza rilevazioni."""
    if k.prestazioni_limitate:
        db.add(Anomalia(tipo="dato", data=giorno, macchina_id=m.id, kpi="prestazioni",
                        descrizione=f"{m.codice}: prestazioni oltre il 100%, verificare il tempo ciclo ideale"))
    if scoperto_s >= SCOPERTO_MINIMO_S:
        db.add(Anomalia(tipo="dato", data=giorno, macchina_id=m.id, valore=scoperto_s / 60,
                        descrizione=f"{m.codice}: {scoperto_s // 60} minuti di turno senza rilevazioni"))


def ricalcola(db: Session, giorni: list[date], adesso: datetime | None = None) -> list[date]:
    """Ricalcola più giorni in un'unica transazione; restituisce quelli che avevano dati."""
    ricalcolati = []
    for giorno in sorted(set(giorni)):
        avvio = orologio.perf_counter()
        if ricalcola_giorno(db, giorno, adesso):
            ricalcolati.append(giorno)
            misure.registra_ricalcolo(giorno, (orologio.perf_counter() - avvio) * 1000)
    db.commit()
    return ricalcolati


def giorni_con_dati(db: Session, da: date, a: date) -> list[date]:
    """Giorni dell'intervallo (estremi inclusi) che hanno almeno una rilevazione."""
    inizio = datetime.combine(da, time(), tzinfo=FUSO)
    fine = datetime.combine(a + timedelta(days=1), time(), tzinfo=FUSO)
    giorno_locale = func.date(func.timezone(FUSO.key, Rilevazione.inizio))
    return list(db.scalars(
        select(giorno_locale).where(Rilevazione.inizio >= inizio, Rilevazione.inizio < fine).distinct()
    ))
