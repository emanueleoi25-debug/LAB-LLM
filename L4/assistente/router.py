"""Router: decide se la domanda rientra nell'ambito dell'assistente.

Lo stesso modello dell'agente, con un prompt di sistema proprio e una risposta JSON vincolata da
`DECISION_SCHEMA`. La risposta viene letta e validata qui: se non è utilizzabile la domanda viene
trattata come in ambito (il router fa da filtro e non deve bloccare l'assistente).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

if TYPE_CHECKING:
    from assistente.graph import ChatModel

logger = logging.getLogger(__name__)

CONVERSATION = "conversazione"
OUT_OF_SCOPE = "fuori_ambito"
CONTEXT_MESSAGES = 4
UNUSABLE_REASON = "risposta del router non utilizzabile"

DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "categoria": {"type": "string", "enum": [CONVERSATION, OUT_OF_SCOPE]},
        "motivo": {"type": "string"},
    },
    "required": ["categoria", "motivo"],
    "additionalProperties": False,
}

ROUTER_PROMPT = (
    "Sei il router dell'assistente del laboratorio. Non rispondi alla domanda dell'utente: decidi "
    "solo se rientra nell'ambito dell'assistente descritto qui sotto. Non valutare quali strumenti "
    "servono: lo decide l'assistente. Una domanda che continua la conversazione recente (per esempio "
    "«e a Tokyo?») va giudicata insieme a quella conversazione. Rispondi solo con un oggetto JSON con "
    'due campi: categoria, che vale "conversazione" se la domanda rientra nell\'ambito e '
    '"fuori_ambito" altrimenti, e motivo, una frase breve in italiano.'
)


@dataclass(frozen=True)
class Decision:
    categoria: str
    motivo: str
    errore: str | None
    grezza: str


def _flat(text: str) -> str:
    return text.replace("\r", " ").replace("\n", " ")


def _user_message(messages: list[BaseMessage]) -> str:
    question_index = max(
        (i for i, m in enumerate(messages) if isinstance(m, HumanMessage)), default=len(messages)
    )
    question = messages[question_index].text if question_index < len(messages) else ""
    context = [
        m
        for m in messages[:question_index]
        if isinstance(m, HumanMessage) or (isinstance(m, AIMessage) and m.text)
    ][-CONTEXT_MESSAGES:]
    if context:
        lines = [
            f"{'Utente' if isinstance(m, HumanMessage) else 'Assistente'}: {_flat(m.text)}" for m in context
        ]
        recent = "Conversazione recente:\n" + "\n".join(lines)
    else:
        recent = "Conversazione recente: (nessuna)"
    return f"{recent}\n\nDomanda da classificare:\n{_flat(question)}"


def _read(content: object) -> tuple[str, str] | str:
    """Categoria e motivo se la risposta è utilizzabile, altrimenti la descrizione dell'errore."""
    if not isinstance(content, str):
        return "contenuto non testuale"
    try:
        data = json.loads(content.strip())
    except ValueError:
        return "JSON non valido"
    if not isinstance(data, dict):
        return "non è un oggetto JSON"
    if "categoria" not in data:
        return "categoria mancante"
    categoria = data["categoria"]
    if categoria not in (CONVERSATION, OUT_OF_SCOPE):
        return f"categoria sconosciuta: {categoria!r}"
    motivo = data.get("motivo")
    if not isinstance(motivo, str) or not motivo.strip():
        return "motivo mancante o vuoto"
    return categoria, motivo.strip()


class Router:
    def __init__(self, model: ChatModel, scope: str) -> None:
        self._model = model
        self._system = f"{ROUTER_PROMPT}\n\nAmbito dell'assistente:\n{scope}"

    def classify(self, messages: list[BaseMessage]) -> Decision:
        sent = [SystemMessage(self._system), HumanMessage(_user_message(messages))]
        for message, role in zip(sent, ("sistema", "utente")):
            logger.debug("→ router [%s] %s", role, message.text.replace("\n", "\\n"))
        reply = self._model.invoke(sent)
        content = reply.content
        result = _read(content)
        raw = content if isinstance(content, str) else str(content)
        if isinstance(result, str):
            return Decision(CONVERSATION, UNUSABLE_REASON, result, raw)
        return Decision(result[0], result[1], None, raw)
