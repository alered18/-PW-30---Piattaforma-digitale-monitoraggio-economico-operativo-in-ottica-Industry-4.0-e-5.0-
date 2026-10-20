"""Formule degli indicatori (KPI): l'unico punto del back-end in cui sono definite.

Il modulo contiene solo funzioni pure: riceve grandezze già sommate e parametri, restituisce i KPI. Non legge il
database e non conosce le API, così ogni formula si verifica con numeri scritti a mano.

Grandezze di base per una macchina in un periodo (tempi in secondi, convertiti in ore nei calcoli):
    T_disp   tempo disponibile da calendario dei turni
    T_man    fermi pianificati (manutenzione programmata)
    T_pian   tempo pianificato = T_disp - T_man
    T_fermo  fermi non pianificati (guasti, setup, mancanza materiale, micro-fermate)
    T_funz   tempo di funzionamento registrato
    N_tot    confezioni prodotte, buone + scartate;  N_scarti  confezioni scartate;  N_buoni = N_tot - N_scarti
    E        energia consumata (kWh)
    TC_id    tempo ciclo ideale = 1 / capacità oraria

Regole generali:
    * un rapporto con denominatore zero non è calcolabile e vale None (in dashboard "n.d."), mai 0;
    * per un periodo lungo si sommano le grandezze di base e poi si calcolano i rapporti (rapporto delle somme),
      invece di fare la media dei valori giornalieri, che darebbe lo stesso peso a giorni con volumi diversi;
    * le percentuali sono frazioni tra 0 e 1.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, fields

SECONDI_ORA = 3600


@dataclass(frozen=True)
class GrandezzeBase:
    """Somme di una macchina in un periodo (un giorno, una settimana, un mese)."""

    t_disp_s: int = 0
    t_man_s: int = 0
    t_fermo_s: int = 0
    t_funz_s: int = 0
    n_tot: int = 0
    n_scarti: int = 0
    kwh: float = 0.0

    @property
    def t_pian_s(self) -> int:
        return self.t_disp_s - self.t_man_s

    @property
    def n_buoni(self) -> int:
        return self.n_tot - self.n_scarti

    def __add__(self, altra: "GrandezzeBase") -> "GrandezzeBase":
        return GrandezzeBase(**{f.name: getattr(self, f.name) + getattr(altra, f.name) for f in fields(self)})


@dataclass(frozen=True)
class DatiMacchina:
    """Dati di anagrafica che servono alle formule."""

    codice: str
    ordine: int  # posizione nella linea; la più alta è l'uscita della linea
    capacita_conf_h: float
    costo_orario_eur: float  # costo sostenuto anche a macchina ferma
    costo_scarto_eur_conf: float  # valore perso per ogni confezione scartata su questa macchina

    @property
    def tempo_ciclo_ideale_h(self) -> float:
        return 1 / self.capacita_conf_h


@dataclass(frozen=True)
class ParametriEconomici:
    prezzo_energia: float  # €/kWh
    costo_materia_conf: float  # €/conf
    costo_imballo_conf: float  # €/conf
    margine_conf: float  # €/conf, margine di contribuzione
    fattore_co2: float  # kg CO2 per kWh


@dataclass(frozen=True)
class Kpi:
    """Indicatori di una macchina o della linea in un periodo. None = non calcolabile."""

    n_tot: int
    n_buoni: int
    n_scarti: int
    produttivita_conf_h: float | None
    disponibilita: float | None
    prestazioni: float | None
    qualita: float | None
    oee: float | None
    tasso_scarto: float | None
    kwh: float
    kwh_conf: float | None
    costo_fermi_eur: float
    co2_kg: float
    co2_kg_conf: float | None
    saturazione: float | None
    costo_macchina_eur: float
    costo_energia_eur: float
    costo_materia_eur: float
    costo_totale_eur: float
    costo_unitario_eur: float | None
    costo_scarti_eur: float  # dettaglio: valore perso negli scarti, già compreso nel costo della materia
    # True se le prestazioni calcolate superavano il 100% e sono state limitate: indica un tempo ciclo ideale
    # sbagliato o dati incoerenti, da segnalare come anomalia.
    prestazioni_limitate: bool = False


def rapporto(numeratore: float, denominatore: float) -> float | None:
    """Divisione che restituisce None invece di fallire o dare 0 quando il denominatore è zero."""
    return numeratore / denominatore if denominatore else None


def somma(grandezze: Iterable[GrandezzeBase]) -> GrandezzeBase:
    """Somma le grandezze di più giorni: è il primo passo per i KPI di settimana, mese o periodo."""
    totale = GrandezzeBase()
    for g in grandezze:
        totale = totale + g
    return totale


def capacita_linea(macchine: Iterable[DatiMacchina]) -> float:
    """La linea non può produrre più della sua macchina più lenta (collo di bottiglia)."""
    return min(m.capacita_conf_h for m in macchine)


def produzione_kg(n_buoni: int, peso_conf_kg: float) -> float:
    """Produzione buona espressa in kg (le quantità si contano in confezioni)."""
    return n_buoni * peso_conf_kg


def valore_produzione_persa_h(capacita_linea_conf_h: float, parametri: ParametriEconomici) -> float:
    """Margine perso in un'ora di linea ferma: ciò che la linea avrebbe prodotto × margine per confezione."""
    return capacita_linea_conf_h * parametri.margine_conf


def _efficienza(
    t_pian_s: int, t_funz_s: int, n_tot: int, n_buoni: int, tempo_ciclo_ideale_h: float
) -> tuple[float | None, float | None, float | None, float | None, bool]:
    """Disponibilità, prestazioni, qualità e OEE.

    L'OEE si calcola nella forma diretta N_buoni × TC_id / T_pian, che è algebricamente uguale a
    Disponibilità × Prestazioni × Qualità ma resta definita anche quando la macchina non ha mai girato
    (OEE = 0 invece di "non calcolabile"). Se le prestazioni superano il 100% vengono limitate a 1 e
    l'OEE è ricalcolato come A × 1 × Q, così le tre componenti restano coerenti con il totale.
    """
    t_pian_h, t_funz_h = t_pian_s / SECONDI_ORA, t_funz_s / SECONDI_ORA
    disponibilita = rapporto(t_funz_h, t_pian_h)
    prestazioni = rapporto(n_tot * tempo_ciclo_ideale_h, t_funz_h)
    qualita = rapporto(n_buoni, n_tot)
    oee = rapporto(n_buoni * tempo_ciclo_ideale_h, t_pian_h)
    limitate = prestazioni is not None and prestazioni > 1
    if limitate:
        prestazioni = 1.0
        oee = disponibilita * qualita
    return disponibilita, prestazioni, qualita, oee, limitate


def kpi_macchina(
    base: GrandezzeBase,
    macchina: DatiMacchina,
    parametri: ParametriEconomici,
    capacita_linea_conf_h: float,
) -> Kpi:
    """KPI di una singola macchina.

    Il costo di una macchina è il suo costo di trasformazione: costo orario per il tempo pianificato, energia e
    valore perso nei suoi scarti. La materia che diventa prodotto buono appartiene alla linea, non alla singola
    macchina, ed è conteggiata nel costo di produzione della linea.
    """
    t_pian_h = base.t_pian_s / SECONDI_ORA
    disponibilita, prestazioni, qualita, oee, limitate = _efficienza(
        base.t_pian_s, base.t_funz_s, base.n_tot, base.n_buoni, macchina.tempo_ciclo_ideale_h
    )
    # Costo dei fermi non pianificati: il costo orario della macchina ferma c'è sempre. La produzione persa dalla
    # linea si conta solo per la macchina più lenta: i fermi delle altre, più veloci, sono assorbiti dai buffer e
    # recuperati, mentre ogni minuto perso dal collo di bottiglia è produzione che la linea non recupera più.
    # Contarla per tutte le macchine sommerebbe più volte la stessa perdita. Se più macchine avessero la stessa
    # capacità minima, sarebbero tutte collo di bottiglia e la conterebbero ciascuna (non è il caso di questa linea).
    collo_di_bottiglia = macchina.capacita_conf_h <= capacita_linea_conf_h
    produzione_persa_h = valore_produzione_persa_h(capacita_linea_conf_h, parametri) if collo_di_bottiglia else 0.0
    costo_fermi = (base.t_fermo_s / SECONDI_ORA) * (macchina.costo_orario_eur + produzione_persa_h)
    co2 = base.kwh * parametri.fattore_co2
    costo_macchina = t_pian_h * macchina.costo_orario_eur
    costo_energia = base.kwh * parametri.prezzo_energia
    costo_scarti = base.n_scarti * macchina.costo_scarto_eur_conf
    costo_totale = costo_macchina + costo_energia + costo_scarti
    return Kpi(
        n_tot=base.n_tot,
        n_buoni=base.n_buoni,
        n_scarti=base.n_scarti,
        produttivita_conf_h=rapporto(base.n_buoni, t_pian_h),
        disponibilita=disponibilita,
        prestazioni=prestazioni,
        qualita=qualita,
        oee=oee,
        tasso_scarto=rapporto(base.n_scarti, base.n_tot),
        kwh=base.kwh,
        kwh_conf=rapporto(base.kwh, base.n_buoni),
        costo_fermi_eur=costo_fermi,
        co2_kg=co2,
        co2_kg_conf=rapporto(co2, base.n_buoni),
        saturazione=rapporto(base.t_funz_s, base.t_disp_s),
        costo_macchina_eur=costo_macchina,
        costo_energia_eur=costo_energia,
        costo_materia_eur=costo_scarti,
        costo_totale_eur=costo_totale,
        costo_unitario_eur=rapporto(costo_totale, base.n_buoni),
        costo_scarti_eur=costo_scarti,
        prestazioni_limitate=limitate,
    )


def kpi_linea(
    basi: Mapping[str, GrandezzeBase],
    macchine: Iterable[DatiMacchina],
    parametri: ParametriEconomici,
) -> Kpi:
    """KPI della linea a partire dalle grandezze di ciascuna macchina (chiave = codice macchina).

    In una linea in serie conta ciò che esce dall'ultima macchina, confrontato con ciò che la linea poteva
    produrre nel tempo pianificato al ritmo del collo di bottiglia. Per questo l'OEE di linea non è la media
    degli OEE delle macchine: con macchine al 90%, 90%, 90%, 90% e 50% la media darebbe 82%, mentre l'uscita
    della linea è limitata dalla macchina al 50%.
    """
    macchine = list(macchine)
    collo = min(macchine, key=lambda m: m.capacita_conf_h)
    uscita = max(macchine, key=lambda m: m.ordine)
    capacita = collo.capacita_conf_h

    n_buoni = basi[uscita.codice].n_buoni
    n_scarti = sum(basi[m.codice].n_scarti for m in macchine)
    # Confezioni avviate dalla linea: quelle uscite buone più quelle scartate lungo il percorso.
    n_tot = n_buoni + n_scarti
    # La manutenzione programmata si fa a linea ferma: il tempo pianificato è lo stesso per tutte le macchine
    # e si prende quello del collo di bottiglia, coerente con il suo tempo ciclo ideale.
    t_pian_s = basi[collo.codice].t_pian_s
    t_pian_h = t_pian_s / SECONDI_ORA

    somma_t_pian = sum(basi[m.codice].t_pian_s for m in macchine)
    somma_t_funz = sum(basi[m.codice].t_funz_s for m in macchine)
    somma_t_disp = sum(basi[m.codice].t_disp_s for m in macchine)
    kwh = sum(basi[m.codice].kwh for m in macchine)

    disponibilita = rapporto(somma_t_funz, somma_t_pian)
    qualita = rapporto(n_buoni, n_tot)
    oee = rapporto(n_buoni * collo.tempo_ciclo_ideale_h, t_pian_h)
    # Le prestazioni di linea si ricavano dall'OEE e dalle altre due componenti. La disponibilità di linea è la
    # media pesata di tutte le macchine, mentre l'OEE dipende solo dall'uscita: se il collo di bottiglia gira
    # sempre e le macchine più veloci recuperano i propri fermi, il rapporto può superare 1 con dati del tutto
    # validi. In quel caso si mostra 1 e l'OEE resta quello calcolato sull'uscita, senza segnalare anomalie.
    prestazioni = rapporto(oee, disponibilita * qualita) if None not in (oee, disponibilita, qualita) else None
    if prestazioni is not None:
        prestazioni = min(prestazioni, 1.0)

    singole = [kpi_macchina(basi[m.codice], m, parametri, capacita) for m in macchine]
    co2 = kwh * parametri.fattore_co2
    costo_macchina = sum(k.costo_macchina_eur for k in singole)
    costo_energia = kwh * parametri.prezzo_energia
    # Materia e imballo di tutte le confezioni avviate, comprese quelle perse negli scarti.
    costo_materia = n_tot * (parametri.costo_materia_conf + parametri.costo_imballo_conf)
    costo_totale = costo_macchina + costo_energia + costo_materia
    return Kpi(
        n_tot=n_tot,
        n_buoni=n_buoni,
        n_scarti=n_scarti,
        produttivita_conf_h=rapporto(n_buoni, t_pian_h),
        disponibilita=disponibilita,
        prestazioni=prestazioni,
        qualita=qualita,
        oee=oee,
        tasso_scarto=None if qualita is None else 1 - qualita,
        kwh=kwh,
        kwh_conf=rapporto(kwh, n_buoni),
        costo_fermi_eur=sum(k.costo_fermi_eur for k in singole),
        co2_kg=co2,
        co2_kg_conf=rapporto(co2, n_buoni),
        saturazione=rapporto(somma_t_funz, somma_t_disp),
        costo_macchina_eur=costo_macchina,
        costo_energia_eur=costo_energia,
        costo_materia_eur=costo_materia,
        costo_totale_eur=costo_totale,
        costo_unitario_eur=rapporto(costo_totale, n_buoni),
        costo_scarti_eur=sum(k.costo_scarti_eur for k in singole),
    )
