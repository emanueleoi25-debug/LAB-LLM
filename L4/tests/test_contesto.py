from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from assistente.contesto import flat, recent_conversation


def test_flat_replaces_newlines():
    assert flat("a\r\nb\nc") == "a  b c"


def test_recent_conversation_keeps_last_four_text_messages():
    call = {"name": "calculate", "args": {}, "id": "c1", "type": "tool_call"}
    history = [
        SystemMessage("s"), HumanMessage("u1"), AIMessage("a1"), HumanMessage("u2"),
        AIMessage("", tool_calls=[call]), ToolMessage("r", tool_call_id="c1", name="calculate"),
        AIMessage("a2"), HumanMessage("u3"), AIMessage("riga1\nriga2"),
    ]
    assert recent_conversation(history, len(history)) == (
        "Conversazione recente:\nUtente: u2\nAssistente: a2\nUtente: u3\nAssistente: riga1 riga2"
    )


def test_recent_conversation_stops_at_end():
    history = [HumanMessage("u1"), AIMessage("a1"), HumanMessage("u2")]
    assert recent_conversation(history, 2) == "Conversazione recente:\nUtente: u1\nAssistente: a1"


def test_recent_conversation_empty():
    assert recent_conversation([SystemMessage("s"), HumanMessage("d")], 1) == "Conversazione recente: (nessuna)"
