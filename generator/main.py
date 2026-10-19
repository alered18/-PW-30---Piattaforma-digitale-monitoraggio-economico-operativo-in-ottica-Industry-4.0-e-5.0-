"""Punto di ingresso del generatore.

Per ora controlla soltanto che il back-end risponda e termina; le modalità storico, live, auto e csv
saranno aggiunte qui.
"""

import logging
import sys
import time

import httpx

from config import Impostazioni

log = logging.getLogger("generatore")


def attendi_backend(api_url: str, tentativi: int = 10, attesa_s: float = 2.0) -> bool:
    """Interroga /salute finché il back-end risponde; False se non risponde dopo tutti i tentativi."""
    for _ in range(tentativi):
        try:
            if httpx.get(f"{api_url}/salute", timeout=5).status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(attesa_s)
    return False


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    impostazioni = Impostazioni()
    log.info("Avvio in modalità '%s', API %s", impostazioni.modalita, impostazioni.api_url)
    if not attendi_backend(impostazioni.api_url):
        log.error("Back-end non raggiungibile su %s", impostazioni.api_url)
        return 1
    log.info("Back-end raggiungibile. Simulazione non ancora implementata.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
