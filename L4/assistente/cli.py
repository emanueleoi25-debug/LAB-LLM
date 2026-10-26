"""Interfaccia da terminale: ciclo di domande, cronologia di sessione, log."""

import logging
import sys
from collections.abc import Callable
from typing import TextIO

import openai
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from assistente.config import ConfigError, Settings, load_settings
from assistente.graph import build_graph
from assistente.model import ModelCheckError, check_model, create_chat_model
from assistente.tools import make_clock_tool

SYSTEM_PROMPT = (
    "Sei l'assistente del laboratorio. Rispondi in italiano, in modo breve e chiaro. "
    "Per conoscere la data o l'ora attuali usa sempre lo strumento get_current_time "
    "e non inventarle."
)
EXIT_WORDS = {"esci", "exit"}
EMPTY_REPLY = "(nessuna risposta dal modello)"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def new_history() -> list[BaseMessage]:
    return [SystemMessage(SYSTEM_PROMPT)]


def ask(graph, history: list[BaseMessage], question: str) -> tuple[list[BaseMessage], str]:
    """Invia una domanda al grafo; restituisce la nuova cronologia e il testo della risposta."""
    result = graph.invoke({"messages": history + [HumanMessage(question)], "tool_steps": 0})
    messages = result["messages"]
    reply = next((m for m in reversed(messages) if isinstance(m, AIMessage)), None)
    text = reply.content if reply is not None and isinstance(reply.content, str) else ""
    return messages, text


def run_chat(
    graph,
    history: list[BaseMessage] | None = None,
    input_fn: Callable[[str], str] = input,
    output: TextIO = sys.stdout,
    errors: TextIO = sys.stderr,
) -> list[BaseMessage]:
    """Ciclo da terminale; restituisce la cronologia finale della sessione."""
    if history is None:
        history = new_history()
    try:
        while True:
            question = input_fn("Tu> ").strip()
            if not question:
                continue
            if question.lower() in EXIT_WORDS:
                break
            try:
                history, text = ask(graph, history, question)
            except openai.APIError as exc:
                print(
                    f"Errore: il modello non ha risposto ({exc}). Domanda scartata, riprova.",
                    file=errors,
                )
                continue
            print(f"Assistente> {text.strip() or EMPTY_REPLY}", file=output)
    except (EOFError, KeyboardInterrupt):
        print(file=output)
    print("Arrivederci.", file=output)
    return history


def configure_logging(level: str) -> None:
    logging.basicConfig(stream=sys.stderr, level=level, format=LOG_FORMAT)
    for name in ("httpx", "httpx2", "httpcore", "openai"):
        logging.getLogger(name).setLevel(logging.WARNING)


def create_graph(settings: Settings):
    """Grafo dell'applicazione: modello di LM Studio con lo strumento orologio."""
    tools = [make_clock_tool(settings.default_timezone)]
    return build_graph(create_chat_model(settings, tools), tools, settings.max_tool_steps)


def main() -> int:
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(f"Configurazione non valida: {exc}", file=sys.stderr)
        return 2
    configure_logging(settings.log_level)
    try:
        check_model(settings)
    except ModelCheckError as exc:
        print(exc, file=sys.stderr)
        return 1
    run_chat(create_graph(settings))
    return 0
