-- Schema del database: tabelle, vincoli e indici.
-- Gli script di questa cartella sono eseguiti in ordine alfabetico dal container PostgreSQL al primo avvio
-- con volume vuoto. Per ripartire da zero: docker compose down -v
--
-- Convenzioni:
--   * percentuali e rapporti sono memorizzati come frazioni tra 0 e 1 (0,65 = 65%);
--   * i tempi delle rilevazioni sono in secondi, l'energia in kWh, gli importi in euro;
--   * la quantità di prodotto si conta in confezioni da 500 g ("conf");
--   * gli orari sono timestamptz; giornata e turni si calcolano nel fuso Europe/Rome.

SET client_encoding = 'UTF8';

-- ---------------------------------------------------------------------------------------------------------
-- Macchinari
-- ---------------------------------------------------------------------------------------------------------

CREATE TABLE linea (
    id      serial PRIMARY KEY,
    codice  varchar(10)  NOT NULL UNIQUE,
    nome    varchar(100) NOT NULL
);

CREATE TABLE macchina (
    id                     serial PRIMARY KEY,
    linea_id               integer       NOT NULL REFERENCES linea (id),
    codice                 varchar(10)   NOT NULL UNIQUE,
    nome                   varchar(100)  NOT NULL,
    -- Posizione nella linea: 1 = prima macchina, la più alta è l'uscita della linea.
    ordine                 smallint      NOT NULL CHECK (ordine > 0),
    capacita_conf_h        numeric(8, 2) NOT NULL CHECK (capacita_conf_h > 0),
    -- Ricavato dalla capacità, così i due valori non possono mai essere incoerenti.
    tempo_ciclo_ideale_s   numeric(10, 6) GENERATED ALWAYS AS (3600 / capacita_conf_h) STORED,
    potenza_funz_kw        numeric(8, 2) NOT NULL CHECK (potenza_funz_kw >= 0),
    potenza_fermo_kw       numeric(8, 2) NOT NULL CHECK (potenza_fermo_kw >= 0),
    -- Costo sostenuto anche a macchina ferma: ammortamento, manutenzione ordinaria, quota di manodopera.
    costo_orario_eur       numeric(8, 2) NOT NULL CHECK (costo_orario_eur >= 0),
    scarto_nominale        numeric(5, 4) NOT NULL CHECK (scarto_nominale BETWEEN 0 AND 1),
    -- Valore perso per ogni confezione scartata su questa macchina (materia prima, più imballo a valle).
    costo_scarto_eur_conf  numeric(8, 4) NOT NULL CHECK (costo_scarto_eur_conf >= 0),
    UNIQUE (linea_id, ordine)
);

-- ---------------------------------------------------------------------------------------------------------
-- Rilevazioni
-- ---------------------------------------------------------------------------------------------------------

CREATE TABLE causale_fermo (
    codice       varchar(30)  PRIMARY KEY,
    descrizione  varchar(100) NOT NULL,
    -- true = fermo pianificato (manutenzione programmata): non penalizza la disponibilità né entra nel costo dei fermi.
    pianificata  boolean      NOT NULL
);

-- Una riga = un intervallo di campionamento di una macchina (60 s nello storico, 5 s nel live).
CREATE TABLE rilevazione (
    id                   bigserial PRIMARY KEY,
    macchina_id          integer      NOT NULL REFERENCES macchina (id),
    inizio               timestamptz  NOT NULL,
    durata_s             integer      NOT NULL CHECK (durata_s > 0),
    pezzi                integer      NOT NULL CHECK (pezzi >= 0),
    scarti               integer      NOT NULL CHECK (scarti >= 0),
    t_funz_s             integer      NOT NULL CHECK (t_funz_s >= 0),
    t_fermo_s            integer      NOT NULL CHECK (t_fermo_s >= 0),
    causale_codice       varchar(30)  REFERENCES causale_fermo (codice),
    kwh                  numeric(10, 4) NOT NULL CHECK (kwh >= 0),
    -- Tempo medio per confezione nell'intervallo; assente se la macchina non ha prodotto.
    tempo_ciclo_medio_s  numeric(10, 4) CHECK (tempo_ciclo_medio_s > 0),
    fonte                varchar(20)  NOT NULL DEFAULT 'generatore' CHECK (fonte IN ('generatore', 'csv')),
    ricevuta_il          timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT rilevazione_scarti_entro_pezzi CHECK (scarti <= pezzi),
    CONSTRAINT rilevazione_tempi_coerenti CHECK (t_funz_s + t_fermo_s = durata_s),
    -- La causale c'è se e solo se nell'intervallo c'è stato un fermo.
    CONSTRAINT rilevazione_causale_se_fermo CHECK ((t_fermo_s > 0) = (causale_codice IS NOT NULL)),
    -- Una macchina non può avere due rilevazioni con lo stesso inizio: rende innocui i reinvii dello stesso blocco.
    CONSTRAINT rilevazione_unica UNIQUE (macchina_id, inizio)
);

-- ---------------------------------------------------------------------------------------------------------
-- Produzione: grandezze di base sommate per giorno e macchina. Settimana e mese si ottengono sommando queste righe.
-- ---------------------------------------------------------------------------------------------------------

CREATE TABLE produzione_giornaliera (
    data                date         NOT NULL,
    macchina_id         integer      NOT NULL REFERENCES macchina (id),
    t_disp_s            integer      NOT NULL CHECK (t_disp_s >= 0),  -- tempo di turno da calendario
    t_man_s             integer      NOT NULL CHECK (t_man_s >= 0),   -- fermi pianificati
    t_fermo_s           integer      NOT NULL CHECK (t_fermo_s >= 0), -- fermi non pianificati
    t_funz_s            integer      NOT NULL CHECK (t_funz_s >= 0),
    n_tot               integer      NOT NULL CHECK (n_tot >= 0),
    n_scarti            integer      NOT NULL CHECK (n_scarti >= 0 AND n_scarti <= n_tot),
    kwh                 numeric(12, 4) NOT NULL CHECK (kwh >= 0),
    ultima_rilevazione  timestamptz,
    -- true per il giorno in corso: i valori crescono man mano che arrivano rilevazioni.
    parziale            boolean      NOT NULL DEFAULT false,
    PRIMARY KEY (data, macchina_id)
);

-- ---------------------------------------------------------------------------------------------------------
-- Costi e configurazione
-- ---------------------------------------------------------------------------------------------------------

-- Parametri economici e operativi: sono dati e non costanti nel codice, così si possono cambiare e ricalcolare.
CREATE TABLE parametro (
    chiave       varchar(50)    PRIMARY KEY,
    valore       numeric(12, 4) NOT NULL,
    unita        varchar(20)    NOT NULL,
    descrizione  varchar(200)   NOT NULL
);

CREATE TABLE soglia (
    id      serial PRIMARY KEY,
    kpi     varchar(30)    NOT NULL,
    ambito  varchar(10)    NOT NULL CHECK (ambito IN ('linea', 'macchina')),
    -- min: fuori soglia se il valore è inferiore; max: fuori soglia se è superiore.
    verso   varchar(3)     NOT NULL CHECK (verso IN ('min', 'max')),
    valore  numeric(12, 4) NOT NULL,
    UNIQUE (kpi, ambito)
);

-- ---------------------------------------------------------------------------------------------------------
-- Indicatori: KPI giornalieri, una riga per giorno e per ambito (ogni macchina e la linea).
-- I KPI non calcolabili (denominatore zero) restano NULL.
-- ---------------------------------------------------------------------------------------------------------

CREATE TABLE indicatore (
    id                    bigserial PRIMARY KEY,
    data                  date      NOT NULL,
    linea_id              integer   REFERENCES linea (id),
    macchina_id           integer   REFERENCES macchina (id),
    n_tot                 integer   NOT NULL,
    n_buoni               integer   NOT NULL,
    n_scarti              integer   NOT NULL,
    produttivita_conf_h   numeric(10, 2),
    disponibilita         numeric(6, 5) CHECK (disponibilita BETWEEN 0 AND 1),
    prestazioni           numeric(6, 5) CHECK (prestazioni BETWEEN 0 AND 1),
    qualita               numeric(6, 5) CHECK (qualita BETWEEN 0 AND 1),
    oee                   numeric(6, 5) CHECK (oee BETWEEN 0 AND 1),
    tasso_scarto          numeric(6, 5) CHECK (tasso_scarto BETWEEN 0 AND 1),
    kwh                   numeric(12, 4) NOT NULL,
    kwh_conf              numeric(10, 6),
    costo_fermi_eur       numeric(12, 2) NOT NULL,
    co2_kg                numeric(12, 4) NOT NULL,
    co2_kg_conf           numeric(10, 6),
    saturazione           numeric(6, 5) CHECK (saturazione BETWEEN 0 AND 1),
    costo_macchina_eur    numeric(12, 2) NOT NULL,
    costo_energia_eur     numeric(12, 2) NOT NULL,
    costo_materia_eur     numeric(12, 2) NOT NULL,
    costo_totale_eur      numeric(12, 2) NOT NULL,
    costo_unitario_eur    numeric(10, 4),
    -- Dettaglio: valore perso negli scarti, già compreso nel costo della materia.
    costo_scarti_eur      numeric(12, 2) NOT NULL,
    parziale              boolean     NOT NULL DEFAULT false,
    calcolato_il          timestamptz NOT NULL DEFAULT now(),
    -- Ambito: o la linea o una macchina, mai entrambe né nessuna.
    CONSTRAINT indicatore_un_solo_ambito CHECK ((linea_id IS NULL) <> (macchina_id IS NULL)),
    CONSTRAINT indicatore_unico UNIQUE NULLS NOT DISTINCT (data, linea_id, macchina_id)
);

-- ---------------------------------------------------------------------------------------------------------
-- Anomalie: fermi (ricavati dalle rilevazioni), KPI fuori soglia, dati incoerenti o mancanti.
-- ---------------------------------------------------------------------------------------------------------

CREATE TABLE anomalia (
    id              bigserial PRIMARY KEY,
    tipo            varchar(10)  NOT NULL CHECK (tipo IN ('fermo', 'soglia', 'dato')),
    -- Giorno di riferimento: permette di ricostruire le anomalie di un giorno quando lo si ricalcola.
    data            date         NOT NULL,
    macchina_id     integer      REFERENCES macchina (id),  -- NULL = riferita alla linea
    inizio          timestamptz,
    fine            timestamptz,
    causale_codice  varchar(30)  REFERENCES causale_fermo (codice),
    kpi             varchar(30),
    valore          numeric(14, 4),
    soglia          numeric(14, 4),
    descrizione     varchar(300) NOT NULL,
    CONSTRAINT anomalia_intervallo_valido CHECK (fine IS NULL OR inizio IS NULL OR fine >= inizio),
    CONSTRAINT anomalia_fermo_con_causale CHECK (tipo <> 'fermo' OR (causale_codice IS NOT NULL AND inizio IS NOT NULL)),
    CONSTRAINT anomalia_soglia_con_kpi CHECK (tipo <> 'soglia' OR (kpi IS NOT NULL AND valore IS NOT NULL))
);

-- ---------------------------------------------------------------------------------------------------------
-- Indici per le interrogazioni frequenti. Quelli creati dai vincoli UNIQUE coprono già rilevazione per macchina e
-- intervallo di tempo, e indicatore per data.
-- ---------------------------------------------------------------------------------------------------------

CREATE INDEX anomalia_per_data ON anomalia (data, tipo);
CREATE INDEX anomalia_per_macchina ON anomalia (macchina_id, inizio);
