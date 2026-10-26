"""Modelli finti per i test: nessuna chiamata a LM Studio."""

from langchain_core.messages import AIMessage, BaseMessage


class ScriptedModel:
    """Restituisce le risposte preparate in ordine e registra i messaggi ricevuti.

    Una risposta che è un'eccezione viene sollevata invece che restituita.
    """

    def __init__(self, responses: list[AIMessage | BaseException]) -> None:
        self._responses = list(responses)
        self.calls: list[list[BaseMessage]] = []

    def invoke(self, messages: list[BaseMessage]) -> AIMessage:
        self.calls.append(list(messages))
        if not self._responses:
            raise AssertionError("ScriptedModel: risposte preparate esaurite")
        response = self._responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response
