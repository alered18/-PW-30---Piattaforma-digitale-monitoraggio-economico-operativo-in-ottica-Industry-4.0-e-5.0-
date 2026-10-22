"""Lettura dei KPI per periodo: giorno, settimana (ISO, da lunedì) o mese di calendario.

Per qualunque granularità il calcolo è lo stesso: si sommano le grandezze di base giornaliere del periodo
(tabella produzione_giornaliera) e si applicano le formule. Così giorno, settimana, mese e totale del periodo
rispettano la regola del rapporto delle somme e usano esattamente lo stesso codice.
"""

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.tabelle import Macchina, Parametro, ProduzioneGiornaliera
from app.kpi.formule import GrandezzeBase, capacita_linea, kpi_linea, kpi_macchina, produzione_kg, somma
from app.servizi import ricalcolo, soglie
from app.servizi.calendario import FUSO, giorno_di, lavorativo

@dataclass
class Periodo:
    etichetta: str
    da: date
    a: date


def periodo_di(giorno: date, granularita: str) -> Periodo:
    if granularita == "giorno":
        return Periodo(giorno.isoformat(), giorno, giorno)
    if granularita == "settimana":
        anno, settimana, _ = giorno.isocalendar()
        lunedi = giorno - timedelta(days=giorno.weekday())
        return Periodo(f"{anno}-W{settimana:02d}", lunedi, lunedi + timedelta(days=6))
    primo = giorno.replace(day=1)
    ultimo = (primo + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    return Periodo(primo.strftime("%Y-%m"), primo, ultimo)


def _giorni_lavorativi_trascorsi(da: date, a: date, oggi: date) -> set[date]:
    return {da + timedelta(days=i) for i in range((min(a, oggi) - da).days + 1) if lavorativo(da + timedelta(days=i))}


def leggi(db: Session, ambito: str, da: date, a: date, granularita: str, adesso: datetime | None = None) -> dict:
    """Serie dei KPI per periodo e totale dell'intervallo richiesto. `ambito` è 'linea' o il codice di una macchina."""
    adesso = adesso or datetime.now(FUSO)
    oggi = giorno_di(adesso)
    _completa_giorni_rimasti_parziali(db, da, a, adesso)

    macchine = list(db.scalars(select(Macchina).order_by(Macchina.ordine)))
    dati = {m.codice: ricalcolo.dati_macchina(m) for m in macchine}
    parametri = ricalcolo.parametri_economici(db)
    peso_conf = float(db.get(Parametro, "peso_conf").valore)
    capacita = capacita_linea(dati.values())
    regole = soglie.regole(db, ambito)

    # Grandezze di base per giorno e macchina nell'intervallo.
    per_giorno: dict[date, dict[str, GrandezzeBase]] = defaultdict(dict)
    parziali: set[date] = set()
    righe = db.execute(
        select(ProduzioneGiornaliera, Macchina.codice)
        .join(Macchina)
        .where(ProduzioneGiornaliera.data >= da, ProduzioneGiornaliera.data <= a)
    )
    for p, codice in righe:
        per_giorno[p.data][codice] = GrandezzeBase(p.t_disp_s, p.t_man_s, p.t_fermo_s, p.t_funz_s, p.n_tot,
                                                   p.n_scarti, float(p.kwh))
        if p.parziale:
            parziali.add(p.data)

    def calcola(giorni: list[date]) -> dict:
        basi = {codice: somma(per_giorno[g].get(codice, GrandezzeBase()) for g in giorni) for codice in dati}
        if ambito == "linea":
            k = kpi_linea(basi, dati.values(), parametri)
        else:
            k = kpi_macchina(basi[ambito], dati[ambito], parametri, capacita)
        return asdict(k) | {"produzione_kg": produzione_kg(k.n_buoni, peso_conf)}

    def parziale(periodo: Periodo, giorni: list[date]) -> bool:
        # Parziale se comprende il giorno in corso, se l'intervallo richiesto lo taglia o se mancano dati di giorni
        # lavorativi già trascorsi (ad esempio una settimana che inizia prima dello storico).
        attesi = _giorni_lavorativi_trascorsi(max(periodo.da, da), min(periodo.a, a), oggi)
        return bool(parziali & set(giorni)) or periodo.da < da or periodo.a > a or not attesi <= set(giorni)

    def punto(etichetta: str, inizio: date, fine: date, incompleto: bool, valori: dict) -> dict:
        return {"periodo": etichetta, "da": inizio, "a": fine, "parziale": incompleto, "kpi": valori,
                "stato_soglie": soglie.stati(valori, regole, un_giorno=inizio == fine)}

    gruppi: dict[str, tuple[Periodo, list[date]]] = {}
    for g in sorted(per_giorno):
        periodo = periodo_di(g, granularita)
        gruppi.setdefault(periodo.etichetta, (periodo, []))[1].append(g)

    serie = [
        punto(p.etichetta, p.da, p.a, parziale(p, giorni), calcola(giorni)) for p, giorni in gruppi.values()
    ]
    tutti = sorted(per_giorno)
    totale = None
    if tutti:
        intero = Periodo(f"{da.isoformat()}/{a.isoformat()}", da, a)
        totale = punto(intero.etichetta, da, a, parziale(intero, tutti), calcola(tutti))
    return {"ambito": ambito, "granularita": granularita, "da": da, "a": a, "soglie": [asdict(r) for r in regole],
            "serie": serie, "totale": totale}


def _completa_giorni_rimasti_parziali(db: Session, da: date, a: date, adesso: datetime) -> None:
    """Un giorno passato può essere rimasto "parziale" se il generatore si è fermato prima della fine del turno:
    ricalcolandolo, il tempo disponibile torna quello dell'intera giornata."""
    rimasti = list(db.scalars(
        select(ProduzioneGiornaliera.data).where(
            ProduzioneGiornaliera.parziale, ProduzioneGiornaliera.data >= da, ProduzioneGiornaliera.data <= a,
            ProduzioneGiornaliera.data < giorno_di(adesso),
        ).distinct()
    ))
    if rimasti:
        ricalcolo.ricalcola(db, rimasti, adesso)
