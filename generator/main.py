"""Punto di ingresso del generatore.

Modalità disponibili:
    storico   simula gli ultimi N giorni, una rilevazione al minuto per macchina, e li invia un giorno alla volta.
"""

import logging
import sys
import time
from datetime import datetime, timedelta

from client_api import ClientApi, ErroreApi
from config import Impostazioni
from simulatore.calendario import FUSO
from simulatore.flusso import simula_storico
from simulatore.macchina import DatiMacchina

log = logging.getLogger("generatore")


def storico(client: ClientApi, impostazioni: Impostazioni) -> None:
    macchine = [DatiMacchina.da_api(m) for m in client.macchine()]
    fine = impostazioni.data_fine or datetime.now(FUSO)
    # Una data di fine senza fuso orario vale come ora di Roma, anche dentro il container (che è in UTC).
    fine = (fine.replace(tzinfo=FUSO) if fine.tzinfo is None else fine.astimezone(FUSO)).replace(second=0, microsecond=0)
    inizio = fine.date() - timedelta(days=impostazioni.giorni - 1)
    log.info("Storico dal %s al %s (seme %d)", inizio, fine, impostazioni.seme)
    avvio = time.perf_counter()
    totale = 0
    for giorno, blocco in simula_storico(macchine, impostazioni.seme, inizio, fine):
        inviato = time.perf_counter()
        esito = client.invia(blocco)
        totale += esito["memorizzate"]
        log.info("%s: %d rilevazioni memorizzate, %d già presenti (%.2f s)",
                 giorno, esito["memorizzate"], esito["duplicate"], time.perf_counter() - inviato)
    log.info("Storico completato: %d rilevazioni in %.1f s", totale, time.perf_counter() - avvio)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    impostazioni = Impostazioni()
    log.info("Avvio in modalità '%s', API %s", impostazioni.modalita, impostazioni.api_url)
    client = ClientApi(impostazioni.api_url)
    if not client.attendi():
        log.error("Back-end non raggiungibile su %s", impostazioni.api_url)
        return 1
    try:
        if impostazioni.modalita == "storico":
            storico(client, impostazioni)
        else:
            log.warning("Modalità '%s' non ancora disponibile: nessun dato generato.", impostazioni.modalita)
    except ErroreApi as errore:
        log.error("%s", errore)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
