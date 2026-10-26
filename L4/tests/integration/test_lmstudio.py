"""Prove reali con LM Studio: si attivano solo con RUN_LMSTUDIO_TESTS=1."""

import os

import pytest
from langchain_core.messages import ToolMessage

from assistente.cli import ask, create_graph, new_history
from assistente.config import load_settings
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
    history, reply = ask(graph, new_history(), "Che ore sono adesso a Tokyo?")
    assert any(isinstance(m, ToolMessage) and m.name == "get_current_time" for m in history)
    assert reply.strip()
