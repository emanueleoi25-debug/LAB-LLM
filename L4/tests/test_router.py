import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from assistente.router import CONVERSATION, OUT_OF_SCOPE, UNUSABLE_REASON, Decision, Router
from tests.fakes import ScriptedModel

VALID = '{"categoria": "conversazione", "motivo": "ora di una città"}'


def classify(content, messages=None):
    model = ScriptedModel([AIMessage(content)])
    decision = Router(model, "AMBITO DI PROVA").classify(messages or [SystemMessage("s"), HumanMessage("domanda")])
    return decision, model


def test_valid_conversation():
    assert classify(VALID)[0] == Decision(CONVERSATION, "ora di una città", None, VALID)


def test_valid_out_of_scope_with_extra_field():
    raw = '{"categoria": "fuori_ambito", "motivo": "ricetta", "extra": 1}'
    assert classify(raw)[0] == Decision(OUT_OF_SCOPE, "ricetta", None, raw)


def test_surrounding_spaces_are_ignored():
    assert classify(f"  {VALID}\n")[0].errore is None


@pytest.mark.parametrize("content, errore", [
    ("non json", "JSON non valido"),
    ('Ecco: {"categoria": "conversazione", "motivo": "m"}', "JSON non valido"),
    ('["conversazione"]', "non è un oggetto JSON"),
    ('{"motivo": "m"}', "categoria mancante"),
    ('{"categoria": "altro", "motivo": "m"}', "categoria sconosciuta: 'altro'"),
    ('{"categoria": "Fuori_ambito", "motivo": "m"}', "categoria sconosciuta: 'Fuori_ambito'"),
    ('{"categoria": 3, "motivo": "m"}', "categoria sconosciuta: 3"),
    ('{"categoria": "fuori_ambito"}', "motivo mancante o vuoto"),
    ('{"categoria": "fuori_ambito", "motivo": "  "}', "motivo mancante o vuoto"),
    ('{"categoria": "fuori_ambito", "motivo": 3}', "motivo mancante o vuoto"),
])
def test_unusable_reply_falls_back_to_conversation(content, errore):
    assert classify(content)[0] == Decision(CONVERSATION, UNUSABLE_REASON, errore, content)


def test_non_text_content_is_unusable():
    content = [{"type": "text", "text": VALID}]
    decision = Router(ScriptedModel([AIMessage(content)]), "A").classify([HumanMessage("d")])
    assert (decision.categoria, decision.errore, decision.grezza) == (CONVERSATION, "contenuto non testuale", str(content))


def test_system_message_has_prompt_and_scope():
    system, human = classify(VALID)[1].calls[0]
    assert isinstance(system, SystemMessage) and isinstance(human, HumanMessage)
    assert system.content.startswith("Sei il router dell'assistente del laboratorio.")
    assert system.content.endswith("Ambito dell'assistente:\nAMBITO DI PROVA")


def test_context_keeps_last_four_text_messages():
    call = {"name": "calculate", "args": {}, "id": "c1", "type": "tool_call"}
    history = [
        SystemMessage("s"), HumanMessage("u1"), AIMessage("a1"), HumanMessage("u2"),
        AIMessage("", tool_calls=[call]), ToolMessage("r", tool_call_id="c1", name="calculate"),
        AIMessage("a2"), HumanMessage("u3"), AIMessage("riga1\nriga2"), HumanMessage("domanda\nfinale"),
    ]
    human = classify(VALID, history)[1].calls[0][1]
    assert human.content == (
        "Conversazione recente:\nUtente: u2\nAssistente: a2\nUtente: u3\nAssistente: riga1 riga2"
        "\n\nDomanda da classificare:\ndomanda finale"
    )


def test_context_without_previous_messages():
    human = classify(VALID)[1].calls[0][1]
    assert human.content == "Conversazione recente: (nessuna)\n\nDomanda da classificare:\ndomanda"
