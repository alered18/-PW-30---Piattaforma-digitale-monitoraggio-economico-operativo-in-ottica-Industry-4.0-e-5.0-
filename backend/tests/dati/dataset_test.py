"""Dataset di test: una giornata della linea con numeri scelti a mano e risultati attesi calcolati a parte.

Anagrafica e parametri sono gli stessi dei dati iniziali del database. I calcoli sono riportati per esteso
perché servono anche a spiegare le formule.

Giornata di prova: 2 turni da 8 ore = 16 h disponibili per ogni macchina, nessuna manutenzione programmata,
quindi tempo pianificato = 16 h = 57.600 s. Le confezioni scorrono lungo la linea e ogni macchina scarta una
parte di ciò che riceve:

    macchina   prodotte   scartate   buone    fermi    funzionamento
    M1         25.600       100     25.500    1,0 h     15,0 h
    M2         25.500       300     25.200    1,5 h     14,5 h
    M3         25.200       400     24.800    2,0 h     14,0 h
    M4         24.800       200     24.600    1,0 h     15,0 h
    M5         24.600       100     24.500    0,5 h     15,5 h

Energia = potenza in funzione × ore di funzionamento + potenza a fermo × ore di fermo:
    M1  30 × 15   +   3 × 1    =   453,00 kWh
    M2  90 × 14,5 +  18 × 1,5  = 1.332,00 kWh
    M3 150 × 14   + 105 × 2    = 2.310,00 kWh
    M4  25 × 15   +   4 × 1    =   379,00 kWh
    M5  15 × 15,5 + 1,5 × 0,5  =   233,25 kWh
                          totale 4.707,25 kWh
"""

from app.kpi.formule import DatiMacchina, GrandezzeBase, ParametriEconomici

ORA = 3600
GIORNATA = 16 * ORA

MACCHINE = [
    DatiMacchina("M1", 1, 2400, 25, 0.25),
    DatiMacchina("M2", 2, 2200, 40, 0.25),
    DatiMacchina("M3", 3, 2000, 45, 0.25),
    DatiMacchina("M4", 4, 2200, 35, 0.29),
    DatiMacchina("M5", 5, 2600, 20, 0.29),
]
PER_CODICE = {m.codice: m for m in MACCHINE}

PARAMETRI = ParametriEconomici(
    prezzo_energia=0.20,
    costo_materia_conf=0.25,
    costo_imballo_conf=0.04,
    margine_conf=0.40,
    fattore_co2=0.20,
)

# Capacità della linea = macchina più lenta (M3) = 2.000 conf/h.
# Valore della produzione persa in un'ora di fermo = 2.000 × 0,40 = 800 €/h.
CAPACITA_LINEA = 2000


def _giorno(fermo_h: float, n_tot: int, n_scarti: int, kwh: float) -> GrandezzeBase:
    t_fermo = round(fermo_h * ORA)
    return GrandezzeBase(GIORNATA, 0, t_fermo, GIORNATA - t_fermo, n_tot, n_scarti, kwh)


GIORNO = {
    "M1": _giorno(1.0, 25600, 100, 453.0),
    "M2": _giorno(1.5, 25500, 300, 1332.0),
    "M3": _giorno(2.0, 25200, 400, 2310.0),
    "M4": _giorno(1.0, 24800, 200, 379.0),
    "M5": _giorno(0.5, 24600, 100, 233.25),
}

# --- Risultati attesi per l'essiccatoio M3 (capacità 2.000 conf/h, tempo ciclo ideale 1,8 s) ---
ATTESI_M3 = {
    "n_tot": 25200,
    "n_scarti": 400,
    "n_buoni": 24800,
    "produttivita_conf_h": 1550.0,  # 24.800 buone / 16 h
    "disponibilita": 0.875,  # 14 h di funzionamento / 16 h pianificate
    "prestazioni": 0.9,  # 25.200 × 1,8 s / 50.400 s di funzionamento
    "qualita": 24800 / 25200,  # 0,98413
    "oee": 0.775,  # 24.800 × 1,8 s / 57.600 s  (= 0,875 × 0,9 × 0,98413)
    "tasso_scarto": 400 / 25200,  # 1,587%
    "kwh": 2310.0,
    "kwh_conf": 2310 / 24800,  # 0,0931 kWh per confezione buona
    "costo_fermi_eur": 1690.0,  # 2 h × (45 €/h + 800 €/h)
    "co2_kg": 462.0,  # 2.310 × 0,20
    "co2_kg_conf": 462 / 24800,  # 0,0186 kg per confezione buona
    "saturazione": 0.875,  # 14 h / 16 h disponibili
    "costo_macchina_eur": 720.0,  # 16 h × 45 €/h
    "costo_energia_eur": 462.0,  # 2.310 × 0,20
    "costo_materia_eur": 100.0,  # 400 scarti × 0,25 €
    "costo_totale_eur": 1282.0,  # 720 + 462 + 100
    "costo_unitario_eur": 1282 / 24800,  # 0,0517 € per confezione buona
    "costo_scarti_eur": 100.0,  # 400 × 0,25 €
}

# --- Risultati attesi per la linea ---
# Uscita della linea: confezioni buone di M5 = 24.500. Scarti lungo la linea: 100 + 300 + 400 + 200 + 100 = 1.100.
# Confezioni avviate: 24.500 + 1.100 = 25.600 (proprio quelle entrate in M1).
_DISPONIBILITA_LINEA = 74 / 80  # 74 h di funzionamento sulle 80 h pianificate delle 5 macchine = 0,925
_QUALITA_LINEA = 24500 / 25600  # 0,95703
_OEE_LINEA = 24500 * 1.8 / 57600  # uscita × tempo ciclo del collo di bottiglia / tempo pianificato = 0,765625
ATTESI_LINEA = {
    "n_tot": 25600,
    "n_buoni": 24500,
    "n_scarti": 1100,
    "produttivita_conf_h": 1531.25,  # 24.500 / 16 h
    "disponibilita": _DISPONIBILITA_LINEA,
    "qualita": _QUALITA_LINEA,
    "oee": _OEE_LINEA,
    "prestazioni": _OEE_LINEA / (_DISPONIBILITA_LINEA * _QUALITA_LINEA),  # 0,86486
    "tasso_scarto": 1100 / 25600,  # 4,297%
    "kwh": 4707.25,
    "kwh_conf": 4707.25 / 24500,  # 0,1921 kWh per confezione
    # Fermi: ore × costo orario; per l'essiccatoio (collo di bottiglia) si aggiungono 800 €/h di produzione persa.
    #   M1 1 × 25 + M2 1,5 × 40 + M3 2 × (45 + 800) + M4 1 × 35 + M5 0,5 × 20 = 25 + 60 + 1.690 + 35 + 10
    "costo_fermi_eur": 1820.0,
    "co2_kg": 4707.25 * 0.20,  # 941,45 kg
    "co2_kg_conf": 4707.25 * 0.20 / 24500,  # 0,0384 kg per confezione
    "saturazione": 74 / 80,  # nessuna manutenzione: tempo disponibile = tempo pianificato
    "costo_macchina_eur": 2640.0,  # 16 h × 165 €/h (somma dei costi orari)
    "costo_energia_eur": 941.45,  # 4.707,25 × 0,20
    "costo_materia_eur": 7424.0,  # 25.600 confezioni avviate × (0,25 + 0,04) €
    "costo_totale_eur": 11005.45,  # 2.640 + 941,45 + 7.424
    "costo_unitario_eur": 11005.45 / 24500,  # 0,4492 € per confezione
    # Dettaglio: 100 × 0,25 + 300 × 0,25 + 400 × 0,25 + 200 × 0,29 + 100 × 0,29 = 25 + 75 + 100 + 58 + 29
    "costo_scarti_eur": 287.0,
}
