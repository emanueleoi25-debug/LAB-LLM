"""Revisore: controlla che la risposta dell'agente sia coerente con la domanda dell'utente.

Lo stesso modello dell'agente, con un prompt di sistema proprio e una risposta JSON vincolata da
`REVIEW_SCHEMA`. La risposta viene letta e validata qui: se non è utilizzabile, o se il server non
risponde, la risposta dell'agente viene approvata (il revisore non deve bloccare l'assistente).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Collection
from dataclasses import dataclass
from typing import TYPE_CHECKING

import openai
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from assistente.contesto import flat, recent_conversation

if TYPE_CHECKING:
    from assistente.graph import ChatModel

logger = logging.getLogger(__name__)

CONTEXT_MESSAGES = 4
COHERENT_UNUSABLE_REASON = "risposta del revisore non utilizzabile"

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {"coerente": {"type": "boolean"}, "motivo": {"type": "string"}},
    "required": ["coerente", "motivo"],
    "additionalProperties": False,
}

REVIEWER_PROMPT = (
    "Sei il revisore dell'assistente del laboratorio. Non rispondi alla domanda dell'utente: "
    "controlli solo se la risposta proposta è coerente con la domanda. Coerente significa che "
    "risponde a tutte le parti richieste e non devia dal tema. Non verificare se i dati sono "
    "corretti: l'assistente li ottiene da strumenti che tu non vedi. Una domanda che continua la "
    "conversazione recente (per esempio «e a Tokyo?») va letta insieme a quella conversazione. "
    "Rispondi solo con un oggetto JSON con due campi: coerente, true se la risposta è coerente e "
    "false altrimenti, e motivo, una frase breve in italiano; se la risposta non è coerente, il "
    "motivo dice che cosa manca o dove devia."
)


@dataclass(frozen=True)
class Review:
    coerente: bool
    motivo: str
    errore: str | None
    grezza: str


def _read(content: object) -> tuple[bool, str] | str:
    """Esito e motivo se la risposta è utilizzabile, altrimenti la descrizione dell'errore."""
    if not isinstance(content, str):
        return "contenuto non testuale"
    try:
        data = json.loads(content.strip())
    except ValueError:
        return "JSON non valido"
    if not isinstance(data, dict):
        return "non è un oggetto JSON"
    coerente = data.get("coerente")
    if type(coerente) is not bool:
        return "coerente mancante o non booleano"
    motivo = data.get("motivo", "")
    if not isinstance(motivo, str):
        return "motivo non testuale"
    motivo = motivo.strip()
    if not coerente and not motivo:
        return "motivo mancante con risposta non coerente"
    return coerente, motivo


def _user_message(messages: list[BaseMessage], discarded: Collection[str]) -> str:
    question_index = max(
        (i for i, m in enumerate(messages) if isinstance(m, HumanMessage) and m.id not in discarded),
        default=len(messages),
    )
    question = messages[question_index].text if question_index < len(messages) else ""
    answer = next((m.text for m in reversed(messages) if isinstance(m, AIMessage)), "")
    recent = recent_conversation(messages, question_index, CONTEXT_MESSAGES)
    return f"{recent}\n\nDomanda dell'utente:\n{flat(question)}\n\nRisposta proposta:\n{flat(answer)}"


class Reviewer:
    def __init__(self, model: ChatModel) -> None:
        self._model = model

    def review(self, messages: list[BaseMessage], discarded: Collection[str] = ()) -> Review:
        sent = [SystemMessage(REVIEWER_PROMPT), HumanMessage(_user_message(messages, discarded))]
        for message, role in zip(sent, ("sistema", "utente")):
            logger.debug("→ revisore [%s] %s", role, flat(message.text))
        try:
            reply = self._model.invoke(sent)
        except openai.OpenAIError as exc:
            return Review(True, COHERENT_UNUSABLE_REASON, f"errore del server: {exc}", "")
        content = reply.content
        result = _read(content)
        raw = content if isinstance(content, str) else str(content)
        if isinstance(result, str):
            return Review(True, COHERENT_UNUSABLE_REASON, result, raw)
        return Review(result[0], result[1], None, raw)
