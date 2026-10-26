"""Grafo LangGraph dell'assistente: stato, nodi e instradamento.

START → modello ─┬─ nessuna tool_call ─────────────────→ END
                 ├─ tool_call, tool_steps < max ──→ strumenti → modello
                 └─ tool_call, tool_steps >= max ─→ limite → END
"""

import logging
from collections.abc import Sequence
from typing import Annotated, Protocol, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, BaseMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

logger = logging.getLogger(__name__)

TOOL_SKIPPED = "non eseguito: limite di passaggi raggiunto"
LIMIT_REPLY = (
    "Mi fermo: ho raggiunto il limite di {max_tool_steps} passaggi con gli strumenti. "
    "Prova a riformulare la domanda."
)


class AssistantState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    tool_steps: int


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


def build_graph(model: ChatModel, tools: Sequence[BaseTool] = (), max_tool_steps: int = 3):
    """Costruisce e compila il grafo con i nodi `modello`, `strumenti` e `limite`."""
    tools_by_name = {t.name: t for t in tools}

    def call_model(state: AssistantState) -> dict:
        return {"messages": [model.invoke(state["messages"])]}

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
        return {"messages": [*skipped, reply]}

    def route_after_model(state: AssistantState) -> str:
        if not _pending_tool_calls(state):
            return END
        if state["tool_steps"] < max_tool_steps:
            return "strumenti"
        return "limite"

    graph = StateGraph(AssistantState)
    graph.add_node("modello", call_model)
    graph.add_node("strumenti", run_tools)
    graph.add_node("limite", stop_at_limit)
    graph.add_edge(START, "modello")
    graph.add_conditional_edges("modello", route_after_model, ["strumenti", "limite", END])
    graph.add_edge("strumenti", "modello")
    graph.add_edge("limite", END)
    return graph.compile()
