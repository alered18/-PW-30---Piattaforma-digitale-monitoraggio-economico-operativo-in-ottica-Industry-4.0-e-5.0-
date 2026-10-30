-- Dati iniziali: la linea del pastificio, le sue macchine, le causali di fermo, i parametri economici e le soglie.
-- I valori sono ipotesi plausibili per una PMI italiana che produce pasta secca, non dati reali.

SET client_encoding = 'UTF8';

INSERT INTO linea (codice, nome) VALUES
    ('L1', 'Linea pasta corta');

-- Capacità in confezioni da 500 g all'ora. L'essiccatoio (M3) è la macchina più lenta e quindi il collo di
-- bottiglia: la linea non può produrre più di 2.000 conf/h. Il consumo a fermo dell'essiccatoio è alto perché
-- resta in temperatura. Il costo di uno scarto cresce dopo il confezionamento perché si perde anche l'imballo.
INSERT INTO macchina (linea_id, codice, nome, ordine, capacita_conf_h, potenza_funz_kw, potenza_fermo_kw,
                      costo_orario_eur, scarto_nominale, costo_scarto_eur_conf)
SELECT l.id, m.codice, m.nome, m.ordine, m.capacita, m.p_funz, m.p_fermo, m.costo_h, m.scarto, m.costo_scarto
FROM linea l
CROSS JOIN (VALUES
    ('M1', 'Impastatrice',      1, 2400, 30,  3.0, 25, 0.003, 0.25),
    ('M2', 'Trafila',           2, 2200, 90, 18.0, 40, 0.010, 0.25),
    ('M3', 'Essiccatoio',       3, 2000, 150, 105.0, 45, 0.015, 0.25),
    ('M4', 'Confezionatrice',   4, 2200, 25,  4.0, 35, 0.008, 0.29),
    ('M5', 'Pallettizzatore',   5, 2600, 15,  1.5, 20, 0.001, 0.29)
) AS m (codice, nome, ordine, capacita, p_funz, p_fermo, costo_h, scarto, costo_scarto)
WHERE l.codice = 'L1';

INSERT INTO causale_fermo (codice, descrizione, pianificata) VALUES
    ('guasto',              'Guasto',                    false),
    ('setup',               'Setup / cambio formato',    false),
    ('mancanza_materiale',  'Mancanza materiale',        false),
    ('manutenzione',        'Manutenzione programmata',  true),
    ('micro_fermata',       'Micro-fermata',             false);

INSERT INTO parametro (chiave, valore, unita, descrizione) VALUES
    ('prezzo_energia',          0.20,  '€/kWh',     'Prezzo dell''energia elettrica per un''utenza non domestica'),
    ('costo_materia_conf',      0.25,  '€/conf',    'Semola di grano duro per una confezione (0,5 kg a 0,50 €/kg)'),
    ('costo_imballo_conf',      0.04,  '€/conf',    'Film, quota di cartone e pallet per una confezione'),
    ('prezzo_vendita_conf',     0.75,  '€/conf',    'Prezzo di vendita franco stabilimento'),
    -- Il valore della produzione persa in un'ora di fermo non è memorizzato: si ricava come capacità della linea
    -- (macchina più lenta) × margine, così resta coerente se uno dei due cambia (2.000 conf/h × 0,40 € = 800 €/h).
    ('margine_conf',            0.40,  '€/conf',    'Margine di contribuzione per confezione'),
    ('fattore_co2',             0.20,  'kgCO₂/kWh', 'Emissioni medie dei consumi elettrici nazionali'),
    ('peso_conf',               0.5,   'kg',        'Peso di una confezione'),
    ('quota_obiettivo_turno',   0.75,  'frazione',  'Obiettivo di turno come quota della capacità di linea in 8 ore');

-- Soglie di default: le percentuali sono frazioni (0.65 = 65%).
INSERT INTO soglia (kpi, ambito, verso, valore) VALUES
    ('oee',             'linea',    'min', 0.65),
    ('oee',             'macchina', 'min', 0.65),
    ('disponibilita',   'macchina', 'min', 0.85),
    ('tasso_scarto',    'linea',    'max', 0.05),
    ('tasso_scarto',    'macchina', 'max', 0.03),
    ('kwh_conf',        'linea',    'max', 0.25),
    ('costo_fermi_eur', 'linea',    'max', 2500),
    ('saturazione',     'macchina', 'min', 0.70);
