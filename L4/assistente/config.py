"""Configurazione letta dalle variabili d'ambiente (ed eventualmente da `.env`)."""

import os
from collections.abc import Mapping
from dataclasses import dataclass

from dotenv import find_dotenv, load_dotenv

LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


class ConfigError(Exception):
    """Configurazione mancante o non valida."""


@dataclass(frozen=True)
class Settings:
    base_url: str
    model: str
    log_level: str = "INFO"


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Legge e valida la configurazione; raccoglie tutti gli errori in un unico ConfigError."""
    if env is None:
        load_dotenv(find_dotenv(usecwd=True), override=False)
        env = os.environ

    def value(name: str) -> str:
        return env.get(name, "").strip()

    problems = []
    base_url = value("LMSTUDIO_BASE_URL")
    model = value("LMSTUDIO_MODEL")
    for name, found in (("LMSTUDIO_BASE_URL", base_url), ("LMSTUDIO_MODEL", model)):
        if not found:
            problems.append(f"{name} mancante")

    log_level = (value("LOG_LEVEL") or "INFO").upper()
    if log_level not in LOG_LEVELS:
        problems.append(f"LOG_LEVEL non valido: '{log_level}' (ammessi: {', '.join(LOG_LEVELS)})")

    if problems:
        raise ConfigError("; ".join(problems))
    return Settings(base_url=base_url, model=model, log_level=log_level)
