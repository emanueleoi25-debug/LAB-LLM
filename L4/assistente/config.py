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
    max_revisions: int = 1
    # Il valore predefinito serve solo ai test che costruiscono Settings a mano:
    # load_settings richiede GIORNI_BASE_URL.
    giorni_base_url: str = "http://localhost:8000"
    # Come sopra: load_settings richiede CATALOGO_BASE_URL.
    catalogo_base_url: str = "http://localhost:8001"
    # Come sopra: load_settings richiede NOTE_DB_PATH (e la rende assoluta).
    note_db_path: str = "dati/note.db"
    # Testo dell'ambito per il router; load_settings lo legge sempre da AMBITO_PATH.
    ambito: str = ""


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
    giorni_base_url = value("GIORNI_BASE_URL")
    catalogo_base_url = value("CATALOGO_BASE_URL")
    note_db_path = value("NOTE_DB_PATH")
    for name, found in (
        ("LMSTUDIO_BASE_URL", base_url),
        ("LMSTUDIO_MODEL", model),
        ("GIORNI_BASE_URL", giorni_base_url),
        ("CATALOGO_BASE_URL", catalogo_base_url),
        ("NOTE_DB_PATH", note_db_path),
    ):
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

    raw_revisions = value("MAX_REVISIONI") or "1"
    try:
        max_revisions = int(raw_revisions)
    except ValueError:
        max_revisions = 0
    if max_revisions < 1:
        problems.append(f"MAX_REVISIONI non valido: '{raw_revisions}' (serve un intero maggiore o uguale a 1)")

    ambito_path = value("AMBITO_PATH") or "ambito.md"
    ambito = ""
    try:
        with open(ambito_path, encoding="utf-8-sig") as f:
            ambito = f.read().strip()
    except (OSError, UnicodeDecodeError) as exc:
        problems.append(f"AMBITO_PATH non leggibile: '{ambito_path}' ({exc})")
    else:
        if not ambito:
            problems.append(f"AMBITO_PATH vuoto: '{ambito_path}'")

    if problems:
        raise ConfigError("; ".join(problems))
    return Settings(
        base_url=base_url,
        model=model,
        log_level=log_level,
        default_timezone=default_timezone,
        max_tool_steps=max_tool_steps,
        max_revisions=max_revisions,
        giorni_base_url=giorni_base_url,
        catalogo_base_url=catalogo_base_url,
        # Assoluta: il sottoprocesso del server delle note non dipende dalla cartella corrente.
        note_db_path=os.path.abspath(note_db_path),
        ambito=ambito,
    )
