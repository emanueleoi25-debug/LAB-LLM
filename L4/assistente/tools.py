"""Strumenti che il modello può richiedere: per ora solo l'orologio."""

import functools
from collections.abc import Callable
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, available_timezones

from langchain_core.tools import BaseTool, tool

from assistente.cities import find_city

CLOCK_DESCRIPTION = (
    "Restituisce la data e l'ora attuali in una città. Parametro city: il nome della città "
    "citata dall'utente, così come l'ha scritta (es. 'Miami', 'Nuova York'). Se l'utente non "
    "nomina una città, omettilo e si usa il fuso predefinito."
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


def current_time(city: str | None, default_timezone: str, now: datetime) -> str:
    """Istante `now` in ISO 8601, seguito da città e fuso usati.

    `city` può essere un nome di città o un nome IANA; se manca si usa il fuso predefinito.
    """
    if city is None or not city.strip():
        timezone, used = default_timezone, f"fuso predefinito {default_timezone}"
    elif (iana := canonical_timezone(city)) is not None:
        timezone, used = iana, f"fuso {iana}"
    elif (found := find_city(city)) is not None:
        timezone, used = found.timezone, f"{found.name}, {found.country}, fuso {found.timezone}"
    else:
        return f"Errore: città sconosciuta '{city}'. Indica il nome di una città, ad esempio 'Roma'."
    local = now.astimezone(ZoneInfo(timezone))
    return f"{local.isoformat(timespec='seconds')} ({used})"


def make_clock_tool(
    default_timezone: str, clock: Callable[[], datetime] = utc_now
) -> BaseTool:
    """Crea lo strumento `get_current_time` con fuso predefinito e orologio iniettabile."""

    def get_current_time(city: str | None = None) -> str:
        return current_time(city, default_timezone, clock())

    return tool("get_current_time", description=CLOCK_DESCRIPTION)(get_current_time)
