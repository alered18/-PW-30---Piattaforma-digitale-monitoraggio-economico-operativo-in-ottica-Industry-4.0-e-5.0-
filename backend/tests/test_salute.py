from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_salute_risponde_ok():
    risposta = client.get("/api/salute")
    assert risposta.status_code == 200
    assert risposta.json() == {"stato": "ok"}


def test_documentazione_openapi_disponibile():
    assert client.get("/api/docs").status_code == 200
