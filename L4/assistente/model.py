"""Collegamento al modello servito da LM Studio (API compatibile OpenAI)."""

from collections.abc import Callable, Sequence

import openai
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from assistente.config import Settings

# LM Studio non richiede una chiave, ma il client OpenAI ne vuole una.
API_KEY = "lm-studio"


class ModelCheckError(Exception):
    """LM Studio non raggiungibile o modello non disponibile."""


def list_models(base_url: str, timeout: float = 5.0) -> list[str]:
    """Identificativi dei modelli restituiti da GET /v1/models."""
    client = openai.OpenAI(base_url=base_url, api_key=API_KEY, timeout=timeout)
    return [model.id for model in client.models.list()]


def check_model(
    settings: Settings, list_models_fn: Callable[[str], list[str]] = list_models
) -> None:
    """Verifica che LM Studio risponda e che serva il modello configurato."""
    try:
        available = list_models_fn(settings.base_url)
    except openai.APIError as exc:
        raise ModelCheckError(
            f"LM Studio non raggiungibile a {settings.base_url}: avvia il server o controlla "
            f"LMSTUDIO_BASE_URL. ({exc})"
        ) from exc
    if settings.model not in available:
        raise ModelCheckError(
            f"Modello '{settings.model}' non disponibile su {settings.base_url}. "
            f"Modelli disponibili: {', '.join(available) or 'nessuno'}."
        )


def create_chat_model(settings: Settings, tools: Sequence[BaseTool] = ()) -> Runnable:
    model = ChatOpenAI(base_url=settings.base_url, api_key=API_KEY, model=settings.model)
    return model.bind_tools(tools) if tools else model
