"""Contesto recente della conversazione, condiviso da router e revisore."""

from collections.abc import Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage


def flat(text: str) -> str:
    """Testo su una riga: ogni `\\r` e `\\n` diventa uno spazio."""
    return text.replace("\r", " ").replace("\n", " ")


def recent_conversation(messages: Sequence[BaseMessage], end: int, limit: int = 4) -> str:
    """Ultimi `limit` messaggi di testo tra utente e assistente prima dell'indice `end`."""
    context = [
        m
        for m in messages[:end]
        if isinstance(m, HumanMessage) or (isinstance(m, AIMessage) and m.text)
    ][-limit:]
    if not context:
        return "Conversazione recente: (nessuna)"
    lines = [f"{'Utente' if isinstance(m, HumanMessage) else 'Assistente'}: {flat(m.text)}" for m in context]
    return "Conversazione recente:\n" + "\n".join(lines)
