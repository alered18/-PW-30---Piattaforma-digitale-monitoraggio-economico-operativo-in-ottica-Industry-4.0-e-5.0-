# PW 30 — Monitoraggio economico-operativo di un processo produttivo

Prototipo universitario (Università Pegaso, L-31, traccia PW 30): piattaforma che simula, raccoglie, memorizza ed
elabora i dati operativi di una linea di un pastificio simulato e li trasforma in indicatori economico-operativi.

La linea ha cinque macchine in serie: impastatrice (M1), trafila (M2), essiccatoio (M3, la più lenta), confezionatrice
(M4) e pallettizzatore (M5). Lavora su due turni, dal lunedì al venerdì dalle 6 alle 22. Macchine, costi e parametri
sono ipotesi realistiche, non dati di un'azienda reale.

## Componenti
| Cartella o file | Contenuto | Tecnologia |
|---|---|---|
| `generator/` | generatore di dati simulati: storico, tempo reale, file CSV di esempio | Python |
| `backend/` | API REST, validazione dei dati, calcolo e memorizzazione dei KPI | Python, FastAPI, SQLAlchemy |
| `database/init/` | schema del database e dati iniziali (linea, macchine, causali di fermo, parametri, soglie) | PostgreSQL |
| `database/esempi/` | file CSV di esempio per l'import | CSV |
| `frontend/` | dashboard web | Angular, Angular Material, ECharts |
| `docker-compose.yml` | avvio dei quattro componenti | Docker Compose |
| `.env.example` | modello della configurazione (porte, credenziali, impostazioni del generatore) | |
| `test.sh` | esecuzione di tutti i test automatici | Bash |

Il generatore è un programma separato: invia le rilevazioni al back-end tramite le API e non accede al database.

## Prerequisiti
- **Docker Desktop** (o Docker Engine con Compose v2), per avviare il prototipo. Non serve altro.
- Solo per eseguire i test, rigenerare il CSV di esempio o sviluppare: **Python 3.14**, **Node.js 22** con npm.

I comandi di questo file sono scritti per una shell bash: su Windows Git Bash (installato con Git), su Linux e macOS
il terminale. Dal Prompt dei comandi di Windows, per creare il file di configurazione si usa
`copy .env.example .env`; i comandi `docker compose` sono gli stessi.

## Avvio
Dalla radice del repository:

```bash
cp .env.example .env          # configurazione: porte, password del database, generatore
docker compose up --build -d
```

Al primo avvio vengono costruite le immagini e creato il database; poi il generatore produce 90 giorni di storico
(circa 300.000 rilevazioni, inviate un giorno alla volta) e passa al tempo reale. Lo storico richiede qualche
minuto e si può seguire con

```bash
docker compose logs -f generator
```

Quando compare il messaggio `Live dalle ...` lo storico è completo. Da quel momento arrivano nuovi dati ogni 5
secondi, ma solo in orario di turno (dal lunedì al venerdì, 6-22).

- Dashboard: http://localhost:8080
- Documentazione delle API (Swagger): http://localhost:8010/api/docs

| Operazione | Comando |
|---|---|
| Fermare tutto (i dati restano) | `docker compose down` |
| Riavviare | `docker compose up -d` (il generatore recupera i dati mancanti e riprende il live, se `GEN_DATA_FINE` è vuota) |
| Ripartire da un database vuoto (cancella tutti i dati) | `docker compose down -v` e poi `docker compose up -d` |
| Log di un componente | `docker compose logs -f backend` (o `generator`, `db`, `frontend`) |

Le porte esposte sul PC si cambiano in `.env` (`PORTA_DB`, `PORTA_BACKEND`, `PORTA_FRONTEND`).

## Uso della dashboard
| Pagina | Contenuto |
|---|---|
| **Cruscotto** | KPI del periodo (produzione, produttività oraria, OEE con disponibilità, prestazioni e qualità, scarti, consumo energetico totale e per confezione, CO₂ stimata, costo dei fermi, saturazione, costo di produzione), grafici dell'andamento nel tempo, ripartizione dei fermi per causale (Pareto), alert dei KPI fuori soglia. Filtri: periodo, linea o singola macchina, granularità giorno / settimana / mese. Se il periodo comprende oggi, i dati si aggiornano da soli ogni 10 secondi |
| **Operatore** | vista semplificata del turno in corso: stato di ogni macchina (in funzione, ferma con la causale, nessun dato recente), confezioni prodotte rispetto all'obiettivo di turno, scarti, alert |
| **Soglie** | soglie dei KPI (minimo o massimo) per la linea e per le macchine (un valore comune a tutte); una modifica ricalcola gli alert |
| **Importa CSV** | caricamento di un file di rilevazioni ed esito: righe memorizzate, già presenti, scartate con il motivo |

I KPI di un periodo si calcolano sommando le grandezze di base dei giorni (tempi, pezzi, energia, costi) e facendo il
rapporto alla fine; il periodo in corso è marcato come "parziale". Un KPI che non si può calcolare (ad esempio il
consumo per confezione in un giorno senza produzione) è mostrato come "n.d.".

## Generatore
Il generatore si configura con le variabili `GEN_*` di `.env`:

| Variabile | Significato | Predefinito |
|---|---|---|
| `GEN_MODALITA` | `auto`, `storico`, `live` o `csv` (vedi sotto) | `auto` |
| `GEN_GIORNI` | giorni di storico | `90` |
| `GEN_INTERVALLO_LIVE_S` | secondi tra due rilevazioni in live (deve dividere 60) | `5` |
| `GEN_SEME` | seme dei numeri casuali | `42` |
| `GEN_DATA_FINE` | fine dello storico, ad esempio `2026-10-16T22:00:00+02:00`; vuota = momento dell'avvio | vuota |
| `GEN_SCENARI` | scenari dello storico separati da virgole: `degrado_trafila`, `mancanze_materiale`, `guasto_grave`; `nessuno` per toglierli (vuota = tutti) | tutti e tre |
| `GEN_FILE_CSV` | file scritto dalla modalità `csv` (solo fuori da Docker) | `../database/esempi/rilevazioni_esempio.csv` |

**Modalità**
- `auto` (usata da Docker Compose): con il database vuoto genera lo storico; altrimenti colma il buco tra l'ultima
  rilevazione e il momento attuale. Poi passa al live. Con `GEN_DATA_FINE` impostata non passa al live: si ferma
  dopo lo storico o dopo il recupero fino a quella data.
- `storico`: genera solo lo storico, un giorno alla volta, e termina.
- `live`: invia ogni `GEN_INTERVALLO_LIVE_S` secondi una rilevazione per macchina, solo in orario di turno; fuori
  turno attende l'apertura successiva.
- `csv`: scrive un file CSV di esempio nel formato dell'import (100 righe valide del 12/01/2026 e 3 non valide).

Per cambiare modalità o parametri si modifica `.env` e si ricrea il generatore con `docker compose up -d`. Lo storico
va generato su un database vuoto. Con gli stessi `GEN_SEME`, `GEN_DATA_FINE`, `GEN_GIORNI` e `GEN_SCENARI` lo storico
è identico a ogni prova (utile ad esempio per gli screenshot): si fissa `GEN_DATA_FINE` e si riparte da zero con
`docker compose down -v` e `docker compose up -d`.

**Scenari.** Lo storico contiene tre situazioni riconoscibili, posizionate rispetto alla data di fine: tre settimane
di degrado della trafila (scarto crescente fino a circa il 6%, poi manutenzione), una settimana di mancanze di
materiale sull'impastatrice e un guasto di 4-6 ore dell'essiccatoio. Le date esatte compaiono nel log del generatore
(`Scenario ...`).

**File CSV e import.** Il file di esempio è già nel repository (`database/esempi/rilevazioni_esempio.csv`) e si
importa dalla pagina **Importa CSV** oppure con le API:

```bash
curl -F "file=@database/esempi/rilevazioni_esempio.csv" http://localhost:8010/api/rilevazioni/import
```

I dati importati sono del 12/01/2026: per vederli nel cruscotto si sceglie quel giorno come periodo. Il file contiene
solo 20 minuti di dati, quindi in quel giorno i KPI risultano molto bassi e compaiono alert.

Formato: testo UTF-8, valori separati da virgole, decimali con il punto, intestazione
`macchina,inizio,durata_s,pezzi,scarti,t_funz_s,t_fermo_s,causale,kwh,tempo_ciclo_medio_s` (`causale` e
`tempo_ciclo_medio_s` possono restare vuote); al massimo 10.000 righe e 5 MB. Le righe valide sono memorizzate e i KPI
dei giorni toccati ricalcolati; le righe già presenti sono ignorate; quelle non valide sono elencate con il motivo.

Per rigenerare il file (sovrascrive quello del repository) la modalità `csv` si avvia fuori da Docker, con Python e
con il back-end attivo, perché legge l'anagrafica delle macchine dalle API. Fuori da Docker il generatore non legge
il `.env` della radice: le variabili `GEN_*` si passano sulla riga di comando.

```bash
cd generator
python -m venv .venv && .venv/Scripts/python -m pip install -e .     # .venv/bin/python su Linux e macOS
GEN_MODALITA=csv .venv/Scripts/python main.py
```

## Test
Tutti i test automatici (back-end, generatore, front-end) si lanciano con un solo comando dalla radice del
repository, da Git Bash su Windows o da un terminale Linux/macOS:

```bash
./test.sh
```

Lo script avvia il servizio `db` se non è attivo (i test del back-end usano il database separato `pw30_test`,
indicato da `DATABASE_URL_TEST` in `.env`), esegue le tre serie e stampa il riepilogo; termina con errore se una
serie fallisce. Richiede gli ambienti di sviluppo locali:

```bash
# su Linux e macOS il Python dell'ambiente è .venv/bin/python
(cd backend && python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]")
(cd generator && python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]")
(cd frontend && npm ci)
```

| Serie | Cosa verifica | Comando singolo |
|---|---|---|
| Back-end | formule dei KPI e casi limite, calendario, soglie; API su database: ricezione e validazione, ricalcolo, KPI per periodo, fermi, alert, import CSV, vista operatore | `cd backend && .venv/Scripts/python -m pytest -q` |
| Generatore | dati riproducibili e coerenti, valori plausibili su 90 giorni, scenari, modalità live | `cd generator && .venv/Scripts/python -m pytest -q` |
| Front-end | cruscotto (formati, "n.d.", soglie e alert) e vista operatore | `cd frontend && npx ng test --watch=false` |

## Misure del sistema
Il prototipo fornisce alcune misure reali su raccolta, elaborazione e memorizzazione dei dati.

| Misura | Dove si legge |
|---|---|
| Spazio del database e di ogni tabella, righe, byte per riga | `GET /api/sistema/misure` → `database_byte`, `tabelle` |
| Dimensione media di una rilevazione in JSON e su disco | `GET /api/sistema/misure` → `rilevazione` |
| Rilevazioni per intervallo di campionamento (60 s storico, 5 s live) | `GET /api/sistema/misure` → `campionamento` |
| Tempo di ricalcolo di un giorno (produzione, KPI, fermi, alert) | `GET /api/sistema/misure` → `ricalcolo_giorno_ms`; log `misure` del back-end |
| Tempo di risposta e dimensione delle risposte delle API, KPI per granularità | `GET /api/sistema/misure` → `richieste_ms`; log `misure` del back-end |
| Tempo di invio di un giorno di storico e di un invio live | `docker compose logs generator` |

I tempi sono in millisecondi e riguardano le ultime 100 richieste di ogni tipo dall'avvio del back-end (si azzerano
al riavvio). Esempio:

```bash
curl http://localhost:8010/api/sistema/misure
docker compose logs backend | grep misure
```

Per confrontare il calcolo dei KPI per giorno, settimana e mese basta aprire il cruscotto e cambiare la granularità,
oppure chiamare `GET /api/kpi` con lo stesso periodo e `granularita` diversa.

## Sviluppo senza Docker
Con il database avviato in Docker (`docker compose up -d db`) i singoli componenti si possono eseguire sul PC:

```bash
# Back-end su http://localhost:8010 (DATABASE_URL verso la porta del database esposta sul PC)
cd backend
DATABASE_URL=postgresql+psycopg://pw30:cambiami@localhost:5432/pw30 .venv/Scripts/uvicorn app.main:app --reload --port 8010

# Front-end su http://localhost:4200, con le chiamate /api inoltrate al back-end su localhost:8010
cd frontend
npx ng serve

# Generatore verso il back-end sul PC (indirizzo predefinito http://localhost:8010/api)
cd generator
GEN_MODALITA=live .venv/Scripts/python main.py
```

Gli ambienti Python e le dipendenze del front-end si installano come indicato nella sezione "Test". Se il back-end
gira anche in Docker sulla stessa porta, va fermato prima (`docker compose stop backend generator`).

## Risoluzione dei problemi
| Problema | Soluzione |
|---|---|
| `port is already allocated` all'avvio | La porta è occupata da un altro programma: cambiare `PORTA_DB`, `PORTA_BACKEND` o `PORTA_FRONTEND` in `.env`. Se si cambia `PORTA_DB`, aggiornare anche la porta in `DATABASE_URL_TEST`. I comandi della sezione "Sviluppo senza Docker" e il proxy di `ng serve` (`frontend/proxy.conf.json`) usano le porte predefinite e vanno adattati allo stesso modo |
| La dashboard è vuota subito dopo il primo avvio | Il generatore sta ancora producendo lo storico: attendere qualche minuto e seguire `docker compose logs -f generator` |
| Nessun dato nuovo, vista operatore con "nessun dato recente" | Fuori dall'orario di turno (sere, sabato e domenica) il live non invia dati: è il comportamento previsto. I dati riprendono all'apertura del turno |
| Il generatore si ferma con `Back-end non raggiungibile` | Controllare `docker compose logs backend`; il generatore riparte da solo quando il back-end è pronto |
| Il back-end non si connette al database dopo aver cambiato la password | La password in `.env` vale solo alla creazione del database: dopo averla cambiata (in `POSTGRES_PASSWORD`, `DATABASE_URL` e `DATABASE_URL_TEST`) ripartire da zero con `docker compose down -v` |
| I test del back-end vengono saltati (`skipped`) | Il database non è raggiungibile o `DATABASE_URL_TEST` manca in `.env`: avviare `docker compose up -d db` e controllare `.env` |
| `./test.sh: Permission denied` | Lanciarlo con `bash test.sh` |
| Pagina della dashboard non aggiornata dopo una modifica del codice | Ricostruire le immagini: `docker compose up --build -d` |

## Limiti noti
- **Dati simulati e parametri ipotetici.** Macchine, costi, prezzi e fattore di emissione sono ipotesi realistiche
  per un pastificio di piccola-media dimensione, non dati di un'azienda reale. I parametri economici sono nel
  database (tabella `parametro`, API `/api/parametri`): cambiandoli si ricalcolano i KPI con `POST /api/kpi/ricalcola`.
- **Ripresa del generatore.** Dopo un riavvio la linea simulata riparte da uno stato nuovo: buffer e fermi in corso
  non proseguono quelli già memorizzati. Il recupero dei giorni mancanti non applica gli scenari, che riguardano
  solo lo storico.
- **Cruscotto aperto a lungo.** Se resta aperto oltre la mezzanotte, il nuovo giorno entra nel periodo solo quando si
  cambia un filtro o si ricarica la pagina.
- **Alert del giorno in corso.** Sono calcolati sui valori parziali del giorno: durante il turno un alert può
  comparire e poi sparire.
- **Cambio dell'ora legale.** Con il database vuoto, nella notte del cambio d'ora il live può restare fermo circa
  un'ora; succede fuori dall'orario di turno, quindi non mancano dati.
- **Import CSV.** Il file è letto interamente in memoria: per questo i limiti di 5 MB e 10.000 righe.
