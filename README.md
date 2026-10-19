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
