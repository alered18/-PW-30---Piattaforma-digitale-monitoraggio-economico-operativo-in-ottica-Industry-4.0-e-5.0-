import main
from config import Impostazioni


def test_impostazioni_predefinite():
    impostazioni = Impostazioni(_env_file=None)
    assert impostazioni.modalita == "auto"
    assert impostazioni.giorni == 90
    assert impostazioni.intervallo_live_s == 5


def test_backend_spento_segnalato():
    # Nessun servizio in ascolto su questa porta: il generatore deve rinunciare e restituire False.
    assert main.attendi_backend("http://127.0.0.1:9/api", tentativi=1, attesa_s=0) is False
