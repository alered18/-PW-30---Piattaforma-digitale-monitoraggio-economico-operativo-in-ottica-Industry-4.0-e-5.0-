# PW 30 — Monitoraggio economico-operativo di un processo produttivo

Prototipo per il project work della traccia 30 (Università Pegaso, L-31). Simula una linea di un pastificio, raccoglie
i dati delle macchine e li trasforma in indicatori come OEE, scarti, consumi e costo dei fermi.

La linea ha cinque macchine in serie (impastatrice, trafila, essiccatoio, confezionatrice, pallettizzatore) e lavora
dal lunedì al venerdì dalle 6 alle 22. Macchine, costi e parametri sono ipotesi, non dati di un'azienda reale.

## Struttura
- `generator/`: generatore dei dati simulati (Python), invia le rilevazioni al back-end tramite le API
- `backend/`: API REST e calcolo dei KPI (Python, FastAPI)
- `frontend/`: dashboard (Angular, Angular Material, ECharts)
- `database/`: schema, dati iniziali e un file CSV di esempio (PostgreSQL)

## Avvio
Serve Docker Desktop, o Docker con Compose v2. Dalla radice del repository, in Git Bash o in un terminale Linux/macOS:

```bash
cp .env.example .env
docker compose up --build -d
docker compose logs -f generator
```

Al primo avvio il generatore crea 90 giorni di storico, circa 300.000 rilevazioni, in qualche minuto. Quando nel log
compare `Completato` i dati sono pronti.

- Dashboard: http://localhost:8080
- Documentazione delle API: http://localhost:8010/api/docs

Comandi utili:

```bash
docker compose down      # ferma tutto, i dati restano
docker compose up -d     # riavvia e recupera i dati mancanti
docker compose down -v   # ferma tutto e cancella i dati
```

## Dashboard
- **Cruscotto**: KPI, grafici nel tempo, fermi per causale e alert, con filtri per periodo, macchina e granularità
- **Operatore**: stato delle macchine e avanzamento del turno in corso
- **Soglie**: modifica delle soglie dei KPI
- **Importa CSV**: caricamento di un file di rilevazioni

Se il periodo scelto comprende oggi, il cruscotto si aggiorna da solo ogni 10 secondi.

## Generatore
Si configura con le variabili `GEN_*` di `.env`, spiegate in `.env.example`. Per applicare una modifica basta
`docker compose up -d`. La modalità si sceglie con `GEN_MODALITA`:

- `auto` (predefinita): crea lo storico se il database è vuoto, altrimenti recupera i dati mancanti; poi passa al live
- `storico`: crea lo storico e si ferma
- `live`: invia una rilevazione per macchina ogni 5 secondi, solo in orario di turno
- `csv`: rigenera il file CSV di esempio; si avvia fuori da Docker, con il back-end attivo

Lo storico contiene tre scenari: degrado della trafila, una settimana di mancanze di materiale sull'impastatrice e un
guasto grave dell'essiccatoio. Le date sono nel log del generatore (`Scenario ...`). Con gli stessi `GEN_SEME` e
`GEN_DATA_FINE` lo storico è sempre identico; va generato su un database vuoto.

## Import CSV
Il file di esempio ha 100 righe valide e 3 errate. Si importa dalla pagina **Importa CSV** oppure con:

```bash
curl -F "file=@database/esempi/rilevazioni_esempio.csv" http://localhost:8010/api/rilevazioni/import
```

I dati sono del 12/01/2026 e coprono 20 minuti, quindi quel giorno i KPI risultano molto bassi. Le colonne richieste
sono elencate nella pagina; il limite è di 10.000 righe e 5 MB.

## Test
Servono Python 3.14 e Node.js 22. Si preparano gli ambienti una volta sola, poi si lancia tutto con `test.sh`, che
avvia anche il database:

```bash
(cd backend && python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]")
(cd generator && python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]")
(cd frontend && npm ci)
./test.sh
```

## Limiti
- I dati sono simulati e i parametri economici sono ipotesi.
- Dopo un riavvio la simulazione riparte da uno stato nuovo e il recupero dei dati mancanti non applica gli scenari.
- KPI e alert del giorno in corso sono calcolati su dati parziali.
