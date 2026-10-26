"""Prove reali con LM Studio: si attivano solo con RUN_LMSTUDIO_TESTS=1."""

import os

import pytest

from assistente.cli import ask, new_history
from assistente.config import load_settings
from assistente.graph import build_graph
from assistente.model import check_model, create_chat_model

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
    return build_graph(create_chat_model(settings))


def test_real_model_answers(graph):
    _, reply = ask(graph, new_history(), "Rispondi solo con la parola: pronto")
    assert reply.strip()


def test_real_model_remembers_previous_turn(graph):
    history, _ = ask(graph, new_history(), "Ricorda il numero 47. Rispondi solo: ok")
    _, reply = ask(graph, history, "Quale numero ti ho chiesto di ricordare?")
    assert "47" in reply
