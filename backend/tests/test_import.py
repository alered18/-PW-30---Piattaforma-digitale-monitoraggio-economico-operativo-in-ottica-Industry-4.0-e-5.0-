"""Import di rilevazioni da CSV con il file di esempio del repository."""

from conftest import RADICE

ESEMPIO = RADICE / "database" / "esempi" / "rilevazioni_esempio.csv"


def importa(client, contenuto: bytes):
    return client.post("/api/rilevazioni/import", files={"file": ("rilevazioni.csv", contenuto, "text/csv")})


def test_import_del_file_di_esempio(client):
    esito = importa(client, ESEMPIO.read_bytes()).json()
    assert (esito["righe"], esito["memorizzate"], esito["duplicate"]) == (103, 100, 0)
    assert esito["giorni_toccati"] == ["2026-01-12"]
    # Le 3 righe non valide in fondo al file, ciascuna con il suo numero di riga e il motivo.
    assert [(s["riga"], s["motivi"]) for s in esito["scartate"]] == [
        (102, ["macchina 'M9' inesistente"]),
        (103, ["gli scarti non possono superare i pezzi prodotti"]),
        (104, ["kwh: deve essere un numero (per i decimali si usa il punto)"]),
    ]
    # Le righe importate entrano nei KPI del giorno e sono marcate come provenienti da CSV.
    kpi = client.get("/api/kpi", params={"da": "2026-01-12", "a": "2026-01-12", "ambito": "M1"}).json()
    assert kpi["totale"]["kpi"]["n_tot"] > 0
    assert client.get("/api/rilevazioni", params={"da": "2026-01-12", "dimensione": 1}).json()["elementi"][0]["fonte"] == "csv"

    # Importare di nuovo lo stesso file non duplica i dati.
    di_nuovo = importa(client, ESEMPIO.read_bytes()).json()
    assert (di_nuovo["memorizzate"], di_nuovo["duplicate"], len(di_nuovo["scartate"])) == (0, 100, 3)


def test_intestazione_errata_rifiuta_il_file(client):
    risposta = importa(client, b"macchina;inizio;pezzi\nM1;2026-01-12T06:00:00+01:00;30\n")
    assert risposta.status_code == 422
    assert risposta.json()["detail"] == "I valori devono essere separati da virgole, non da punti e virgola"

    intestazione = ESEMPIO.read_text(encoding="utf-8").splitlines()[0].replace("kwh", "energia")
    risposta = importa(client, intestazione.encode())
    assert risposta.status_code == 422
    assert risposta.json()["detail"].startswith("Intestazione non valida (mancano kwh; colonne non previste: energia)")
