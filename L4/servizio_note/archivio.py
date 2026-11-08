"""Archivio SQLite delle note: solo SQL, nessuna dipendenza da `mcp`.

Ogni funzione apre e chiude la sua connessione (il server dura una sola chiamata). Gli errori di
`sqlite3` e quelli della creazione della cartella salgono al chiamante.
"""

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

# AUTOINCREMENT: un id eliminato non viene mai riassegnato (spec §3.1).
SCHEMA = (
    "CREATE TABLE IF NOT EXISTS note ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, testo TEXT NOT NULL, creata TEXT NOT NULL)"
)


@dataclass(frozen=True)
class Note:
    id: int
    testo: str
    creata: datetime  # istante UTC


def _connect(path: str | Path) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute(SCHEMA)
    return connection


def _note(row: tuple) -> Note:
    note_id, testo, creata = row
    return Note(note_id, testo, datetime.fromisoformat(creata))


def add(path: str | Path, text: str, now: datetime) -> Note:
    """Salva `text` così com'è con l'istante `now` (convertito in UTC)."""
    creata = now.astimezone(UTC).isoformat(timespec="seconds")
    with closing(_connect(path)) as connection, connection:
        cursor = connection.execute("INSERT INTO note (testo, creata) VALUES (?, ?)", (text, creata))
        return Note(cursor.lastrowid, text, datetime.fromisoformat(creata))


def list_recent(path: str | Path, limit: int) -> tuple[list[Note], int]:
    """Al massimo `limit` note dalla più recente (id decrescente) e il totale."""
    with closing(_connect(path)) as connection:
        rows = connection.execute(
            "SELECT id, testo, creata FROM note ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        (total,) = connection.execute("SELECT COUNT(*) FROM note").fetchone()
    return [_note(row) for row in rows], total


def delete(path: str | Path, note_id: int) -> Note | None:
    """Elimina la nota e la restituisce; `None` se l'id non esiste."""
    with closing(_connect(path)) as connection, connection:
        row = connection.execute(
            "SELECT id, testo, creata FROM note WHERE id = ?", (note_id,)
        ).fetchone()
        if row is None:
            return None
        connection.execute("DELETE FROM note WHERE id = ?", (note_id,))
    return _note(row)
