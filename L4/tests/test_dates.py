from datetime import UTC, datetime

import httpx
import pytest
from langchain_core.utils.function_calling import convert_to_openai_tool

from assistente.dates import (
    ADD_BUSINESS_DAYS_DESCRIPTION,
    ADD_DAYS_DESCRIPTION,
    DATE_INFO_DESCRIPTION,
    DAYS_BETWEEN_DESCRIPTION,
    TIMEOUT,
    make_date_tools,
)

NOW = datetime(2026, 11, 5, 10, 0, tzinfo=UTC)
BASE_URL = "http://giorni.test"


def make_tools(response=None, clock=lambda: NOW, error=None):
    """Strumenti con trasporto finto: restituisce (strumenti per nome, richieste registrate)."""
    requests = []

    def handler(request):
        requests.append(request)
        if error is not None:
            raise error
        return response

    tools = make_date_tools(
        BASE_URL, "Europe/Rome", clock=clock, transport=httpx.MockTransport(handler)
    )
    return {t.name: t for t in tools}, requests


def json_response(body, status=200):
    return httpx.Response(status, json=body)


def test_tool_order():
    tools, _ = make_tools(json_response({}))
    assert list(tools) == ["days_between", "add_days", "add_business_days", "date_info"]


def test_timeout_is_five_seconds():
    assert TIMEOUT == 5.0


def test_today_in_default_timezone():
    # 23:30 UTC del 31 dicembre sono già le 00:30 del 1 gennaio a Roma
    tools, requests = make_tools(
        json_response({}), clock=lambda: datetime(2026, 12, 31, 23, 30, tzinfo=UTC)
    )
    tools["date_info"].invoke({})
    assert dict(requests[0].url.params) == {"oggi": "2027-01-01"}


@pytest.mark.parametrize(
    ("name", "args", "path", "params"),
    [
        ("days_between", {"end": "12-25"}, "/giorni-tra", {"oggi": "2026-11-05", "fine": "12-25"}),
        (
            "days_between",
            {"end": "12-25", "start": "2026-11-01"},
            "/giorni-tra",
            {"oggi": "2026-11-05", "fine": "12-25", "inizio": "2026-11-01"},
        ),
        (
            "add_days",
            {"days": 30, "start": "2026-11-27"},
            "/aggiungi-giorni",
            {"oggi": "2026-11-05", "giorni": "30", "data": "2026-11-27"},
        ),
        ("add_days", {"days": 30}, "/aggiungi-giorni", {"oggi": "2026-11-05", "giorni": "30"}),
        (
            "add_business_days",
            {"days": -3},
            "/aggiungi-lavorativi",
            {"oggi": "2026-11-05", "giorni": "-3"},
        ),
        (
            "date_info",
            {"date": "2027-06-02"},
            "/info-data",
            {"oggi": "2026-11-05", "data": "2027-06-02"},
        ),
    ],
)
def test_requests(name, args, path, params):
    tools, requests = make_tools(json_response({}))
    tools[name].invoke(args)
    assert len(requests) == 1
    assert requests[0].method == "GET"
    assert requests[0].url.path == path
    assert dict(requests[0].url.params) == params


def between(days, working, start="2026-11-05", end="2026-12-25", day_start="giovedì", day_end="venerdì"):
    return {
        "inizio": start,
        "fine": end,
        "giorno_inizio": day_start,
        "giorno_fine": day_end,
        "giorni": days,
        "lavorativi": working,
    }


def added(days, result, day_result, start="2026-11-05", day_start="giovedì", skipped=None):
    body = {
        "data": start,
        "giorno_data": day_start,
        "giorni": days,
        "risultato": result,
        "giorno_risultato": day_result,
    }
    if skipped is not None:
        body["festivita_saltate"] = skipped
    return body


def info(date, day, holiday, weekend, working):
    return {
        "data": date,
        "giorno": day,
        "festivita": holiday,
        "fine_settimana": weekend,
        "lavorativo": working,
    }


@pytest.mark.parametrize(
    ("name", "args", "body", "text"),
    [
        (
            "days_between",
            {"end": "12-25"},
            between(50, 34),
            "Dal 2026-11-05 (giovedì) al 2026-12-25 (venerdì): 50 giorni di calendario, "
            "34 giorni lavorativi (esclusa la partenza, inclusa la data di arrivo).",
        ),
        (
            "days_between",
            {"end": "2019-12-31", "start": "2019-01-01"},
            between(364, None, "2019-01-01", "2019-12-31", "martedì", "martedì"),
            "Dal 2019-01-01 (martedì) al 2019-12-31 (martedì): 364 giorni di calendario; "
            "giorni lavorativi non disponibili fuori dagli anni 2020-2040.",
        ),
        (
            "days_between",
            {"end": "2026-11-02"},
            between(-3, -2, "2026-11-05", "2026-11-02", "giovedì", "lunedì"),
            "Dal 2026-11-05 (giovedì) al 2026-11-02 (lunedì): -3 giorni di calendario, "
            "-2 giorni lavorativi (esclusa la partenza, inclusa la data di arrivo).",
        ),
        (
            "days_between",
            {"end": "2026-11-06"},
            between(1, 1, "2026-11-05", "2026-11-06", "giovedì", "venerdì"),
            "Dal 2026-11-05 (giovedì) al 2026-11-06 (venerdì): 1 giorno di calendario, "
            "1 giorno lavorativo (esclusa la partenza, inclusa la data di arrivo).",
        ),
        (
            "days_between",
            {"end": "2026-11-04"},
            between(-1, -1, "2026-11-05", "2026-11-04", "giovedì", "mercoledì"),
            "Dal 2026-11-05 (giovedì) al 2026-11-04 (mercoledì): -1 giorno di calendario, "
            "-1 giorno lavorativo (esclusa la partenza, inclusa la data di arrivo).",
        ),
        (
            "days_between",
            {"end": "2026-11-05"},
            between(0, 0, "2026-11-05", "2026-11-05", "giovedì", "giovedì"),
            "Dal 2026-11-05 (giovedì) al 2026-11-05 (giovedì): 0 giorni di calendario, "
            "0 giorni lavorativi (esclusa la partenza, inclusa la data di arrivo).",
        ),
        (
            "add_days",
            {"days": 30},
            added(30, "2026-12-05", "sabato"),
            "2026-11-05 (giovedì) + 30 giorni = 2026-12-05 (sabato)",
        ),
        (
            "add_days",
            {"days": -10},
            added(-10, "2026-10-26", "lunedì"),
            "2026-11-05 (giovedì) - 10 giorni = 2026-10-26 (lunedì)",
        ),
        (
            "add_days",
            {"days": 1},
            added(1, "2026-11-06", "venerdì"),
            "2026-11-05 (giovedì) + 1 giorno = 2026-11-06 (venerdì)",
        ),
        (
            "add_days",
            {"days": -1},
            added(-1, "2026-11-04", "mercoledì"),
            "2026-11-05 (giovedì) - 1 giorno = 2026-11-04 (mercoledì)",
        ),
        (
            "add_business_days",
            {"days": 10, "start": "2026-11-27"},
            added(
                10,
                "2026-12-14",
                "lunedì",
                "2026-11-27",
                "venerdì",
                [{"data": "2026-12-08", "nome": "Immacolata Concezione"}],
            ),
            "2026-11-27 (venerdì) + 10 giorni lavorativi = 2026-12-14 (lunedì); "
            "festività saltate: 2026-12-08 Immacolata Concezione.",
        ),
        (
            "add_business_days",
            {"days": 3},
            added(3, "2026-11-10", "martedì", skipped=[]),
            "2026-11-05 (giovedì) + 3 giorni lavorativi = 2026-11-10 (martedì); "
            "nessuna festività saltata.",
        ),
        (
            "add_business_days",
            {"days": 1},
            added(1, "2026-11-06", "venerdì", skipped=[]),
            "2026-11-05 (giovedì) + 1 giorno lavorativo = 2026-11-06 (venerdì); "
            "nessuna festività saltata.",
        ),
        (
            "add_business_days",
            {"days": -3},
            added(-3, "2026-11-02", "lunedì", skipped=[]),
            "2026-11-05 (giovedì) - 3 giorni lavorativi = 2026-11-02 (lunedì); "
            "nessuna festività saltata.",
        ),
        (
            "add_business_days",
            {"days": 20, "start": "2026-12-01"},
            added(
                20,
                "2027-01-04",
                "lunedì",
                "2026-12-01",
                "martedì",
                [
                    {"data": "2026-12-08", "nome": "Immacolata Concezione"},
                    {"data": "2026-12-25", "nome": "Natale"},
                ],
            ),
            "2026-12-01 (martedì) + 20 giorni lavorativi = 2027-01-04 (lunedì); "
            "festività saltate: 2026-12-08 Immacolata Concezione, 2026-12-25 Natale.",
        ),
        (
            "date_info",
            {"date": "2027-06-02"},
            info("2027-06-02", "mercoledì", "Festa della Repubblica", False, False),
            "2027-06-02 (mercoledì): festività, Festa della Repubblica; non lavorativo.",
        ),
        (
            "date_info",
            {"date": "2026-10-04"},
            info("2026-10-04", "domenica", "San Francesco d'Assisi", True, False),
            "2026-10-04 (domenica): festività, San Francesco d'Assisi; fine settimana; "
            "non lavorativo.",
        ),
        (
            "date_info",
            {"date": "2026-11-07"},
            info("2026-11-07", "sabato", None, True, False),
            "2026-11-07 (sabato): fine settimana; non lavorativo.",
        ),
        (
            "date_info",
            {},
            info("2026-11-05", "giovedì", None, False, True),
            "2026-11-05 (giovedì): giorno lavorativo.",
        ),
        (
            "date_info",
            {"date": "2019-06-02"},
            info("2019-06-02", "domenica", None, True, None),
            "2019-06-02 (domenica): festività non disponibili fuori dagli anni 2020-2040.",
        ),
    ],
)
def test_success_texts(name, args, body, text):
    tools, _ = make_tools(json_response(body))
    assert tools[name].invoke(args) == text


@pytest.mark.parametrize(
    ("name", "args"),
    [
        ("days_between", {"end": "02-30"}),
        ("add_days", {"days": 5, "start": "02-30"}),
        ("add_business_days", {"days": 5, "start": "02-30"}),
        ("date_info", {"date": "02-30"}),
    ],
)
def test_400_becomes_error_text(name, args):
    detail = "data non valida '02-30'. Usa AAAA-MM-GG o MM-GG."
    tools, _ = make_tools(json_response({"detail": detail}, status=400))
    assert tools[name].invoke(args) == f"Errore: {detail}"


@pytest.mark.parametrize(
    ("response", "code"),
    [
        (httpx.Response(500, json={"detail": "boom"}), 500),
        (httpx.Response(404, text="non trovato"), 404),
        (httpx.Response(400, text="non è json"), 400),
        (httpx.Response(400, json={"altro": 1}), 400),
        (httpx.Response(200, text="ciao"), 200),
        (httpx.Response(200, json=["non", "un", "oggetto"]), 200),
        (httpx.Response(200, json={"giorno": "giovedì"}), 200),  # campi mancanti
    ],
)
def test_unexpected_response(response, code):
    tools, _ = make_tools(response)
    assert tools["date_info"].invoke({}) == (
        f"Errore: risposta non valida dal servizio giorni (HTTP {code})."
    )


@pytest.mark.parametrize(
    "error", [httpx.ConnectError("rifiutata"), httpx.ReadTimeout("lento")]
)
def test_unreachable(error):
    tools, _ = make_tools(error=error)
    for name, args in (
        ("days_between", {"end": "12-25"}),
        ("add_days", {"days": 1}),
        ("add_business_days", {"days": 1}),
        ("date_info", {}),
    ):
        assert tools[name].invoke(args) == (
            "Errore: servizio giorni non raggiungibile a http://giorni.test."
        )


@pytest.mark.parametrize(
    ("name", "args"),
    [
        ("days_between", {"end": "12-25"}),
        ("add_days", {"days": 1}),
        ("add_business_days", {"days": 1}),
        ("date_info", {}),
    ],
)
def test_http_error_becomes_invalid_response(name, args):
    tools, _ = make_tools(error=httpx.DecodingError("corpo illeggibile"))
    assert tools[name].invoke(args) == "Errore: risposta non valida dal servizio giorni."


DESCRIPTIONS = {
    "days_between": (
        DAYS_BETWEEN_DESCRIPTION,
        "Conta i giorni tra due date: giorni di calendario e giorni lavorativi in Italia "
        "(esclusi sabati, domeniche e festività nazionali). Parametri: end, la data di arrivo; "
        "start, la data di partenza (omettilo per partire da oggi). Date come AAAA-MM-GG; se "
        "l'utente non dice l'anno passa MM-GG (es. '12-25' per Natale) e si usa la prossima "
        "occorrenza. Se una data non è valida restituisce un errore che spiega il motivo: "
        "chiamalo comunque, non rispondere a mente.",
    ),
    "add_days": (
        ADD_DAYS_DESCRIPTION,
        "Calcola la data che si ottiene aggiungendo (o togliendo, con un numero negativo) "
        "giorni di calendario a una data. Parametri: days, il numero di giorni (es. 30, oppure "
        "-10 per '10 giorni fa'); start, la data di partenza come AAAA-MM-GG o MM-GG (omettilo "
        "per partire da oggi). Se i dati non sono validi restituisce un errore che spiega il "
        "motivo: chiamalo comunque, non rispondere a mente.",
    ),
    "add_business_days": (
        ADD_BUSINESS_DAYS_DESCRIPTION,
        "Calcola una scadenza in giorni lavorativi in Italia (esclusi sabati, domeniche e "
        "festività nazionali): restituisce il giorno lavorativo che cade dopo days giorni "
        "lavorativi, senza contare la data di partenza. Parametri: days, il numero di giorni "
        "lavorativi (negativo per andare indietro); start, la data di partenza come AAAA-MM-GG "
        "o MM-GG (omettilo per partire da oggi). Se i dati non sono validi restituisce un "
        "errore che spiega il motivo: chiamalo comunque, non rispondere a mente.",
    ),
    "date_info": (
        DATE_INFO_DESCRIPTION,
        "Dice che giorno della settimana è una data, se è una festività nazionale italiana "
        "(con il nome), se cade nel fine settimana e se è lavorativa. Parametro: date, come "
        "AAAA-MM-GG o MM-GG (omettilo per oggi). Se la data non è valida restituisce un errore "
        "che spiega il motivo: chiamalo comunque, non rispondere a mente.",
    ),
}


@pytest.mark.parametrize("name", list(DESCRIPTIONS))
def test_descriptions_are_exact(name):
    constant, literal = DESCRIPTIONS[name]
    tools, _ = make_tools(json_response({}))
    fn = convert_to_openai_tool(tools[name])["function"]
    assert constant == literal
    assert fn["description"] == literal


@pytest.mark.parametrize(
    ("name", "properties", "required", "integer"),
    [
        ("days_between", {"end", "start"}, ["end"], None),
        ("add_days", {"days", "start"}, ["days"], "days"),
        ("add_business_days", {"days", "start"}, ["days"], "days"),
        ("date_info", {"date"}, [], None),
    ],
)
def test_schemas(name, properties, required, integer):
    tools, _ = make_tools(json_response({}))
    fn = convert_to_openai_tool(tools[name])["function"]
    assert fn["name"] == name
    assert set(fn["parameters"]["properties"]) == properties
    assert fn["parameters"].get("required", []) == required
    if integer:
        assert fn["parameters"]["properties"][integer]["type"] == "integer"
