import logging
from datetime import datetime, timezone

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from assistente.cli import ask, new_history
from assistente.graph import LIMIT_REPLY, TOOL_SKIPPED, build_graph
from assistente.tools import make_clock_tool
from tests.fakes import ScriptedModel

NOW = datetime(2026, 10, 26, 16, 5, tzinfo=timezone.utc)
TOKYO = "2026-10-27T01:05:00+09:00 (Asia/Tokyo)"
clock = make_clock_tool("Europe/Rome", clock=lambda: NOW)


def call(name, args, id):
    return {"name": name, "args": args, "id": id, "type": "tool_call"}


def start(text="x"):
    return {"messages": [HumanMessage(text)], "tool_steps": 0}


def tokyo_scenario():
    return ScriptedModel([
        AIMessage("", tool_calls=[call("get_current_time", {"timezone": "Asia/Tokyo"}, "c1")]),
        AIMessage("Sono le 01:05"),
    ])


def test_reply_without_tool_calls_ends_after_one_model_call():
    model = ScriptedModel([AIMessage(content="Ciao!")])
    result = build_graph(model).invoke({"messages": [HumanMessage("Ciao")], "tool_steps": 0})
    assert len(model.calls) == 1
    assert [m.type for m in result["messages"]] == ["human", "ai"]
    assert result["messages"][-1].content == "Ciao!"


def test_model_receives_all_messages():
    model = ScriptedModel([AIMessage(content="ok")])
    build_graph(model).invoke({"messages": [SystemMessage("s"), HumanMessage("d")], "tool_steps": 0})
    assert [m.type for m in model.calls[0]] == ["system", "human"]


def test_graph_has_model_node():
    assert "modello" in build_graph(ScriptedModel([])).get_graph().nodes


def test_graph_has_tool_and_limit_nodes():
    nodes = build_graph(ScriptedModel([]), [clock]).get_graph().nodes
    assert {"modello", "strumenti", "limite"} <= set(nodes)


def test_tool_call_runs_tool_and_returns_result_to_model():
    model = tokyo_scenario()
    result = build_graph(model, [clock]).invoke(start("ora a Tokyo?"))
    sent = model.calls[1][-1]
    assert isinstance(sent, ToolMessage) and sent.tool_call_id == "c1" and sent.content == TOKYO
    assert sent.name == "get_current_time"
    assert result["messages"][-1].content == "Sono le 01:05" and result["tool_steps"] == 1


def test_parallel_tool_calls_count_as_one_step():
    model = ScriptedModel([
        AIMessage("", tool_calls=[
            call("get_current_time", {"timezone": "Asia/Tokyo"}, "c1"),
            call("get_current_time", {}, "c2"),
        ]),
        AIMessage("fatto"),
    ])
    result = build_graph(model, [clock]).invoke(start())
    tools = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert [m.tool_call_id for m in tools] == ["c1", "c2"]
    assert result["tool_steps"] == 1


def always_tool(n):
    return ScriptedModel([AIMessage("", tool_calls=[call("get_current_time", {}, f"c{i}")]) for i in range(n)])


def test_limit_stops_the_loop():
    model = always_tool(3)
    result = build_graph(model, [clock], max_tool_steps=2).invoke(start())
    tools = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(model.calls) == 3
    assert [m.content for m in tools].count(TOOL_SKIPPED) == 1 and len(tools) == 3
    assert result["messages"][-1].content == LIMIT_REPLY.format(max_tool_steps=2)
    asked = {c["id"] for m in result["messages"] if isinstance(m, AIMessage) for c in m.tool_calls}
    assert asked == {m.tool_call_id for m in tools}


def test_limit_is_logged_as_warning(caplog):
    caplog.set_level(logging.INFO, logger="assistente.graph")
    build_graph(always_tool(3), [clock], max_tool_steps=2).invoke(start())
    warnings = [r for r in caplog.records if r.name == "assistente.graph" and r.levelno == logging.WARNING]
    assert len(warnings) == 1


def single_call_result(name, args, tools):
    model = ScriptedModel([AIMessage("", tool_calls=[call(name, args, "c1")]), AIMessage("ok")])
    result = build_graph(model, tools).invoke(start())
    return next(m for m in result["messages"] if isinstance(m, ToolMessage)).content


def test_unknown_tool_returns_error():
    assert single_call_result("meteo", {}, [clock]) == "Errore: strumento sconosciuto 'meteo'."


def test_tool_exception_returns_error():
    @tool
    def boom() -> str:
        """Strumento che fallisce sempre."""
        raise RuntimeError("rotto")

    content = single_call_result("boom", {}, [boom])
    assert content.startswith("Errore durante l'esecuzione di boom") and "rotto" in content


def test_malformed_tool_args_return_error():
    content = single_call_result("get_current_time", {"timezone": ["Asia/Tokyo"]}, [clock])
    assert content.startswith("Errore durante l'esecuzione di get_current_time")


def test_tool_calls_are_logged(caplog):
    caplog.set_level(logging.INFO, logger="assistente.graph")
    build_graph(tokyo_scenario(), [clock]).invoke(start())
    assert "strumento richiesto: get_current_time {'timezone': 'Asia/Tokyo'}" in caplog.text
    assert f"risultato strumento: {TOKYO}" in caplog.text


def test_history_after_tool_turn_is_valid_for_next_turn():
    model = ScriptedModel([
        AIMessage("", tool_calls=[call("get_current_time", {"timezone": "Asia/Tokyo"}, "c1")]),
        AIMessage("Sono le 01:05"),
        AIMessage("Prego"),
    ])
    graph = build_graph(model, [clock])
    history, _ = ask(graph, new_history(), "ora a Tokyo?")
    ask(graph, history, "grazie")
    assert [m.type for m in model.calls[2]] == ["system", "human", "ai", "tool", "ai", "human"]
