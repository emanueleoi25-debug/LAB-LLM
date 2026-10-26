"""Collegamento al modello."""

from langchain_core.messages import AIMessage, BaseMessage

FIXED_REPLY = "Risposta fissa: il collegamento al modello arriverà nel prossimo incremento."


class FixedReplyModel:
    """Modello provvisorio che risponde sempre con lo stesso testo."""

    def invoke(self, messages: list[BaseMessage]) -> AIMessage:
        return AIMessage(content=FIXED_REPLY)
