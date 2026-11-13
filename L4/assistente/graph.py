"""Grafo LangGraph dell'assistente: stato, nodi e instradamento.

START → router ─┬─ conversazione (anche risposta non utilizzabile) → agente
                └─ fuori_ambito → rifiuto → END

agente ─┬─ tool_call, tool_steps < max ─→ strumenti → agente
        ├─ tool_call, tool_steps >= max → limite → END
        └─ nessuna tool_call ───────────→ revisore

revisore ─┬─ approvata (coerente o risposta non utilizzabile) → END
          ├─ rifiutata, revisioni < max_revisions ──────────→ agente
          └─ rifiutata, revisioni = max_revisions ──────────→ END (resta l'ultima bozza)

Senza router (build_graph senza `router`) il grafo parte direttamente da `agente`; senza revisore
(build_graph senza `reviewer`) l'agente senza tool_call va a END. Bozze rifiutate e indicazioni del
revisore vengono tolte dalla cronologia a fine turno.
"""

import logging
from uuid import uuid4
from collections.abc import Sequence
from typing import Annotated, NotRequired, Protocol, TypedDict

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    BaseMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from assistente.revisore import Reviewer
from assistente.router import OUT_OF_SCOPE, Router

logger = logging.getLogger(__name__)

TOOL_SKIPPED = "non eseguito: limite di passaggi raggiunto"
LIMIT_REPLY = (
    "Mi fermo: ho raggiunto il limite di {max_tool_steps} passaggi con gli strumenti. "
    "Prova a riformulare la domanda."
)
REFUSAL_REPLY = (
    "Posso aiutarti solo con il laboratorio: ora e fusi orari, unità di misura, calcoli, date e "
    "scadenze, inventario e note. Questa domanda è fuori dal mio ambito."
)
REVIEW_HINT = (
    "Indicazione del revisore: la risposta non è coerente con la domanda dell'utente. "
    "Motivo: {motivo} Rispondi di nuovo alla domanda, in modo completo."
)
APPROVED, REJECTED, AT_LIMIT = "approvata", "rifiutata", "limite"


class AssistantState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    tool_steps: int
    categoria: NotRequired[str]  # "conversazione" o "fuori_ambito", scritta dal router
    motivo: NotRequired[str]  # motivo del router (o dell'inutilizzabilità della risposta)
    revisioni: NotRequired[int]  # rifiuti del revisore in questo turno
    scartati: NotRequired[list[str]]  # id di bozze rifiutate e indicazioni, tolti a fine turno
    esito_revisione: NotRequired[str]  # "approvata", "rifiutata" o "limite"
    motivo_revisione: NotRequired[str]  # motivo del revisore (o dell'inutilizzabilità della risposta)


class ChatModel(Protocol):
    def invoke(self, messages: list[BaseMessage]) -> AIMessage: ...


def _pending_tool_calls(state: AssistantState) -> list[dict]:
    """Chiamate dell'ultima AIMessage, comprese quelle con argomenti non interpretabili.

    Anche le `invalid_tool_calls` vanno chiuse con una ToolMessage: altrimenti la cronologia
    conterrebbe una chiamata senza risposta e la richiesta successiva verrebbe rifiutata.
    """
    last = state["messages"][-1]
    if not isinstance(last, AIMessage):
        return []
    return [*last.tool_calls, *last.invalid_tool_calls]


def _one_line(text: str) -> str:
    return text.replace("\n", "\\n")


def _role(message: BaseMessage) -> str:
    if isinstance(message, SystemMessage):
        return "sistema"
    if isinstance(message, HumanMessage):
        return "utente"
    if isinstance(message, ToolMessage):
        return f"strumento {message.name}"
    return message.type


def _log_sent(messages: list[AnyMessage]) -> None:
    """Registra i messaggi nuovi per il modello: quelli dopo la sua ultima risposta."""
    start = 0
    for i, message in enumerate(messages):
        if isinstance(message, AIMessage):
            start = i + 1
    for message in messages[start:]:
        logger.info("→ modello [%s] %s", _role(message), _one_line(message.text))


def _log_received(message: AIMessage) -> None:
    for tool_call in message.tool_calls:
        logger.info("← modello [chiamata] %s %s", tool_call["name"], tool_call["args"])
    for tool_call in message.invalid_tool_calls:
        detail = tool_call.get("error") or tool_call.get("args")
        logger.info("← modello [chiamata non valida] %s %s", tool_call.get("name"), _one_line(str(detail)))
    if message.text:
        logger.info("← modello [risposta] %s", _one_line(message.text))


def _discard(state: AssistantState) -> list[RemoveMessage]:
    """Toglie dalla cronologia le bozze rifiutate e le indicazioni del revisore di questo turno."""
    discarded = state.get("scartati", [])
    if discarded:
        logger.info("revisore: tolti %d messaggi dalla cronologia", len(discarded))
    return [RemoveMessage(id=message_id) for message_id in discarded]


def build_graph(
    model: ChatModel,
    tools: Sequence[BaseTool] = (),
    max_tool_steps: int = 3,
    *,
    router: Router | None = None,
    reviewer: Reviewer | None = None,
    max_revisions: int = 1,
):
    """Costruisce e compila il grafo: `agente`, `strumenti`, `limite` e, se presenti, `router` e
    `rifiuto` (con il router) e `revisore` (con il revisore)."""
    tools_by_name = {t.name: t for t in tools}

    def call_model(state: AssistantState) -> dict:
        _log_sent(state["messages"])
        message = model.invoke(state["messages"])
        if message.id is not None and any(m.id == message.id for m in state["messages"]):
            # Con lo stesso id add_messages sostituirebbe il messaggio vecchio (per esempio la bozza
            # rifiutata) e la pulizia del revisore toglierebbe poi anche la risposta finale.
            message = message.model_copy(update={"id": str(uuid4())})
        _log_received(message)
        return {"messages": [message]}

    def run_tools(state: AssistantState) -> dict:
        results = []
        for tool_call in _pending_tool_calls(state):
            name, args = tool_call["name"], tool_call["args"]
            logger.info("strumento richiesto: %s %s", name, args)
            tool = tools_by_name.get(name)
            if tool_call.get("type") == "invalid_tool_call":
                content = f"Errore: argomenti non validi per {name}: {tool_call.get('error') or args}"
            elif tool is None:
                content = f"Errore: strumento sconosciuto '{name}'."
            else:
                try:
                    content = str(tool.invoke(args))
                except Exception as exc:
                    content = f"Errore durante l'esecuzione di {name}: {exc}"
            logger.info("risultato strumento: %s", content)
            results.append(ToolMessage(content=content, tool_call_id=tool_call["id"], name=name))
        return {"messages": results, "tool_steps": state["tool_steps"] + 1}

    def stop_at_limit(state: AssistantState) -> dict:
        logger.warning("limite di passaggi raggiunto (%d)", max_tool_steps)
        skipped = [
            ToolMessage(content=TOOL_SKIPPED, tool_call_id=tool_call["id"], name=tool_call["name"])
            for tool_call in _pending_tool_calls(state)
        ]
        reply = AIMessage(content=LIMIT_REPLY.format(max_tool_steps=max_tool_steps))
        return {"messages": [*_discard(state), *skipped, reply]}

    def classify(state: AssistantState) -> dict:
        decision = router.classify(state["messages"])
        if decision.errore is None:
            logger.info("router: categoria=%s motivo=%s", decision.categoria, _one_line(decision.motivo))
        else:
            logger.warning(
                "router: risposta non utilizzabile (%s), la domanda passa all'agente: %s",
                decision.errore,
                _one_line(decision.grezza),
            )
        return {"categoria": decision.categoria, "motivo": decision.motivo}

    def route_after_router(state: AssistantState) -> str:
        target = "rifiuto" if state["categoria"] == OUT_OF_SCOPE else "agente"
        logger.info("router → %s", target)
        return target

    def refuse(state: AssistantState) -> dict:
        logger.info("rifiuto: domanda fuori ambito, agente non eseguito")
        return {"messages": [AIMessage(content=REFUSAL_REPLY)]}

    def review_answer(state: AssistantState) -> dict:
        revisions = state.get("revisioni", 0)
        discarded = state.get("scartati", [])
        review = reviewer.review(state["messages"], discarded)
        if review.errore is None:
            logger.info(
                "revisore: coerente=%s motivo=%s", "sì" if review.coerente else "no", _one_line(review.motivo)
            )
        else:
            logger.warning(
                "revisore: risposta non utilizzabile (%s), risposta approvata: %s",
                review.errore,
                _one_line(review.grezza),
            )
        result = {"motivo_revisione": review.motivo}
        if review.coerente:
            return {**result, "esito_revisione": APPROVED, "messages": _discard(state)}
        if revisions >= max_revisions:
            logger.warning(
                "revisore: limite di revisioni raggiunto (%d), restituita l'ultima risposta", max_revisions
            )
            return {**result, "esito_revisione": AT_LIMIT, "messages": _discard(state)}
        hint = HumanMessage(REVIEW_HINT.format(motivo=review.motivo), id=str(uuid4()))
        return {
            **result,
            "esito_revisione": REJECTED,
            "revisioni": revisions + 1,
            "scartati": [*discarded, state["messages"][-1].id, hint.id],
            "messages": [hint],
        }

    def route_after_reviewer(state: AssistantState) -> str:
        if state["esito_revisione"] == REJECTED:
            logger.info("revisore → agente (revisione %d di %d)", state["revisioni"], max_revisions)
            return "agente"
        logger.info("revisore → END")
        return END

    def route_after_model(state: AssistantState) -> str:
        if not _pending_tool_calls(state):
            return "revisore" if reviewer is not None else END
        if state["tool_steps"] < max_tool_steps:
            return "strumenti"
        return "limite"

    graph = StateGraph(AssistantState)
    graph.add_node("agente", call_model)
    graph.add_node("strumenti", run_tools)
    graph.add_node("limite", stop_at_limit)
    if router is None:
        graph.add_edge(START, "agente")
    else:
        graph.add_node("router", classify)
        graph.add_node("rifiuto", refuse)
        graph.add_edge(START, "router")
        graph.add_conditional_edges("router", route_after_router, ["agente", "rifiuto"])
        graph.add_edge("rifiuto", END)
    after_model = ["strumenti", "limite", END]
    if reviewer is not None:
        graph.add_node("revisore", review_answer)
        graph.add_conditional_edges("revisore", route_after_reviewer, ["agente", END])
        after_model.append("revisore")
    graph.add_conditional_edges("agente", route_after_model, after_model)
    graph.add_edge("strumenti", "agente")
    graph.add_edge("limite", END)
    return graph.compile()
