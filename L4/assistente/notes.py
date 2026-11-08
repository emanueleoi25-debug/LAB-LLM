"""Strumenti delle note: il server MCP `servizio_note`, avviato come sottoprocesso stdio."""

import sys
from pathlib import Path

from langchain_core.tools import BaseTool
from mcp import StdioServerParameters

from assistente.mcp_client import load_mcp_tools

# Copia identica di quella del server (che non dipende da `assistente`); un test le confronta.
NOTE_FAILURE_HINT = "Non è possibile leggere o modificare le note: dillo all'utente e non inventarle."
# Cartella che contiene `assistente/` e `servizio_note/`: `cwd` del sottoprocesso, così
# `python -m servizio_note.server` funziona da qualsiasi cartella corrente.
PROJECT_DIR = Path(__file__).resolve().parent.parent


def make_note_tools(db_path: str, timezone: str, timeout: float = 10.0) -> list[BaseTool]:
    """Legge gli strumenti dal server delle note; solleva MCPStartupError se non parte."""
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "servizio_note.server"],
        env={"NOTE_DB_PATH": db_path, "NOTE_TIMEZONE": timezone},
        cwd=PROJECT_DIR,
    )
    return load_mcp_tools(params, NOTE_FAILURE_HINT, label="server delle note", timeout=timeout)
