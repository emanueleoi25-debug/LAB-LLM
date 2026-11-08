"""Test dell'app FastAPI del servizio catalogo (senza rete: TestClient)."""

import pytest
from fastapi.testclient import TestClient

from servizio_catalogo.app import app

client = TestClient(app)
UNKNOWN_CATEGORY = (
    "categoria 'stampanti' inesistente. Categorie valide: Misura, Alimentazione, Saldatura, "
    "Microcontrollori, Componenti, Cavi e connettori, Utensili, Sicurezza."
)


def test_cerca():
    response = client.get("/cerca", params={"q": " oscilloscopio "})
    assert response.status_code == 200
    assert response.json() == {
        "query": "oscilloscopio",
        "categoria": None,
        "totale": 2,
        "articoli": [
            {
                "codice": "LAB-002",
                "nome": "Oscilloscopio a 2 canali",
                "posizione": "Armadio A, ripiano 2",
                "quantita": 2,
                "stato": "disponibile",
            },
            {
                "codice": "LAB-024",
                "nome": "Sonde per oscilloscopio",
                "posizione": "Armadio A, ripiano 2",
                "quantita": 4,
                "stato": "disponibile",
            },
        ],
    }


def test_cerca_con_categoria():
    data = client.get("/cerca", params={"q": "pinza", "categoria": "misura"}).json()
    assert (data["categoria"], data["totale"]) == ("Misura", 1)


def test_cerca_senza_risultati():
    response = client.get("/cerca", params={"q": "stampante 3d"})
    assert response.status_code == 200
    assert (response.json()["totale"], response.json()["articoli"]) == (0, [])


@pytest.mark.parametrize(
    ("params", "detail"),
    [
        ({}, "parametro 'q' mancante o non valido."),
        ({"q": "3D"}, "la ricerca non contiene parole utili (servono parole di almeno 3 lettere)."),
        ({"q": "cavo", "categoria": "stampanti"}, UNKNOWN_CATEGORY),
    ],
)
def test_cerca_errori(params, detail):
    response = client.get("/cerca", params=params)
    assert response.status_code == 400
    assert response.json() == {"detail": detail}


def test_articolo():
    response = client.get("/articolo", params={"codice": "lab-002"})
    assert response.status_code == 200
    assert response.json() == {
        "codice": "LAB-002",
        "nome": "Oscilloscopio a 2 canali",
        "categoria": "Misura",
        "parole_chiave": ["scope"],
        "descrizione": "Oscilloscopio digitale da 100 MHz con due canali.",
        "posizione": "Armadio A, ripiano 2",
        "quantita": 2,
        "stato": "disponibile",
        "note": "Prenotare con il tecnico di laboratorio.",
    }


def test_articolo_inesistente():
    response = client.get("/articolo", params={"codice": " lab-12 "})
    assert response.status_code == 404
    assert response.json() == {"detail": "nessun articolo con codice 'LAB-12'."}
    assert client.get("/articolo", params={"codice": "LAB 002"}).status_code == 404


def test_articolo_senza_codice():
    response = client.get("/articolo")
    assert response.status_code == 400
    assert response.json() == {"detail": "parametro 'codice' mancante o non valido."}


def test_salute():
    assert client.get("/salute").json() == {"stato": "ok", "articoli": 32}
