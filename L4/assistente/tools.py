"""Strumenti che il modello può richiedere: per ora solo l'orologio."""

import functools
from collections.abc import Callable
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, available_timezones

from langchain_core.tools import BaseTool, tool

CLOCK_DESCRIPTION = (
    "Restituisce la data e l'ora attuali. Parametro timezone: nome IANA del fuso orario, "
    "ad esempio 'Asia/Tokyo'. Se omesso usa il fuso predefinito."
)


def utc_now() -> datetime:
    return datetime.now(UTC)


@functools.lru_cache(maxsize=1)
def _timezones_by_lower_name() -> dict[str, str]:
    return {name.lower(): name for name in available_timezones()}


def canonical_timezone(name: str) -> str | None:
    """Nome IANA canonico, senza distinguere maiuscole e minuscole; None se sconosciuto.

    Il confronto avviene sull'elenco dei fusi noti, così il risultato non dipende dal file
    system (Windows non distingue le maiuscole, Linux sì).
    """
    name = name.strip()
    by_lower = _timezones_by_lower_name()
    if name in by_lower.values():
        return name
    return by_lower.get(name.lower())


def current_time(timezone: str | None, default_timezone: str, now: datetime) -> str:
    """Istante `now` nel fuso richiesto (o in quello predefinito), in ISO 8601 con il nome del fuso."""
    requested = timezone if timezone is not None and timezone.strip() else default_timezone
    name = canonical_timezone(requested)
    if name is None:
        return f"Errore: fuso orario sconosciuto '{requested}'. Usa un nome IANA come 'Europe/Rome'."
    local = now.astimezone(ZoneInfo(name))
    return f"{local.isoformat(timespec='seconds')} ({name})"


def make_clock_tool(
    default_timezone: str, clock: Callable[[], datetime] = utc_now
) -> BaseTool:
    """Crea lo strumento `get_current_time` con fuso predefinito e orologio iniettabile."""

    def get_current_time(timezone: str | None = None) -> str:
        return current_time(timezone, default_timezone, clock())

    return tool("get_current_time", description=CLOCK_DESCRIPTION)(get_current_time)
