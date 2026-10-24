"""Messaggi in italiano per gli errori di validazione di Pydantic, comuni alle API e all'import da CSV."""

# Traduzione dei tipi di errore più frequenti; per gli altri resta il messaggio originale.
MESSAGGI = {
    "missing": "campo obbligatorio mancante",
    "int_parsing": "deve essere un numero intero",
    "int_from_float": "deve essere un numero intero",
    "float_parsing": "deve essere un numero",
    "finite_number": "deve essere un numero finito",
    "datetime_parsing": "data e ora non valide (formato atteso: 2026-10-19T08:00:00+02:00)",
    "datetime_from_date_parsing": "data e ora non valide (formato atteso: 2026-10-19T08:00:00+02:00)",
    "date_parsing": "data non valida (formato atteso: 2026-10-19)",
    "date_from_datetime_parsing": "data non valida (formato atteso: 2026-10-19)",
    "string_type": "deve essere un testo",
    "list_type": "deve essere un elenco",
    "greater_than_equal": "valore troppo piccolo",
    "less_than": "valore troppo grande",
    "less_than_equal": "valore troppo grande",
}


def messaggio(errore: dict) -> str:
    return MESSAGGI.get(errore["type"], errore["msg"])
