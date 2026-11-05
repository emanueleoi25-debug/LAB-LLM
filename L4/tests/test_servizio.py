"""Test dell'app FastAPI del servizio giorni (senza rete: TestClient)."""

import pytest
from fastapi.testclient import TestClient

from servizio_giorni.app import app

client = TestClient(app)
OGGI = "2026-11-05"


def test_giorni_tra():
    response = client.get("/giorni-tra", params={"oggi": OGGI, "fine": "12-25"})
    assert response.status_code == 200
    assert response.json() == {
        "inizio": "2026-11-05",
        "fine": "2026-12-25",
        "giorno_inizio": "giovedì",
        "giorno_fine": "venerdì",
        "giorni": 50,
        "lavorativi": 34,
    }


def test_giorni_tra_fuori_file():
    response = client.get(
        "/giorni-tra", params={"oggi": OGGI, "inizio": "2019-01-01", "fine": "2019-12-31"}
    )
    assert response.status_code == 200
    assert response.json()["lavorativi"] is None
    assert response.json()["giorni"] == 364


def test_aggiungi_giorni():
    response = client.get("/aggiungi-giorni", params={"oggi": OGGI, "giorni": 30})
    assert response.status_code == 200
    assert response.json() == {
        "data": "2026-11-05",
        "giorno_data": "giovedì",
        "giorni": 30,
        "risultato": "2026-12-05",
        "giorno_risultato": "sabato",
    }


def test_aggiungi_lavorativi():
    response = client.get(
        "/aggiungi-lavorativi", params={"oggi": OGGI, "data": "2026-11-27", "giorni": 10}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["risultato"] == "2026-12-14"
    assert body["giorno_risultato"] == "lunedì"
    assert body["festivita_saltate"] == [{"data": "2026-12-08", "nome": "Immacolata Concezione"}]


def test_info_data():
    response = client.get("/info-data", params={"oggi": OGGI, "data": "2027-06-02"})
    assert response.status_code == 200
    assert response.json() == {
        "data": "2027-06-02",
        "giorno": "mercoledì",
        "festivita": "Festa della Repubblica",
        "fine_settimana": False,
        "lavorativo": False,
    }


def test_info_data_senza_data_vale_oggi():
    response = client.get("/info-data", params={"oggi": OGGI})
    assert response.json()["data"] == OGGI


def test_salute():
    response = client.get("/salute")
    assert response.status_code == 200
    assert response.json() == {"stato": "ok", "anni_festivita": [2020, 2040]}


@pytest.mark.parametrize(
    ("path", "params", "detail"),
    [
        (
            "/info-data",
            {"oggi": OGGI, "data": "02-30"},
            "data non valida '02-30'. Usa AAAA-MM-GG o MM-GG.",
        ),
        (
            "/aggiungi-lavorativi",
            {"oggi": OGGI, "giorni": 0},
            "il numero di giorni lavorativi deve essere diverso da 0 e compreso tra -366 e 366.",
        ),
        (
            "/aggiungi-giorni",
            {"oggi": OGGI, "giorni": 40000},
            "il numero di giorni deve essere compreso tra -36500 e 36500.",
        ),
        ("/info-data", {"oggi": "11-05"}, "data non valida '11-05'. Usa AAAA-MM-GG."),
    ],
)
def test_errori_400(path, params, detail):
    response = client.get(path, params=params)
    assert response.status_code == 400
    assert response.json() == {"detail": detail}


def test_ordine_dei_controlli():
    # oggi invalido prevale sulla data di partenza invalida, questa su `fine` e su `giorni`.
    response = client.get("/giorni-tra", params={"oggi": "x", "inizio": "y", "fine": "z"})
    assert response.json()["detail"] == "data non valida 'x'. Usa AAAA-MM-GG."
    response = client.get("/giorni-tra", params={"oggi": OGGI, "inizio": "y", "fine": "z"})
    assert response.json()["detail"] == "data non valida 'y'. Usa AAAA-MM-GG o MM-GG."
    response = client.get(
        "/aggiungi-giorni", params={"oggi": OGGI, "data": "2101-01-01", "giorni": 99999}
    )
    assert response.json()["detail"] == "anno 2101 fuori intervallo: ammessi 1900-2100."


def test_mese_giorno_di_fine_parte_dalla_partenza():
    # 12-19 da oggi (2026-11-05) sarebbe il 2026-12-19; dalla partenza 2026-12-20 è il 2027.
    response = client.get(
        "/giorni-tra", params={"oggi": OGGI, "inizio": "2026-12-20", "fine": "12-19"}
    )
    assert response.json()["fine"] == "2027-12-19"


def test_risultato_fuori_anni_del_file():
    response = client.get(
        "/aggiungi-lavorativi", params={"oggi": OGGI, "data": "2040-12-30", "giorni": 5}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == (
        "giorni lavorativi e festività disponibili solo per gli anni 2020-2040."
    )


def test_validazione_diventa_400():
    response = client.get("/aggiungi-giorni", params={"oggi": OGGI, "giorni": "trenta"})
    assert response.status_code == 400
    assert response.json() == {"detail": "parametro 'giorni' mancante o non valido."}
    response = client.get("/giorni-tra", params={"oggi": OGGI})
    assert response.status_code == 400
    assert response.json() == {"detail": "parametro 'fine' mancante o non valido."}
    response = client.get("/info-data")
    assert response.status_code == 400
    assert response.json() == {"detail": "parametro 'oggi' mancante o non valido."}
