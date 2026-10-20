"""Punto di ingresso del generatore.

Modalità disponibili:
    storico   simula gli ultimi N giorni, una rilevazione al minuto per macchina, e li invia un giorno alla volta;
    auto      se il database è vuoto genera lo storico, altrimenti colma il buco tra l'ultima rilevazione e adesso.
              È la modalità usata da Docker Compose: al primo avvio la dashboard ha subito dei dati.
"""

import logging
import sys
import time
from datetime import date, datetime, timedelta

from client_api import ClientApi, ErroreApi
from config import Impostazioni
from simulatore.calendario import FUSO
from simulatore.flusso import simula_storico
from simulatore.macchina import DatiMacchina

log = logging.getLogger("generatore")


def istante_di_fine(impostazioni: Impostazioni) -> datetime:
    fine = impostazioni.data_fine or datetime.now(FUSO)
    # Una data di fine senza fuso orario vale come ora di Roma, anche dentro il container (che è in UTC).
    fine = fine.replace(tzinfo=FUSO) if fine.tzinfo is None else fine.astimezone(FUSO)
    return fine.replace(second=0, microsecond=0)


def ripresa(ultime: list[dict]) -> datetime | None:
    """Fine dell'ultima rilevazione memorizzata (fra tutte le macchine); None se il database è vuoto."""
    fini = [
        datetime.fromisoformat(u["ultima"]["inizio"]) + timedelta(seconds=u["ultima"]["durata_s"])
        for u in ultime if u["ultima"]
    ]
    return max(fini) if fini else None


def genera(client: ClientApi, seme: int, da: date, fine: datetime, dopo: datetime | None = None) -> None:
    """Simula dal giorno `da` all'istante `fine` e invia un blocco per giorno; con `dopo` invia solo ciò che segue."""
    macchine = [DatiMacchina.da_api(m) for m in client.macchine()]
    avvio = time.perf_counter()
    totale = 0
    for giorno, blocco in simula_storico(macchine, seme, da, fine):
        if dopo:
            blocco = [r for r in blocco if datetime.fromisoformat(r["inizio"]) >= dopo]
            if not blocco:
                continue
        inviato = time.perf_counter()
        esito = client.invia(blocco)
        totale += esito["memorizzate"]
        log.info("%s: %d rilevazioni memorizzate, %d già presenti (%.2f s)",
                 giorno, esito["memorizzate"], esito["duplicate"], time.perf_counter() - inviato)
    log.info("Completato: %d rilevazioni in %.1f s", totale, time.perf_counter() - avvio)


def storico(client: ClientApi, impostazioni: Impostazioni) -> None:
    fine = istante_di_fine(impostazioni)
    inizio = fine.date() - timedelta(days=impostazioni.giorni - 1)
    log.info("Storico dal %s al %s (seme %d)", inizio, fine, impostazioni.seme)
    genera(client, impostazioni.seme, inizio, fine)


def auto(client: ClientApi, impostazioni: Impostazioni) -> None:
    da_dove = ripresa(client.ultime())
    if da_dove is None:
        log.info("Database vuoto: genero lo storico")
        storico(client, impostazioni)
        return
    fine = istante_di_fine(impostazioni)
    if da_dove >= fine:
        log.info("Dati già aggiornati fino a %s", da_dove)
        return
    log.info("Riprendo dall'ultima rilevazione (%s) fino a %s", da_dove, fine)
    giorno = da_dove.astimezone(FUSO).date()
    # La ripresa simula di nuovo il giorno dalle 6:00 con uno stato nuovo della linea (buffer e fermi non proseguono
    # quelli già salvati) e invia solo i minuti mancanti. Il seme dipende dal giorno, così giorni diversi non
    # ripetono lo stesso andamento; riavvii nello stesso giorno restano coerenti fra loro.
    genera(client, impostazioni.seme + giorno.toordinal(), giorno, fine, dopo=da_dove)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    impostazioni = Impostazioni()
    log.info("Avvio in modalità '%s', API %s", impostazioni.modalita, impostazioni.api_url)
    client = ClientApi(impostazioni.api_url)
    if not client.attendi():
        log.error("Back-end non raggiungibile su %s", impostazioni.api_url)
        return 1
    modalita = {"storico": storico, "auto": auto}
    try:
        if impostazioni.modalita in modalita:
            modalita[impostazioni.modalita](client, impostazioni)
        else:
            log.warning("Modalità '%s' non ancora disponibile: nessun dato generato.", impostazioni.modalita)
    except ErroreApi as errore:
        log.error("%s", errore)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
