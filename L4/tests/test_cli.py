import io
import logging

import httpx
import openai
import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool

import assistente.cli as cli
import servizio_note.server
from assistente import notes
from assistente.cli import SYSTEM_PROMPT, configure_logging, create_graph, main, make_tools, run_chat
from assistente.config import Settings
from assistente.mcp_client import MCPStartupError
from assistente.graph import build_graph
from assistente.router import Router
from tests.fakes import ScriptedModel


def inputs(*lines):
    """input_fn che fornisce le righe in ordine e poi simula Ctrl+D."""
    remaining = list(lines)

    def input_fn(prompt: str) -> str:
        if not remaining:
            raise EOFError
        return remaining.pop(0)

    return input_fn


@pytest.mark.parametrize("word", ["esci", "exit", "  Esci ", "EXIT"])
def test_exit_words_end_loop(word):
    model = ScriptedModel([])
    run_chat(build_graph(model), input_fn=inputs(word), output=io.StringIO())
    assert model.calls == []


def test_bom_before_exit_word_ends_loop():
    # La pipe di PowerShell manda la prima riga con un BOM: «esci» deve chiudere comunque.
    model = ScriptedModel([])
    run_chat(build_graph(model), input_fn=inputs("\ufeffesci"), output=io.StringIO())
    assert model.calls == []


def test_bom_is_removed_from_question():
    model = ScriptedModel([AIMessage("Ciao!")])
    history = run_chat(build_graph(model), input_fn=inputs("\ufeffCiao", "esci"), output=io.StringIO())
    assert [m.content for m in history if m.type == "human"][-1] == "Ciao"


@pytest.mark.parametrize("exc", [EOFError, KeyboardInterrupt])
def test_eof_and_ctrl_c_end_loop(exc):
    def input_fn(prompt):
        raise exc

    out = io.StringIO()
    run_chat(build_graph(ScriptedModel([])), input_fn=input_fn, output=out)
    assert "Arrivederci." in out.getvalue()


def test_blank_lines_are_ignored():
    model = ScriptedModel([])
    run_chat(build_graph(model), input_fn=inputs("", "   ", "esci"), output=io.StringIO())
    assert model.calls == []


def test_reply_is_printed():
    out = io.StringIO()
    run_chat(build_graph(ScriptedModel([AIMessage("Ciao!")])), input_fn=inputs("Ciao", "esci"), output=out)
    assert "Assistente> Ciao!" in out.getvalue()


def test_history_is_kept_between_turns():
    model = ScriptedModel([AIMessage("uno"), AIMessage("due")])
    history = run_chat(build_graph(model), input_fn=inputs("a", "b", "esci"), output=io.StringIO())
    assert [m.type for m in model.calls[1]] == ["system", "human", "ai", "human"]
    assert len(history) == 5


def test_empty_reply_prints_placeholder():
    out = io.StringIO()
    run_chat(build_graph(ScriptedModel([AIMessage("")])), input_fn=inputs("x", "esci"), output=out)
    assert "Assistente> (nessuna risposta dal modello)" in out.getvalue()


def test_ctrl_c_while_waiting_exits_cleanly():
    out = io.StringIO()
    run_chat(build_graph(ScriptedModel([KeyboardInterrupt()])), input_fn=inputs("x", "y"), output=out)
    assert "Arrivederci." in out.getvalue()


def test_model_error_discards_question_and_continues():
    err_conn = openai.APIConnectionError(request=httpx.Request("POST", "http://x"))
    model = ScriptedModel([err_conn, AIMessage("ok")])
    out, errs = io.StringIO(), io.StringIO()
    run_chat(build_graph(model), input_fn=inputs("prima", "seconda", "esci"), output=out, errors=errs)
    assert "Errore" in errs.getvalue()
    assert [m.type for m in model.calls[1]] == ["system", "human"]
    assert "Assistente> ok" in out.getvalue()


def test_main_fails_with_missing_config(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    for name in ("LMSTUDIO_BASE_URL", "LMSTUDIO_MODEL"):
        monkeypatch.delenv(name, raising=False)
    assert main() == 2
    assert "LMSTUDIO_BASE_URL" in capsys.readouterr().err


@pytest.mark.parametrize("name", ["httpx", "httpx2", "httpcore", "openai"])
def test_http_client_loggers_are_quiet(name):
    configure_logging("INFO")
    assert logging.getLogger(name).level == logging.WARNING


def test_unexpected_model_error_discards_question_and_continues():
    model = ScriptedModel([ValueError("tool_calls.0.args non validi"), AIMessage("ok")])
    out, errs = io.StringIO(), io.StringIO()
    run_chat(build_graph(model), input_fn=inputs("prima", "seconda", "esci"), output=out, errors=errs)
    assert "Errore" in errs.getvalue()
    assert [m.type for m in model.calls[1]] == ["system", "human"]
    assert "Assistente> ok" in out.getvalue()


def test_system_prompt_mentions_city_parameter():
    assert "parametro city" in SYSTEM_PROMPT


def fake_note_tools(db_path, timezone):
    return [
        StructuredTool.from_function(func=lambda: "", name=name, description=name)
        for name in ("add_note", "list_notes", "delete_note")
    ]


def test_tools_include_all_local_tools(monkeypatch):
    monkeypatch.setattr(cli, "make_note_tools", fake_note_tools)
    settings = Settings(base_url="http://localhost:1234/v1", model="m")
    names = [t.name for t in make_tools(settings)]
    assert len(set(names)) == len(names)
    assert names == [
        "get_current_time",
        "convert_units",
        "calculate",
        "days_between",
        "add_days",
        "add_business_days",
        "date_info",
        "search_catalog",
        "get_catalog_item",
        "add_note",
        "list_notes",
        "delete_note",
    ]


def test_system_prompt_mentions_converter():
    assert "convert_units" in SYSTEM_PROMPT


def test_system_prompt_mentions_calculator():
    assert (
        " Per qualsiasi calcolo aritmetico, anche semplice, usa sempre lo strumento calculate "
        "e non fare il calcolo a mente."
    ) in SYSTEM_PROMPT


def test_system_prompt_asks_to_call_tools_anyway():
    assert (
        " Usa gli strumenti anche quando la risposta ti sembra ovvia, il calcolo è facile o "
        "l'operazione sembra impossibile (per esempio una divisione per zero o una conversione "
        "tra unità di categorie diverse): chiama comunque lo strumento e riporta il suo esito. "
        "Ogni domanda che chiede quanto vale una quantità in un'altra unità è una conversione."
    ) in SYSTEM_PROMPT


def test_system_prompt_mentions_date_tools():
    assert (
        " Per contare giorni tra date, calcolare scadenze in giorni di calendario o lavorativi "
        "e sapere se una data è festiva o lavorativa usa gli strumenti days_between, add_days, "
        "add_business_days e date_info; se l'utente non dice l'anno passa la data come MM-GG."
    ) in SYSTEM_PROMPT


def test_system_prompt_contains_service_failure_rule():
    assert (
        " Se uno strumento risponde che il servizio giorni non è raggiungibile o che la sua "
        "risposta non è valida, di' all'utente che il calcolo non è disponibile e non dare "
        "risultati calcolati a mente o con altri strumenti."
    ) in SYSTEM_PROMPT


def test_system_prompt_contains_catalog_rule():
    assert (
        " Per sapere se un articolo del laboratorio c'è, dove si trova, quanti pezzi ci sono o in "
        "che stato è usa search_catalog e, per la scheda completa, get_catalog_item; non "
        "inventare articoli, posizioni o quantità. Se il servizio catalogo non è raggiungibile o "
        "la sua risposta non è valida, di' all'utente che l'inventario non è consultabile."
    ) in SYSTEM_PROMPT


def test_system_prompt_ends_with_notes_rule():
    assert SYSTEM_PROMPT.endswith(
        " Per salvare, elencare o eliminare note usa add_note, list_notes e delete_note; per "
        "eliminare una nota serve il suo id: se non lo conosci chiama prima list_notes. Non dire "
        "che una nota è stata salvata o eliminata se lo strumento non lo conferma."
    )


def test_main_exits_when_notes_server_fails(monkeypatch, capsys):
    settings = Settings(base_url="http://localhost:1234/v1", model="m")
    monkeypatch.setattr(cli, "load_settings", lambda: settings)
    monkeypatch.setattr(cli, "check_model", lambda s: None)

    def broken(db_path, timezone):
        raise MCPStartupError("boom")

    monkeypatch.setattr(cli, "make_note_tools", broken)
    assert main() == 1
    assert "Server MCP delle note non avviabile: boom" in capsys.readouterr().err


def test_failure_hints_match():
    assert notes.NOTE_FAILURE_HINT == servizio_note.server.NOTE_FAILURE_HINT


def test_create_graph_starts_with_router(monkeypatch):
    monkeypatch.setattr(cli, "make_note_tools", fake_note_tools)
    graph = create_graph(Settings(base_url="http://localhost:1234/v1", model="m", ambito="A"))
    assert {"router", "rifiuto", "agente"} <= set(graph.get_graph().nodes)


def test_router_error_discards_question_and_continues():
    ok = AIMessage('{"categoria": "conversazione", "motivo": "m"}')
    router = Router(ScriptedModel([RuntimeError("risposta troncata"), ok]), "A")
    out, errs = io.StringIO(), io.StringIO()
    run_chat(build_graph(ScriptedModel([AIMessage("ok")]), router=router),
             input_fn=inputs("prima", "seconda", "esci"), output=out, errors=errs)
    assert "risposta troncata" in errs.getvalue() and "Domanda scartata" in errs.getvalue()
    assert "Assistente> ok" in out.getvalue()
