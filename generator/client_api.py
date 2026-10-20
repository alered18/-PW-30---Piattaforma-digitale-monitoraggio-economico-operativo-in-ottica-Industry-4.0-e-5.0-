"""Comunicazione con il back-end: il generatore usa solo le API, non conosce il database."""

import time

import httpx


class ErroreApi(Exception):
    """Il back-end non risponde o ha rifiutato i dati."""


class ClientApi:
    def __init__(self, api_url: str, timeout_s: float = 60):
        self.api_url = api_url.rstrip("/")
        self.http = httpx.Client(timeout=timeout_s)

    def attendi(self, tentativi: int = 10, attesa_s: float = 2.0) -> bool:
        """Interroga /salute finché il back-end risponde; False se non risponde dopo tutti i tentativi."""
        for _ in range(tentativi):
            try:
                if self.http.get(f"{self.api_url}/salute", timeout=5).status_code == 200:
                    return True
            except httpx.HTTPError:
                pass
            time.sleep(attesa_s)
        return False

    def macchine(self) -> list[dict]:
        return self._richiesta("GET", "/macchine")

    def invia(self, rilevazioni: list[dict]) -> dict:
        """Invia un blocco di rilevazioni e restituisce l'esito; se il back-end lo rifiuta solleva ErroreApi."""
        return self._richiesta("POST", "/rilevazioni", json=rilevazioni)

    def _richiesta(self, metodo: str, percorso: str, **opzioni):
        try:
            risposta = self.http.request(metodo, f"{self.api_url}{percorso}", **opzioni)
        except httpx.HTTPError as errore:
            raise ErroreApi(f"back-end non raggiungibile su {self.api_url}: {errore}") from errore
        if risposta.status_code >= 400:
            raise ErroreApi(f"{metodo} {percorso} rifiutata ({risposta.status_code}): {risposta.text[:500]}")
        return risposta.json()
