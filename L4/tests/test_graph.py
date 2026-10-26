from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from assistente.graph import build_graph
from tests.fakes import ScriptedModel


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
