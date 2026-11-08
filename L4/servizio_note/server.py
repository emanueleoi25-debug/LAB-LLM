"""Server MCP delle note: tre strumenti sopra l'archivio SQLite, su stdio.

Avvio: `python -m servizio_note.server`. Configurazione dalle variabili d'ambiente, lette a ogni
chiamata: `NOTE_DB_PATH` (file SQLite, obbligatoria) e `NOTE_TIMEZONE` (fuso per mostrare le date,
predefinito `Europe/Rome`). Gli errori previsti diventano `ToolError`: l'SDK li restituisce al client
come risultato d'errore preceduto da `Error executing tool <nome>: `.
"""

import os
import sqlite3
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from servizio_note import archivio

NOTE_FAILURE_HINT = "Non è possibile leggere o modificare le note: dillo all'utente e non inventarle."
ADD_DESCRIPTION = (
    "Salva una nota nell'archivio delle note persistenti, che restano anche dopo la fine della "
    "sessione. Parametro text: il testo della nota, come l'utente vuole ricordarlo. Usalo quando "
    "l'utente chiede di annotare, segnare o ricordare qualcosa."
)
LIST_DESCRIPTION = (
    "Elenca le note salvate, dalla più recente, con id, data e testo. Usalo per mostrare le note "
    "all'utente e per trovare l'id di una nota da eliminare."
)
DELETE_DESCRIPTION = (
    "Elimina una nota dato il suo id, un numero intero. Se non conosci l'id usa prima list_notes: "
    "non indovinarlo."
)
MAX_TEXT = 1000
MAX_ROWS = 20
DEFAULT_TIMEZONE = "Europe/Rome"

# WARNING: i ToolError previsti (registrati dall'SDK a INFO sullo stderr ereditato dall'agente)
# non devono comparire nel terminale della chat; un crash resta visibile.
server = MCPServer("note", log_level="WARNING")


def _now() -> datetime:
    return datetime.now(UTC)


def _unusable(detail: object) -> ToolError:
    return ToolError(f"archivio delle note non utilizzabile ({detail}). {NOTE_FAILURE_HINT}")


def _db_path() -> str:
    path = os.environ.get("NOTE_DB_PATH", "").strip()
    if not path:
        raise _unusable("NOTE_DB_PATH mancante")
    return path


def _zone() -> ZoneInfo:
    name = os.environ.get("NOTE_TIMEZONE", "").strip() or DEFAULT_TIMEZONE
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise _unusable(f"fuso NOTE_TIMEZONE non valido: '{name}'") from None


def _one_line(text: str) -> str:
    """Gli a capo diventano spazi, così ogni nota resta su una riga dell'elenco."""
    return " ".join(text.split())


@server.tool(description=ADD_DESCRIPTION)
def add_note(text: str) -> str:
    text = text.strip()
    if not text:
        raise ToolError("il testo della nota è vuoto.")
    if len(text) > MAX_TEXT:
        raise ToolError(f"il testo della nota supera {MAX_TEXT} caratteri.")
    path = _db_path()
    try:
        note = archivio.add(path, text, _now())
    except (sqlite3.Error, OSError) as exc:
        raise _unusable(exc) from exc
    return f"Nota {note.id} salvata: «{note.testo}»."


@server.tool(description=LIST_DESCRIPTION)
def list_notes() -> str:
    path, zone = _db_path(), _zone()
    try:
        notes, total = archivio.list_recent(path, MAX_ROWS)
    except (sqlite3.Error, OSError) as exc:
        raise _unusable(exc) from exc
    if total == 0:
        return "Nessuna nota salvata."
    lines = ["1 nota salvata:" if total == 1 else f"{total} note salvate, dalla più recente:"]
    lines += [
        f"- {n.id} ({n.creata.astimezone(zone):%Y-%m-%d %H:%M}): {_one_line(n.testo)}" for n in notes
    ]
    hidden = total - len(notes)
    if hidden == 1:
        lines.append("Altra 1 nota non mostrata.")
    elif hidden > 1:
        lines.append(f"Altre {hidden} note non mostrate.")
    return "\n".join(lines)


@server.tool(description=DELETE_DESCRIPTION)
def delete_note(id: int) -> str:  # noqa: A002 - il nome del parametro è quello visto dal modello
    path = _db_path()
    try:
        note = archivio.delete(path, id)
    except (sqlite3.Error, OSError) as exc:
        raise _unusable(exc) from exc
    if note is None:
        raise ToolError(f"nessuna nota con id {id}. Usa list_notes per vedere gli id.")
    return f"Nota {note.id} eliminata: «{note.testo}»."


def main() -> None:
    server.run("stdio")


if __name__ == "__main__":
    main()
