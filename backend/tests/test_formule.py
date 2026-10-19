"""Test delle formule dei KPI con il dataset scritto a mano (nessun database)."""

from dataclasses import replace

import pytest

from app.kpi.formule import GrandezzeBase, kpi_linea, kpi_macchina, somma
from dati.dataset_test import (
    ATTESI_LINEA,
    ATTESI_M3,
    CAPACITA_LINEA,
    GIORNATA,
    GIORNO,
    MACCHINE,
    ORA,
    PARAMETRI,
    PER_CODICE,
)


def kpi_di(codice: str, base: GrandezzeBase | None = None):
    return kpi_macchina(base or GIORNO[codice], PER_CODICE[codice], PARAMETRI, CAPACITA_LINEA)


# --- Valori del dataset ---


@pytest.mark.parametrize("nome", ATTESI_M3)
def test_kpi_essiccatoio(nome):
    assert getattr(kpi_di("M3"), nome) == pytest.approx(ATTESI_M3[nome])


@pytest.mark.parametrize("nome", ATTESI_LINEA)
def test_kpi_linea(nome):
    assert getattr(kpi_linea(GIORNO, MACCHINE, PARAMETRI), nome) == pytest.approx(ATTESI_LINEA[nome])


@pytest.mark.parametrize("codice", PER_CODICE)
def test_oee_uguale_a_disponibilita_per_prestazioni_per_qualita(codice):
    k = kpi_di(codice)
    assert k.oee == pytest.approx(k.disponibilita * k.prestazioni * k.qualita)
    for componente in (k.disponibilita, k.prestazioni, k.qualita, k.oee):
        assert 0 <= componente <= 1


def test_oee_linea_non_e_la_media_degli_oee_delle_macchine():
    media = sum(kpi_di(c).oee for c in PER_CODICE) / 5
    linea = kpi_linea(GIORNO, MACCHINE, PARAMETRI)
    assert linea.oee == pytest.approx(ATTESI_LINEA["oee"])
    assert linea.oee != pytest.approx(media, abs=1e-3)
    assert linea.oee == pytest.approx(linea.disponibilita * linea.prestazioni * linea.qualita)


def test_consumo_di_linea_somma_delle_macchine():
    assert kpi_linea(GIORNO, MACCHINE, PARAMETRI).kwh == pytest.approx(sum(g.kwh for g in GIORNO.values()))


def test_componenti_del_costo_sommano_al_totale():
    for k in [kpi_di("M2"), kpi_linea(GIORNO, MACCHINE, PARAMETRI)]:
        assert k.costo_macchina_eur + k.costo_energia_eur + k.costo_materia_eur == pytest.approx(k.costo_totale_eur)


def test_co2_proporzionale_ai_kwh_e_al_fattore():
    raddoppiato = replace(PARAMETRI, fattore_co2=PARAMETRI.fattore_co2 * 2)
    normale = kpi_di("M3")
    doppio = kpi_macchina(GIORNO["M3"], PER_CODICE["M3"], raddoppiato, CAPACITA_LINEA)
    assert doppio.co2_kg == pytest.approx(2 * normale.co2_kg)


# --- Costo dei fermi ---


def test_fermo_di_un_ora_sulla_trafila():
    # 60 minuti di fermo su M2: 1 h × (40 €/h costo della trafila + 2.000 conf/h × 0,40 €) = 840 €.
    base = GrandezzeBase(GIORNATA, 0, ORA, GIORNATA - ORA, 25000, 0, 1000.0)
    assert kpi_di("M2", base).costo_fermi_eur == pytest.approx(840.0)


def test_manutenzione_programmata_non_penalizza_oee_e_non_costa_come_fermo():
    # 2 h di manutenzione: il tempo pianificato scende a 14 h e la macchina gira per tutte le 14 h.
    base = GrandezzeBase(GIORNATA, 2 * ORA, 0, 14 * ORA, 14 * 2000, 0, 2100.0)
    k = kpi_di("M3", base)
    assert k.disponibilita == pytest.approx(1.0)
    assert k.oee == pytest.approx(1.0)
    assert k.costo_fermi_eur == 0
    assert k.saturazione == pytest.approx(14 / 16)  # la saturazione invece usa il tempo disponibile


def test_macchina_mai_ferma_ha_saturazione_piena():
    base = GrandezzeBase(GIORNATA, 0, 0, GIORNATA, 30000, 0, 480.0)
    assert kpi_di("M1", base).saturazione == pytest.approx(1.0)


# --- Aggregazione: rapporto delle somme ---


def test_settimana_e_rapporto_delle_somme_non_media_dei_giorni():
    # Lunedì 10.000 confezioni con il 5% di scarti, martedì 30.000 con l'1%.
    lunedi = GrandezzeBase(GIORNATA, 0, 0, GIORNATA, 10000, 500, 0.0)
    martedi = GrandezzeBase(GIORNATA, 0, 0, GIORNATA, 30000, 300, 0.0)
    settimana = kpi_di("M2", somma([lunedi, martedi]))
    assert settimana.tasso_scarto == pytest.approx(800 / 40000)  # 2%
    media_dei_giorni = (kpi_di("M2", lunedi).tasso_scarto + kpi_di("M2", martedi).tasso_scarto) / 2
    assert media_dei_giorni == pytest.approx(0.03)
    assert settimana.tasso_scarto != pytest.approx(media_dei_giorni)


def test_somma_delle_grandezze():
    totale = somma([GIORNO["M1"], GIORNO["M1"]])
    assert totale == GrandezzeBase(2 * GIORNATA, 0, 2 * ORA, 30 * ORA, 51200, 200, 906.0)
    assert somma([]) == GrandezzeBase()


# --- Casi limite ---


def test_giorno_senza_turni_tutti_i_rapporti_non_disponibili():
    k = kpi_di("M1", GrandezzeBase())
    for nome in ("produttivita_conf_h", "disponibilita", "prestazioni", "qualita", "oee", "tasso_scarto",
                 "kwh_conf", "co2_kg_conf", "saturazione", "costo_unitario_eur"):
        assert getattr(k, nome) is None, nome
    assert k.costo_totale_eur == 0 and k.costo_fermi_eur == 0


def test_linea_senza_turni_non_disponibile():
    vuoto = {codice: GrandezzeBase() for codice in PER_CODICE}
    k = kpi_linea(vuoto, MACCHINE, PARAMETRI)
    assert k.oee is None and k.disponibilita is None and k.prestazioni is None and k.kwh_conf is None


def test_macchina_ferma_tutto_il_giorno():
    # Guasto per l'intera giornata: nessuna produzione, ma consumo a fermo dell'essiccatoio che resta caldo.
    base = GrandezzeBase(GIORNATA, 0, GIORNATA, 0, 0, 0, 105 * 16.0)
    k = kpi_di("M3", base)
    assert k.disponibilita == 0
    assert k.oee == 0  # la macchina doveva lavorare e non ha prodotto nulla
    assert k.prestazioni is None and k.qualita is None and k.tasso_scarto is None
    assert k.kwh == pytest.approx(1680.0) and k.kwh_conf is None  # consumo senza produzione: per confezione n.d.
    assert k.costo_fermi_eur == pytest.approx(16 * 845)


def test_prestazioni_oltre_il_cento_per_cento_limitate_e_segnalate():
    # 30.000 confezioni in 14 h su una macchina da 2.000 conf/h: impossibile (servirebbero 15 h).
    base = GrandezzeBase(GIORNATA, 0, 2 * ORA, 14 * ORA, 30000, 0, 0.0)
    k = kpi_di("M3", base)
    assert k.prestazioni_limitate
    assert k.prestazioni == 1.0
    assert k.oee == pytest.approx(k.disponibilita * k.qualita)
    assert not kpi_di("M3").prestazioni_limitate


def test_linea_con_collo_di_bottiglia_sempre_in_funzione():
    # M3 gira tutte le 16 h al ritmo ideale (32.000 confezioni); le altre macchine, più veloci, hanno fermi ma
    # recuperano. L'uscita della linea è il massimo possibile: OEE di linea 100%, anche se la disponibilità
    # media delle macchine è più bassa. Le prestazioni di linea non possono superare il 100% e non è un'anomalia.
    def macchina(fermo_h):
        return GrandezzeBase(GIORNATA, 0, round(fermo_h * ORA), GIORNATA - round(fermo_h * ORA), 32000, 0, 0.0)

    giorno = {"M1": macchina(2.6), "M2": macchina(1.4), "M3": macchina(0), "M4": macchina(1.4), "M5": macchina(3.6)}
    k = kpi_linea(giorno, MACCHINE, PARAMETRI)
    assert k.oee == pytest.approx(1.0)
    assert k.disponibilita == pytest.approx((80 - 9) / 80)
    assert k.prestazioni == 1.0
    assert not k.prestazioni_limitate


def test_linea_su_piu_giorni_rapporto_delle_somme():
    # Due giornate identiche: i rapporti non cambiano, le quantità raddoppiano.
    due_giorni = {codice: somma([g, g]) for codice, g in GIORNO.items()}
    k = kpi_linea(due_giorni, MACCHINE, PARAMETRI)
    assert k.oee == pytest.approx(ATTESI_LINEA["oee"])
    assert k.n_buoni == 2 * ATTESI_LINEA["n_buoni"]
    assert k.costo_totale_eur == pytest.approx(2 * ATTESI_LINEA["costo_totale_eur"])
    # Giornata con produzione dimezzata: il tasso di scarto di linea pesa i volumi, non fa la media dei due giorni.
    meta = {c: GrandezzeBase(GIORNATA, 0, 0, GIORNATA, g.n_tot // 2, 0, 0.0) for c, g in GIORNO.items()}
    k = kpi_linea({c: somma([GIORNO[c], meta[c]]) for c in GIORNO}, MACCHINE, PARAMETRI)
    assert k.tasso_scarto == pytest.approx(1100 / (24500 + 12300 + 1100))


def test_linea_senza_confezioni_buone_in_uscita():
    giorno = dict(GIORNO, M5=GrandezzeBase(GIORNATA, 0, GIORNATA, 0, 0, 0, 24.0))
    k = kpi_linea(giorno, MACCHINE, PARAMETRI)
    assert k.n_buoni == 0
    assert k.oee == 0
    assert k.kwh_conf is None and k.costo_unitario_eur is None
