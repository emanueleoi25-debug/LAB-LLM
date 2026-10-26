"""Configurazione letta dalle variabili d'ambiente (ed eventualmente da `.env`)."""

import os
from collections.abc import Mapping
from dataclasses import dataclass

from dotenv import find_dotenv, load_dotenv

from assistente.tools import canonical_timezone

LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


class ConfigError(Exception):
    """Configurazione mancante o non valida."""


@dataclass(frozen=True)
class Settings:
    base_url: str
    model: str
    log_level: str = "INFO"
    default_timezone: str = "Europe/Rome"
    max_tool_steps: int = 3


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

    raw_timezone = value("DEFAULT_TIMEZONE") or "Europe/Rome"
    default_timezone = canonical_timezone(raw_timezone)
    if default_timezone is None:
        problems.append(f"DEFAULT_TIMEZONE non valido: '{raw_timezone}' (usa un nome IANA come 'Europe/Rome')")

    raw_steps = value("MAX_TOOL_STEPS") or "3"
    try:
        max_tool_steps = int(raw_steps)
    except ValueError:
        max_tool_steps = 0
    if max_tool_steps < 1:
        problems.append(f"MAX_TOOL_STEPS non valido: '{raw_steps}' (serve un intero maggiore o uguale a 1)")

    if problems:
        raise ConfigError("; ".join(problems))
    return Settings(
        base_url=base_url,
        model=model,
        log_level=log_level,
        default_timezone=default_timezone,
        max_tool_steps=max_tool_steps,
    )
