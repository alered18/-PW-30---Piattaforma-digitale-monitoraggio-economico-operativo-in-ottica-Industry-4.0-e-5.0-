"""Test delle formule dei KPI con il dataset scritto a mano (nessun database)."""

import pytest

from app.kpi.formule import GrandezzeBase, kpi_linea, kpi_macchina, somma
from dati.dataset_test import ATTESI_LINEA, ATTESI_M3, CAPACITA_LINEA, GIORNATA, GIORNO, MACCHINE, ORA, PARAMETRI, PER_CODICE


def kpi_di(codice: str, base: GrandezzeBase | None = None):
    return kpi_macchina(base or GIORNO[codice], PER_CODICE[codice], PARAMETRI, CAPACITA_LINEA)


def test_kpi_essiccatoio():
    k = kpi_di("M3")
    for nome, atteso in ATTESI_M3.items():
        assert getattr(k, nome) == pytest.approx(atteso), nome
    assert k.oee == pytest.approx(k.disponibilita * k.prestazioni * k.qualita)


def test_kpi_linea_non_media_delle_macchine():
    k = kpi_linea(GIORNO, MACCHINE, PARAMETRI)
    for nome, atteso in ATTESI_LINEA.items():
        assert getattr(k, nome) == pytest.approx(atteso), nome
    media = sum(kpi_di(c).oee for c in PER_CODICE) / 5
    assert k.oee != pytest.approx(media, abs=1e-3)


def test_costo_di_un_fermo_di_un_ora():
    base = GrandezzeBase(GIORNATA, 0, ORA, GIORNATA - ORA, 25000, 0, 1000.0)
    # Trafila: i buffer assorbono il fermo, si paga solo il suo costo orario (40 €).
    assert kpi_di("M2", base).costo_fermi_eur == pytest.approx(40.0)
    # Essiccatoio, collo di bottiglia: 45 €/h + 2.000 conf/h × 0,40 € di produzione persa = 845 €.
    assert kpi_di("M3", base).costo_fermi_eur == pytest.approx(845.0)


def test_manutenzione_programmata_non_penalizza_oee():
    # 2 h di manutenzione: il tempo pianificato scende a 14 h e la macchina gira per tutte le 14 h.
    k = kpi_di("M3", GrandezzeBase(GIORNATA, 2 * ORA, 0, 14 * ORA, 14 * 2000, 0, 2100.0))
    assert k.oee == pytest.approx(1.0)
    assert k.costo_fermi_eur == 0
    assert k.saturazione == pytest.approx(14 / 16)  # la saturazione invece usa il tempo disponibile


def test_settimana_e_rapporto_delle_somme_non_media_dei_giorni():
    # Lunedì 10.000 confezioni con il 5% di scarti, martedì 30.000 con l'1%: 800 / 40.000 = 2%, non 3%.
    lunedi = GrandezzeBase(GIORNATA, 0, 0, GIORNATA, 10000, 500, 0.0)
    martedi = GrandezzeBase(GIORNATA, 0, 0, GIORNATA, 30000, 300, 0.0)
    assert kpi_di("M2", somma([lunedi, martedi])).tasso_scarto == pytest.approx(0.02)


def test_casi_limite():
    # Giorno senza turni: i KPI sono "n.d.", non 0.
    vuoto = kpi_di("M1", GrandezzeBase())
    assert vuoto.oee is None and vuoto.kwh_conf is None and vuoto.saturazione is None
    # Guasto per l'intera giornata: la macchina doveva lavorare, quindi OEE 0; il consumo a fermo resta.
    ferma = kpi_di("M3", GrandezzeBase(GIORNATA, 0, GIORNATA, 0, 0, 0, 1680.0))
    assert ferma.oee == 0 and ferma.qualita is None and ferma.kwh_conf is None
    # Prestazioni oltre il 100%: 30.000 confezioni in 14 h a 2.000 conf/h è impossibile, quindi è un dato da segnalare.
    k = kpi_di("M3", GrandezzeBase(GIORNATA, 0, 2 * ORA, 14 * ORA, 30000, 0, 0.0))
    assert k.prestazioni == 1.0 and k.prestazioni_limitate
    # Sulla linea invece no: M3 gira sempre e le macchine più veloci recuperano i fermi; OEE 100% e nessuna anomalia.
    fermo_h = {"M1": 2.6, "M2": 1.4, "M3": 0, "M4": 1.4, "M5": 3.6}
    linea = kpi_linea({c: GrandezzeBase(GIORNATA, 0, round(h * ORA), GIORNATA - round(h * ORA), 32000, 0, 0.0)
                       for c, h in fermo_h.items()}, MACCHINE, PARAMETRI)
    assert linea.oee == pytest.approx(1.0) and linea.prestazioni == 1.0 and not linea.prestazioni_limitate
