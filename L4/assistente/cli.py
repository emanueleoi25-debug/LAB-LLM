"""Interfaccia da terminale: ciclo di domande, cronologia di sessione, log."""

import logging
import sys
from collections.abc import Callable
from typing import TextIO

import openai
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from assistente.catalog import make_catalog_tools
from assistente.config import ConfigError, Settings, load_settings
from assistente.dates import make_date_tools
from assistente.graph import build_graph
from assistente.mcp_client import MCPStartupError
from assistente.model import ModelCheckError, check_model, create_chat_model
from assistente.notes import make_note_tools
from assistente.tools import make_calculator_tool, make_clock_tool, make_converter_tool

SYSTEM_PROMPT = (
    "Sei l'assistente del laboratorio. Rispondi in italiano, in modo breve e chiaro. "
    "Per conoscere la data o l'ora attuali usa sempre lo strumento get_current_time "
    "e non inventarle. Se l'utente chiede l'ora di una città, passa il nome della città "
    "nel parametro city. Per convertire unità di misura usa sempre lo strumento "
    "convert_units e non fare il calcolo a mente. Per qualsiasi calcolo aritmetico, anche "
    "semplice, usa sempre lo strumento calculate e non fare il calcolo a mente. Usa gli "
    "strumenti anche quando la risposta ti sembra ovvia, il calcolo è facile o l'operazione "
    "sembra impossibile (per esempio una divisione per zero o una conversione tra unità di "
    "categorie diverse): chiama comunque lo strumento e riporta il suo esito. Ogni domanda che "
    "chiede quanto vale una quantità in un'altra unità è una conversione. "
    "Per contare giorni tra date, calcolare scadenze in giorni di calendario o lavorativi e "
    "sapere se una data è festiva o lavorativa usa gli strumenti days_between, add_days, "
    "add_business_days e date_info; se l'utente non dice l'anno passa la data come MM-GG. "
    "Se uno strumento risponde che il servizio giorni non è raggiungibile o che la sua "
    "risposta non è valida, di' all'utente che il calcolo non è disponibile e non dare "
    "risultati calcolati a mente o con altri strumenti. "
    "Per sapere se un articolo del laboratorio c'è, dove si trova, quanti pezzi ci sono o in che "
    "stato è usa search_catalog e, per la scheda completa, get_catalog_item; non inventare "
    "articoli, posizioni o quantità. Se il servizio catalogo non è raggiungibile o la sua "
    "risposta non è valida, di' all'utente che l'inventario non è consultabile. "
    "Per salvare, elencare o eliminare note usa add_note, list_notes e delete_note; per eliminare "
    "una nota serve il suo id: se non lo conosci chiama prima list_notes. Non dire che una nota è "
    "stata salvata o eliminata se lo strumento non lo conferma."
)
logger = logging.getLogger(__name__)

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
            except Exception as exc:
                # Es. tool_call con argomenti che langchain-openai non riesce a convertire.
                logger.debug("errore durante la domanda", exc_info=True)
                print(
                    f"Errore: risposta del modello non valida ({exc}). Domanda scartata, riprova.",
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


def make_tools(settings: Settings) -> list[BaseTool]:
    """Strumenti offerti al modello: orologio, convertitore, calcolatrice, date, catalogo e note."""
    return [
        make_clock_tool(settings.default_timezone),
        make_converter_tool(),
        make_calculator_tool(),
        *make_date_tools(settings.giorni_base_url, settings.default_timezone),
        *make_catalog_tools(settings.catalogo_base_url),
        *make_note_tools(settings.note_db_path, settings.default_timezone),
    ]


def create_graph(settings: Settings):
    """Grafo dell'applicazione: modello di LM Studio con i suoi strumenti."""
    tools = make_tools(settings)
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
    try:
        graph = create_graph(settings)
    except MCPStartupError as exc:
        print(f"Server MCP delle note non avviabile: {exc}", file=sys.stderr)
        return 1
    run_chat(graph)
    return 0
