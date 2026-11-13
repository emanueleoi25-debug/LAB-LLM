import httpx
import openai
import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from openai.types.chat import ChatCompletion

from assistente.revisore import COHERENT_UNUSABLE_REASON, REVIEWER_PROMPT, Review, Reviewer
from tests.fakes import ScriptedModel

HISTORY = [SystemMessage("s"), HumanMessage("domanda"), AIMessage("risposta")]


def review(content, messages=None, discarded=()):
    model = ScriptedModel([content if isinstance(content, BaseException) else AIMessage(content)])
    result = Reviewer(model).review(messages or HISTORY, discarded)
    return result, model


def sent_text(model):
    return model.calls[0][1].content


def test_valid_coherent_without_reason():
    raw = '{"coerente": true, "motivo": ""}'
    assert review(raw)[0] == Review(True, "", None, raw)
    missing = review('{"coerente": true}')[0]
    assert missing.motivo == "" and missing.errore is None and missing.coerente is True


def test_valid_coherent_with_reason_and_extra_field():
    raw = '{"coerente": true, "motivo": "ok", "x": 1}'
    assert review(raw)[0] == Review(True, "ok", None, raw)


def test_valid_not_coherent():
    raw = '{"coerente": false, "motivo": " manca il calcolo. "}'
    assert review(raw)[0] == Review(False, "manca il calcolo.", None, raw)


@pytest.mark.parametrize("content, errore", [
    ("non json", "JSON non valido"),
    ('Ecco: {"coerente": true}', "JSON non valido"),
    ("[true]", "non è un oggetto JSON"),
    ('{"motivo": "m"}', "coerente mancante o non booleano"),
    ('{"coerente": "true", "motivo": "m"}', "coerente mancante o non booleano"),
    ('{"coerente": 1, "motivo": "m"}', "coerente mancante o non booleano"),
    ('{"coerente": true, "motivo": 3}', "motivo non testuale"),
    ('{"coerente": false}', "motivo mancante con risposta non coerente"),
    ('{"coerente": false, "motivo": "  "}', "motivo mancante con risposta non coerente"),
])
def test_unusable_reply_is_approved(content, errore):
    assert review(content)[0] == Review(True, COHERENT_UNUSABLE_REASON, errore, content)


def test_non_text_content_is_unusable():
    content = [{"type": "text", "text": '{"coerente": false, "motivo": "m"}'}]
    result = Reviewer(ScriptedModel([AIMessage(content)])).review(HISTORY)
    assert (result.coerente, result.errore, result.grezza) == (True, "contenuto non testuale", str(content))


@pytest.mark.parametrize("exc", [
    openai.APIConnectionError(request=httpx.Request("POST", "http://x")),
    openai.LengthFinishReasonError(completion=ChatCompletion.model_construct(usage=None)),
])
def test_server_errors_are_approved(exc):
    result = review(exc)[0]
    assert result.coerente is True and result.motivo == COHERENT_UNUSABLE_REASON
    assert result.errore.startswith("errore del server: ") and result.grezza == ""


def test_other_exceptions_propagate():
    with pytest.raises(ValueError):
        review(ValueError("x"))


def test_messages_sent_to_reviewer():
    history = [SystemMessage("s"), HumanMessage("u1"), AIMessage("a1"), HumanMessage("domanda"), AIMessage("risposta")]
    model = review('{"coerente": true}', history)[1]
    system, human = model.calls[0]
    assert isinstance(system, SystemMessage) and system.content == REVIEWER_PROMPT
    assert isinstance(human, HumanMessage)
    assert human.content == (
        "Conversazione recente:\nUtente: u1\nAssistente: a1\n\n"
        "Domanda dell'utente:\ndomanda\n\nRisposta proposta:\nrisposta"
    )
    assert REVIEWER_PROMPT.startswith("Sei il revisore dell'assistente del laboratorio.")


def test_question_skips_discarded_messages():
    history = [
        HumanMessage("domanda"), AIMessage("bozza", id="b1"),
        HumanMessage("Indicazione del revisore: …", id="i1"), AIMessage("nuova"),
    ]
    text = sent_text(review('{"coerente": true}', history, {"b1", "i1"})[1])
    assert text == "Conversazione recente: (nessuna)\n\nDomanda dell'utente:\ndomanda\n\nRisposta proposta:\nnuova"


def test_question_and_answer_are_flattened():
    text = sent_text(review('{"coerente": true}', [HumanMessage("a\nb"), AIMessage("c\nd")])[1])
    assert "Domanda dell'utente:\na b\n" in text and text.endswith("Risposta proposta:\nc d")
