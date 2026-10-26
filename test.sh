#!/usr/bin/env bash
# Esegue tutti i test automatici: back-end, generatore e front-end, poi stampa il riepilogo.
# Si lancia dalla radice del repository con ./test.sh (Git Bash su Windows, oppure Linux e macOS).
# Richiede gli ambienti Python di backend/ e generator/ e le dipendenze di frontend/ (vedi README).
# I test del back-end usano il database di test nel container db, che viene avviato se non è già attivo.

set -u
cd "$(dirname "$0")"

# Python dell'ambiente virtuale della cartella corrente: Scripts su Windows, bin su Linux e macOS.
python_venv() {
  if [ -x .venv/Scripts/python ]; then echo .venv/Scripts/python; else echo .venv/bin/python; fi
}

test_backend() { cd backend && "$(python_venv)" -m pytest -q; }
test_generatore() { cd generator && "$(python_venv)" -m pytest -q; }
test_frontend() { cd frontend && npx ng test --watch=false; }

riepilogo=()
esito=0

# Ogni serie gira in una sottoshell, così il cambio di cartella non si propaga alle successive.
esegui() {
  echo
  echo "=== $1 ==="
  if ( "$2" ); then
    riepilogo+=("$1: superati")
  else
    riepilogo+=("$1: FALLITI")
    esito=1
  fi
}

echo "Avvio del database (servizio db)..."
if ! docker compose up -d --wait db; then
  echo "Database non avviato: i test del back-end non possono girare."
  exit 1
fi

esegui "Back-end" test_backend
esegui "Generatore" test_generatore
esegui "Front-end" test_frontend

echo
echo "=== Riepilogo ==="
printf '%s\n' "${riepilogo[@]}"
exit "$esito"
