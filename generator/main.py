"""Punto di ingresso del generatore.

Modalità disponibili:
    storico   simula gli ultimi N giorni, una rilevazione al minuto per macchina, e li invia un giorno alla volta;
    live      in tempo reale: ogni N secondi una rilevazione per macchina, solo in orario di turno, finché non viene
              fermato;
    auto      se il database è vuoto genera lo storico, altrimenti colma il buco tra l'ultima rilevazione e adesso;
              poi passa al live. È la modalità usata da Docker Compose: al primo avvio la dashboard ha subito dei dati
              e poi continua ad aggiornarsi. Con una data di fine fissata non passa al live (dati riproducibili);
    csv       scrive un file CSV di esempio nel formato di import, con 100 righe valide e 3 non valide.

Gli scenari riconoscibili (degrado, mancanze di materiale, guasto grave) si applicano solo allo storico, perché sono
posizionati rispetto alla sua data di fine; il recupero dei dati mancanti e il live simulano la linea senza scenari.
"""

import logging
import random
import sys
import time
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path

from client_api import ClientApi, ErroreApi
from config import Impostazioni
from simulatore import esempio_csv
from simulatore.calendario import APERTURA, CHIUSURA, FUSO, lavorativo
from simulatore.flusso import Linea, simula_storico
from simulatore.macchina import DatiMacchina
from simulatore.scenari import Scenari, nomi_da_configurazione

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


def genera(
    client: ClientApi, seme: int, da: date, fine: datetime, dopo: datetime | None = None,
    scenari: Scenari | None = None,
) -> None:
    """Simula dal giorno `da` all'istante `fine` e invia un blocco per giorno; con `dopo` invia solo ciò che segue."""
    macchine = [DatiMacchina.da_api(m) for m in client.macchine()]
    avvio = time.perf_counter()
    totale = 0
    for giorno, blocco in simula_storico(macchine, seme, da, fine, scenari=scenari):
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
    scenari = Scenari(fine.date(), nomi_da_configurazione(impostazioni.scenari))
    log.info("Storico dal %s al %s (seme %d)", inizio, fine, impostazioni.seme)
    for nome in sorted(scenari.attivi):
        if scenari.primo_giorno(nome) < inizio:
            log.warning("Scenario %s fuori dallo storico (%s): servono più giorni", nome, scenari.descrizione(nome))
        else:
            log.info("Scenario %s: %s", nome, scenari.descrizione(nome))
    genera(client, impostazioni.seme, inizio, fine, scenari=scenari)


def in_turno(inizio: datetime, passo_s: int) -> bool:
    """Vero se l'intervallo [inizio, inizio + passo) cade tutto nell'orario di lavoro."""
    locale = inizio.astimezone(FUSO)
    chiusura = datetime.combine(locale.date(), CHIUSURA, tzinfo=FUSO)
    return lavorativo(locale.date()) and locale.time() >= APERTURA and locale + timedelta(seconds=passo_s) <= chiusura


def live(
    client: ClientApi,
    impostazioni: Impostazioni,
    da: datetime | None = None,
    fino_a: datetime | None = None,
    adesso: Callable[[], datetime] = lambda: datetime.now(FUSO),
    dormi: Callable[[float], None] = time.sleep,
) -> None:
    """Invia una rilevazione per macchina ogni `intervallo_live_s` secondi, ciascuna dopo la fine del suo intervallo.

    Con `da` (la fine dell'ultima rilevazione memorizzata) si prosegue da lì senza lasciare buchi: i passi già
    trascorsi si inviano subito, uno dopo l'altro, finché si raggiunge l'ora attuale. Senza `da` si parte dall'ora
    attuale, allineata all'orologio (con 5 s: :00, :05, :10…) così i passi coincidono con l'inizio dei turni.
    Fuori orario di turno non si invia nulla. `fino_a`, `adesso` e `dormi` servono ai test per simulare il tempo.
    """
    passo = impostazioni.intervallo_live_s
    ora = adesso()
    allineato = ora.replace(microsecond=0) - timedelta(seconds=int(ora.timestamp()) % passo)
    istante = da or allineato
    macchine = [DatiMacchina.da_api(m) for m in client.macchine()]
    linea = Linea(macchine, random.Random(impostazioni.seme + istante.toordinal()))
    log.info("Live dalle %s: una rilevazione per macchina ogni %d s", istante.astimezone(FUSO).time(), passo)

    inviate, ultimo_log, era_in_turno, tempi = 0, time.monotonic(), False, []
    while fino_a is None or istante + timedelta(seconds=passo) <= fino_a:
        attesa = (istante + timedelta(seconds=passo) - adesso()).total_seconds()
        if attesa > 0:
            dormi(attesa)
        turno = in_turno(istante, passo)
        if era_in_turno and not turno:
            linea.fine_giornata()
            log.info("Fine del turno: il live riprende all'apertura")
        era_in_turno = turno
        if turno:
            try:
                blocco = linea.passo(istante, passo)
                avvio = time.perf_counter()
                client.invia(blocco)
                tempi.append(time.perf_counter() - avvio)
                inviate += len(macchine)
            except ErroreApi as errore:
                # Un back-end momentaneamente fermo non interrompe il live: l'intervallo perso resta "non coperto".
                log.warning("Intervallo delle %s non inviato: %s", istante.astimezone(FUSO).time(), errore)
        if time.monotonic() - ultimo_log >= 60:
            if inviate:
                # Tempo di andata e ritorno di un invio: rete, validazione, memorizzazione e ricalcolo del giorno.
                log.info("Live: %d rilevazioni inviate nell'ultimo minuto, %.0f ms in media per invio",
                         inviate, 1000 * sum(tempi) / len(tempi))
            inviate, ultimo_log, tempi = 0, time.monotonic(), []
        istante += timedelta(seconds=passo)


def auto(client: ClientApi, impostazioni: Impostazioni) -> None:
    da_dove = ripresa(client.ultime())
    fine = istante_di_fine(impostazioni)
    if da_dove is None:
        log.info("Database vuoto: genero lo storico")
        storico(client, impostazioni)
    elif da_dove < fine:
        log.info("Riprendo dall'ultima rilevazione (%s) fino a %s", da_dove, fine)
        giorno = da_dove.astimezone(FUSO).date()
        # La ripresa simula di nuovo il giorno dalle 6:00 con uno stato nuovo della linea (buffer e fermi non
        # proseguono quelli già salvati) e invia solo i minuti mancanti. Il seme dipende dal giorno, così giorni
        # diversi non ripetono lo stesso andamento; riavvii nello stesso giorno restano coerenti fra loro.
        genera(client, impostazioni.seme + giorno.toordinal(), giorno, fine, dopo=da_dove)
    else:
        log.info("Dati già aggiornati fino a %s", da_dove)
    if impostazioni.data_fine:
        return
    # Il live riparte dalla fine dell'ultima rilevazione: i minuti trascorsi durante il recupero si inviano subito.
    live(client, impostazioni, da=ripresa(client.ultime()))


def scrivi_csv(client: ClientApi, impostazioni: Impostazioni) -> None:
    macchine = [DatiMacchina.da_api(m) for m in client.macchine()]
    righe = esempio_csv.righe_esempio(macchine, impostazioni.seme)
    percorso = Path(impostazioni.file_csv)
    esempio_csv.scrivi(percorso, righe)
    log.info("Scritte %d righe in %s", len(righe), percorso.resolve())


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    impostazioni = Impostazioni()
    log.info("Avvio in modalità '%s', API %s", impostazioni.modalita, impostazioni.api_url)
    client = ClientApi(impostazioni.api_url)
    if not client.attendi():
        log.error("Back-end non raggiungibile su %s", impostazioni.api_url)
        return 1
    modalita = {"storico": storico, "live": live, "auto": auto, "csv": scrivi_csv}
    try:
        modalita[impostazioni.modalita](client, impostazioni)
    except ErroreApi as errore:
        log.error("%s", errore)
        return 1
    except KeyboardInterrupt:
        log.info("Generatore fermato")
    return 0


if __name__ == "__main__":
    sys.exit(main())
