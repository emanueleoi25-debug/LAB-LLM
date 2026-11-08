"""Test degli strumenti del catalogo (assistente/catalog.py): servizio finto o app vera, niente rete."""

import httpx
import pytest
from fastapi.testclient import TestClient
from langchain_core.utils.function_calling import convert_to_openai_tool

from assistente import catalog
from assistente.catalog import CATALOG_FAILURE_HINT, TIMEOUT, make_catalog_tools
from servizio_catalogo.app import app

BASE_URL = "http://127.0.0.1:8001"


def make_tools(handler):
    """Strumenti per nome, collegati a un servizio finto (`handler` riceve la richiesta)."""
    client = httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler))
    return {t.name: t for t in make_catalog_tools(BASE_URL, client=client)}


def answering(response):
    """Strumenti il cui servizio finto risponde sempre `response`."""
    return make_tools(lambda request: response)


def json_response(body, status=200):
    return httpx.Response(status, json=body)


def line(code, name, position, quantity, state="disponibile"):
    return {"codice": code, "nome": name, "posizione": position, "quantita": quantity, "stato": state}


OSCILLOSCOPES = [
    line("LAB-002", "Oscilloscopio a 2 canali", "Armadio A, ripiano 2", 2),
    line("LAB-024", "Sonde per oscilloscopio", "Armadio A, ripiano 2", 4),
]
LAB_002 = {
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


def found(articles, total=None, query="oscilloscopio", category=None):
    total = len(articles) if total is None else total
    return {"query": query, "categoria": category, "totale": total, "articoli": articles}


# --- descrizioni, schemi, client ----------------------------------------------------------------


def test_tool_names_and_descriptions():
    tools = make_catalog_tools(BASE_URL, client=httpx.Client())
    assert [t.name for t in tools] == ["search_catalog", "get_catalog_item"]
    assert tools[0].description == (
        "Cerca attrezzatura e materiale nell'inventario del laboratorio e restituisce codice, "
        "nome, posizione, quantità e stato degli articoli trovati. Parametri: query, 1-3 parole "
        "chiave in italiano (es. 'multimetro', 'cavo usb'); category, facoltativo, una categoria "
        "dell'inventario. Usalo per sapere se un articolo c'è, dove si trova e quanti pezzi ci "
        "sono: non rispondere a mente."
    )
    assert tools[1].description == (
        "Restituisce la scheda completa di un articolo dell'inventario (descrizione, posizione, "
        "quantità, stato, note) dato il suo codice, es. 'LAB-012'. Se non conosci il codice usa "
        "prima search_catalog."
    )
    search, item = (convert_to_openai_tool(t)["function"]["parameters"] for t in tools)
    assert set(search["properties"]) == {"query", "category"}
    assert search["required"] == ["query"]
    assert set(item["properties"]) == {"code"}
    assert item["required"] == ["code"]


def test_default_client(monkeypatch):
    assert TIMEOUT == 5.0
    calls = []
    real_client = httpx.Client  # catalog.httpx è lo stesso modulo: va salvato prima del patch

    def spy(**kwargs):
        calls.append(kwargs)
        return real_client()

    monkeypatch.setattr(catalog.httpx, "Client", spy)
    make_catalog_tools(BASE_URL)
    assert calls == [{"base_url": BASE_URL, "timeout": 5.0}]


@pytest.mark.parametrize(
    ("name", "args", "path", "params"),
    [
        ("search_catalog", {"query": "multimetro"}, "/cerca", {"q": "multimetro"}),
        (
            "search_catalog",
            {"query": "pinza", "category": "Misura"},
            "/cerca",
            {"q": "pinza", "categoria": "Misura"},
        ),
        ("search_catalog", {"query": "pinza", "category": ""}, "/cerca", {"q": "pinza"}),
        ("search_catalog", {"query": "pinza", "category": "  "}, "/cerca", {"q": "pinza"}),
        ("get_catalog_item", {"code": "LAB-002"}, "/articolo", {"codice": "LAB-002"}),
    ],
)
def test_requests(name, args, path, params):
    seen = []

    def handler(request):
        seen.append(request)
        return json_response(found([]) if path == "/cerca" else LAB_002)

    make_tools(handler)[name].invoke(args)
    assert seen[0].url.path == path
    assert dict(seen[0].url.params) == params


# --- testi di successo --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("body", "text"),
    [
        (
            found(OSCILLOSCOPES),
            "Trovati 2 articoli per «oscilloscopio»:\n"
            "- LAB-002 Oscilloscopio a 2 canali: Armadio A, ripiano 2; 2 pezzi; disponibile\n"
            "- LAB-024 Sonde per oscilloscopio: Armadio A, ripiano 2; 4 pezzi; disponibile",
        ),
        (
            found([line("LAB-032", "Cassetta di pronto soccorso", "Ingresso", 1)], query="soccorso"),
            "Trovato 1 articolo per «soccorso»:\n"
            "- LAB-032 Cassetta di pronto soccorso: Ingresso; 1 pezzo; disponibile",
        ),
        (
            found(
                [line("LAB-003", "Pinza amperometrica", "Armadio A, ripiano 1", 1, "in manutenzione")],
                query="pinza",
                category="Misura",
            ),
            "Trovato 1 articolo per «pinza» nella categoria Misura:\n"
            "- LAB-003 Pinza amperometrica: Armadio A, ripiano 1; 1 pezzo; in manutenzione",
        ),
        (
            found([line("LAB-023", "Cavo HDMI", "Armadio B, ripiano 3", 0, "esaurito")], query="hdmi"),
            "Trovato 1 articolo per «hdmi»:\n"
            "- LAB-023 Cavo HDMI: Armadio B, ripiano 3; 0 pezzi; esaurito",
        ),
    ],
)
def test_success_texts(body, text):
    assert answering(json_response(body))["search_catalog"].invoke({"query": "x"}) == text


@pytest.mark.parametrize(
    ("total", "last"),
    [
        (15, "Altri 5 articoli non mostrati: restringi la ricerca."),
        (11, "Altro 1 articolo non mostrato: restringi la ricerca."),
    ],
)
def test_more_results_than_shown(total, last):
    articles = [line(f"LAB-{n:03d}", f"Cavo {n}", "Banco 1", 3) for n in range(1, 11)]
    text = answering(json_response(found(articles, total, query="cavo")))["search_catalog"].invoke(
        {"query": "cavo"}
    )
    lines = text.split("\n")
    assert lines[0] == f"Trovati {total} articoli per «cavo»:"
    assert len(lines) == 12
    assert lines[-1] == last


def test_no_results():
    tools = answering(json_response(found([], query="stampante 3d")))
    assert tools["search_catalog"].invoke({"query": "stampante 3d"}) == (
        "Nessun articolo trovato per «stampante 3d»: dillo all'utente e non inventare articoli."
    )
    tools = answering(json_response(found([], query="x", category="Misura")))
    assert tools["search_catalog"].invoke({"query": "x"}) == (
        "Nessun articolo trovato per «x» nella categoria Misura: dillo all'utente e non "
        "inventare articoli."
    )


def test_item_text():
    tools = answering(json_response(LAB_002))
    assert tools["get_catalog_item"].invoke({"code": "LAB-002"}) == (
        "LAB-002 Oscilloscopio a 2 canali (Misura)\n"
        "Posizione: Armadio A, ripiano 2\n"
        "Quantità: 2 pezzi\n"
        "Stato: disponibile\n"
        "Descrizione: Oscilloscopio digitale da 100 MHz con due canali.\n"
        "Note: Prenotare con il tecnico di laboratorio."
    )


def test_item_text_without_note_and_single_piece():
    tools = answering(json_response({**LAB_002, "note": "", "quantita": 1}))
    text = tools["get_catalog_item"].invoke({"code": "LAB-002"})
    assert "Note:" not in text
    assert "Quantità: 1 pezzo\n" in text
    assert text.endswith("Descrizione: Oscilloscopio digitale da 100 MHz con due canali.")


# --- errori -------------------------------------------------------------------------------------


def test_user_errors():
    detail = "la ricerca non contiene parole utili (servono parole di almeno 3 lettere)."
    tools = answering(json_response({"detail": detail}, 400))
    assert tools["search_catalog"].invoke({"query": "3D"}) == f"Errore: {detail}"
    tools = answering(json_response({"detail": "nessun articolo con codice 'LAB-12'."}, 404))
    assert tools["get_catalog_item"].invoke({"code": "LAB-12"}) == (
        "Errore: nessun articolo con codice 'LAB-12'. Usa search_catalog per trovare il codice."
    )


@pytest.mark.parametrize(
    ("name", "args", "response", "code"),
    [
        ("search_catalog", {"query": "x"}, json_response({"detail": "boom"}, 500), 500),
        ("get_catalog_item", {"code": "LAB-001"}, json_response({"detail": "boom"}, 500), 500),
        ("search_catalog", {"query": "x"}, httpx.Response(200, text="non json"), 200),
        ("get_catalog_item", {"code": "LAB-001"}, httpx.Response(200, text="non json"), 200),
        ("search_catalog", {"query": "x"}, json_response([1, 2]), 200),
        ("search_catalog", {"query": "x"}, json_response({"query": "x"}), 200),
        ("get_catalog_item", {"code": "LAB-001"}, json_response({"codice": "LAB-001"}), 200),
        ("search_catalog", {"query": "x"}, json_response({"errore": "?"}, 400), 400),
        ("search_catalog", {"query": "x"}, json_response({"detail": "Not Found"}, 404), 404),
        ("get_catalog_item", {"code": "LAB-001"}, json_response({"detail": "Not Found"}, 404), 404),
    ],
)
def test_invalid_responses(name, args, response, code):
    assert answering(response)[name].invoke(args) == (
        f"Errore: risposta non valida dal servizio catalogo (HTTP {code}). {CATALOG_FAILURE_HINT}"
    )


@pytest.mark.parametrize("error", [httpx.ConnectError, httpx.ReadTimeout])
def test_unreachable(error):
    def handler(request):
        raise error("giù", request=request)

    for name, args in (("search_catalog", {"query": "x"}), ("get_catalog_item", {"code": "x"})):
        assert make_tools(handler)[name].invoke(args) == (
            f"Errore: servizio catalogo non raggiungibile a {BASE_URL}. {CATALOG_FAILURE_HINT}"
        )


def test_http_error_without_status():
    def handler(request):
        raise httpx.DecodingError("corpo illeggibile", request=request)

    assert make_tools(handler)["search_catalog"].invoke({"query": "x"}) == (
        f"Errore: risposta non valida dal servizio catalogo. {CATALOG_FAILURE_HINT}"
    )


def test_failure_hint_text():
    assert CATALOG_FAILURE_HINT == (
        "Non è possibile consultare l'inventario: dillo all'utente e non rispondere a mente."
    )


# --- contratto con l'app vera -------------------------------------------------------------------


@pytest.fixture(scope="module")
def real():
    tools = make_catalog_tools("http://testserver", client=TestClient(app))
    return {t.name: t for t in tools}


def test_contract_search(real):
    text = real["search_catalog"].invoke({"query": "multimetro"})
    assert "- LAB-001 Multimetro digitale: Armadio A, ripiano 1; 6 pezzi; disponibile" in text


def test_contract_item(real):
    text = real["get_catalog_item"].invoke({"code": "lab-002"})
    assert text.endswith("Note: Prenotare con il tecnico di laboratorio.")


def test_contract_unknown_code(real):
    assert real["get_catalog_item"].invoke({"code": "LAB-99"}) == (
        "Errore: nessun articolo con codice 'LAB-99'. Usa search_catalog per trovare il codice."
    )


def test_contract_unknown_category(real):
    text = real["search_catalog"].invoke({"query": "cavo", "category": "stampanti"})
    assert text.startswith("Errore: categoria 'stampanti' inesistente.")
