"""Grafo LangGraph dell'assistente: stato, nodi e instradamento."""

from typing import Annotated, Protocol, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, BaseMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages


class AssistantState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    tool_steps: int


class ChatModel(Protocol):
    def invoke(self, messages: list[BaseMessage]) -> AIMessage: ...


def build_graph(model: ChatModel):
    """Costruisce e compila il grafo: START → modello → END."""

    def call_model(state: AssistantState) -> dict:
        return {"messages": [model.invoke(state["messages"])]}

    graph = StateGraph(AssistantState)
    graph.add_node("modello", call_model)
    graph.add_edge(START, "modello")
    graph.add_edge("modello", END)
    return graph.compile()
