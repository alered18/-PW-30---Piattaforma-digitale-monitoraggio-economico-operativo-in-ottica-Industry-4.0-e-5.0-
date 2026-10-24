# PW 30 — Monitoraggio economico-operativo di un processo produttivo

Prototipo universitario (Università Pegaso, L-31, traccia PW 30): piattaforma che simula, raccoglie, memorizza ed
elabora i dati operativi di una linea di un pastificio simulato e li trasforma in indicatori economico-operativi.

## Componenti
| Cartella | Componente | Tecnologia |
|---|---|---|
| `generator/` | generatore di dati simulati | Python |
| `backend/` | API REST e calcolo dei KPI | Python, FastAPI |
| `database/` | schema e dati iniziali | PostgreSQL |
| `frontend/` | dashboard web | Angular, Angular Material |
| `docs/` | requisiti, architettura, decisioni, piano | Markdown |

## Avvio rapido
Prerequisito: Docker Desktop.

```bash
cp .env.example .env          # poi, se serve, cambiare porte e password in .env
docker compose up --build
```

- Dashboard: http://localhost:8080
- Documentazione API: http://localhost:8010/api/docs

Per ripartire da un database vuoto: `docker compose down -v`.

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
