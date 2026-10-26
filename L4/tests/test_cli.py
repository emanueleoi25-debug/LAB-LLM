import io

import pytest
from langchain_core.messages import AIMessage

from assistente.cli import run_chat
from assistente.graph import build_graph
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
