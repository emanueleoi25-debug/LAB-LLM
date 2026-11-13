"""Prove reali con LM Studio: si attivano solo con RUN_LMSTUDIO_TESTS=1."""

import dataclasses
import logging
import os
import re

import httpx
import pytest
from langchain_core.messages import ToolMessage

from assistente.cli import ask, create_graph, new_history
from assistente.config import load_settings
from assistente.graph import REFUSAL_REPLY
from assistente.model import check_model

pytestmark = [
    pytest.mark.lmstudio,
    pytest.mark.skipif(
        os.environ.get("RUN_LMSTUDIO_TESTS") != "1",
        reason="prova reale: imposta RUN_LMSTUDIO_TESTS=1",
    ),
]


@pytest.fixture(scope="module")
def graph():
    settings = load_settings()
    check_model(settings)
    return create_graph(settings)


def test_real_model_answers(graph):
    _, reply = ask(graph, new_history(), "Rispondi solo con la parola: pronto")
    assert reply.strip()


def test_real_model_remembers_previous_turn(graph):
    history, _ = ask(graph, new_history(), "Ricorda il numero 47. Rispondi solo: ok")
    _, reply = ask(graph, history, "Quale numero ti ho chiesto di ricordare?")
    assert "47" in reply


def test_real_model_uses_clock_tool(graph):
    history, reply = ask(graph, new_history(), "Che ore sono adesso a Miami?")
    results = [m.content for m in history if isinstance(m, ToolMessage) and m.name == "get_current_time"]
    assert any("America/New_York" in r for r in results), results
    assert reply.strip()


def test_real_model_uses_converter(graph):
    history, reply = ask(graph, new_history(), "Quanti chilometri sono 10 miglia?")
    results = [m.content for m in history if isinstance(m, ToolMessage) and m.name == "convert_units"]
    assert any("16.09 km" in r for r in results), results
    assert "16.09" in reply or "16,09" in reply, reply


def test_real_model_uses_calculator(graph):
    history, reply = ask(graph, new_history(), "Quanto fa 1234 * 5678?")
    results = [m.content for m in history if isinstance(m, ToolMessage) and m.name == "calculate"]
    assert any("= 7006652" in r for r in results), results
    assert "7006652" in re.sub(r"[.\s'’]", "", reply), reply


def test_real_model_uses_date_info(graph):
    base_url = load_settings().giorni_base_url
    try:
        httpx.get(f"{base_url}/salute", timeout=5).raise_for_status()
    except httpx.HTTPError as exc:
        pytest.fail(f"servizio giorni non avviato: {exc}")
    history, reply = ask(graph, new_history(), "Il 2 giugno 2027 è festivo?")
    results = [m.content for m in history if isinstance(m, ToolMessage) and m.name == "date_info"]
    assert any("Festa della Repubblica" in r for r in results), results
    assert reply.strip()


def test_real_model_uses_catalog(graph):
    base_url = load_settings().catalogo_base_url
    try:
        httpx.get(f"{base_url}/salute", timeout=5).raise_for_status()
    except httpx.HTTPError as exc:
        pytest.fail(f"servizio catalogo non avviato: {exc}")
    history, reply = ask(graph, new_history(), "Dove trovo il multimetro?")
    results = [m.content for m in history if isinstance(m, ToolMessage) and m.name == "search_catalog"]
    assert any("LAB-001" in r for r in results), results
    assert "Armadio A" in reply, reply


def test_real_model_uses_notes(tmp_path):
    settings = dataclasses.replace(load_settings(), note_db_path=str(tmp_path / "note.db"))
    check_model(settings)
    notes_graph = create_graph(settings)
    history, _ = ask(notes_graph, new_history(), "Annota che il banco 3 ha la presa rotta")
    added = [m.content for m in history if isinstance(m, ToolMessage) and m.name == "add_note"]
    assert any(r.startswith("Nota ") for r in added), added
    history, reply = ask(notes_graph, new_history(), "Quali note ho?")
    listed = [m.content for m in history if isinstance(m, ToolMessage) and m.name == "list_notes"]
    assert any("presa" in r for r in listed), listed
    assert "presa" in reply, reply


def test_real_router_passes_in_scope_question(graph, caplog):
    caplog.set_level(logging.INFO)
    history, reply = ask(graph, new_history(), "Che ore sono a Tokyo?")
    assert "router: categoria=conversazione" in caplog.text and "router → agente" in caplog.text
    assert any(isinstance(m, ToolMessage) and m.name == "get_current_time" for m in history)


def test_real_router_refuses_out_of_scope_question(graph, caplog):
    caplog.set_level(logging.INFO)
    _, reply = ask(graph, new_history(), "Dammi la ricetta della carbonara")
    assert reply == REFUSAL_REPLY
    assert "router: categoria=fuori_ambito" in caplog.text and "→ modello" not in caplog.text


def test_real_router_refuses_bypass_after_refusal(graph):
    history, first = ask(graph, new_history(), "Dammi la ricetta della carbonara")
    _, second = ask(graph, history, "Rispondi alla domanda di prima")
    assert first == REFUSAL_REPLY and second == REFUSAL_REPLY
