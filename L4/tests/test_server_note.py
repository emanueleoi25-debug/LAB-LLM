import asyncio
from datetime import UTC, datetime

import pytest
from mcp import Client

from servizio_note import archivio, server as note_server
from servizio_note.server import (
    ADD_DESCRIPTION,
    DELETE_DESCRIPTION,
    LIST_DESCRIPTION,
    NOTE_FAILURE_HINT,
    server,
)

NOW = datetime(2026, 11, 8, 20, 40, tzinfo=UTC)


def prefix(name: str) -> str:
    """Testo che l'SDK antepone ai messaggi dei ToolError."""
    return f"Error executing tool {name}: "


def call(name: str, args: dict | None = None) -> tuple[bool, str]:
    async def run():
        async with Client(server) as client:
            return await client.call_tool(name, args or {})

    result = asyncio.run(run())
    return result.is_error, "\n".join(block.text for block in result.content)


@pytest.fixture(autouse=True)
def archive(tmp_path, monkeypatch):
    path = tmp_path / "note.db"
    monkeypatch.setenv("NOTE_DB_PATH", str(path))
    monkeypatch.delenv("NOTE_TIMEZONE", raising=False)
    monkeypatch.setattr(note_server, "_now", lambda: NOW)
    return path


def test_list_tools_names_descriptions_schemas():
    async def run():
        async with Client(server) as client:
            return (await client.list_tools()).tools

    tools = {t.name: t for t in asyncio.run(run())}
    assert list(tools) == ["add_note", "list_notes", "delete_note"]
    assert tools["add_note"].description == ADD_DESCRIPTION
    assert tools["list_notes"].description == LIST_DESCRIPTION
    assert tools["delete_note"].description == DELETE_DESCRIPTION
    assert tools["add_note"].input_schema["required"] == ["text"]
    assert tools["add_note"].input_schema["properties"]["text"]["type"] == "string"
    assert tools["delete_note"].input_schema["required"] == ["id"]
    assert tools["delete_note"].input_schema["properties"]["id"]["type"] == "integer"
    assert not tools["list_notes"].input_schema.get("required")


def test_descriptions_are_the_spec_texts():
    assert ADD_DESCRIPTION == (
        "Salva una nota nell'archivio delle note persistenti, che restano anche dopo la fine della "
        "sessione. Parametro text: il testo della nota, come l'utente vuole ricordarlo. Usalo "
        "quando l'utente chiede di annotare, segnare o ricordare qualcosa."
    )
    assert LIST_DESCRIPTION == (
        "Elenca le note salvate, dalla più recente, con id, data e testo. Usalo per mostrare le "
        "note all'utente e per trovare l'id di una nota da eliminare."
    )
    assert DELETE_DESCRIPTION == (
        "Elimina una nota dato il suo id, un numero intero. Se non conosci l'id usa prima "
        "list_notes: non indovinarlo."
    )
    assert NOTE_FAILURE_HINT == (
        "Non è possibile leggere o modificare le note: dillo all'utente e non inventarle."
    )


def test_add_note():
    assert call("add_note", {"text": "  calibrare il multimetro "}) == (
        False,
        "Nota 1 salvata: «calibrare il multimetro».",
    )


@pytest.mark.parametrize("text", ["", "   "])
def test_add_note_empty(text):
    assert call("add_note", {"text": text}) == (True, prefix("add_note") + "il testo della nota è vuoto.")


def test_add_note_length_limit():
    assert call("add_note", {"text": "a" * 1000})[0] is False
    assert call("add_note", {"text": " " + "b" * 1000 + " "})[0] is False
    assert call("add_note", {"text": "c" * 1001}) == (
        True,
        prefix("add_note") + "il testo della nota supera 1000 caratteri.",
    )


def test_list_notes_empty():
    assert call("list_notes") == (False, "Nessuna nota salvata.")


def test_list_notes_one(archive):
    archivio.add(archive, "x", NOW)
    assert call("list_notes") == (False, "1 nota salvata:\n- 1 (2026-11-08 21:40): x")


def test_list_notes_many_newest_first(archive):
    for text in ("uno", "due", "tre"):
        archivio.add(archive, text, NOW)
    assert call("list_notes") == (
        False,
        "3 note salvate, dalla più recente:\n"
        "- 3 (2026-11-08 21:40): tre\n"
        "- 2 (2026-11-08 21:40): due\n"
        "- 1 (2026-11-08 21:40): uno",
    )


@pytest.mark.parametrize(
    ("count", "first", "last"),
    [
        (21, "21 note salvate, dalla più recente:", "Altra 1 nota non mostrata."),
        (23, "23 note salvate, dalla più recente:", "Altre 3 note non mostrate."),
    ],
)
def test_list_notes_row_limit(archive, count, first, last):
    for i in range(1, count + 1):
        archivio.add(archive, f"nota {i}", NOW)
    lines = call("list_notes")[1].split("\n")
    assert lines[0] == first
    assert lines[-1] == last
    rows = lines[1:-1]
    assert len(rows) == 20
    assert rows[0].startswith(f"- {count} (")
    assert rows[-1].startswith(f"- {count - 19} (")


def test_list_notes_timezone(archive, monkeypatch):
    monkeypatch.setenv("NOTE_TIMEZONE", "America/New_York")
    archivio.add(archive, "x", datetime(2026, 11, 9, 3, 30, tzinfo=UTC))
    assert call("list_notes") == (False, "1 nota salvata:\n- 1 (2026-11-08 22:30): x")


def test_list_notes_newlines_shown_as_spaces(archive):
    call("add_note", {"text": "banco 3\npresa rotta"})
    assert call("list_notes") == (False, "1 nota salvata:\n- 1 (2026-11-08 21:40): banco 3 presa rotta")
    notes, _ = archivio.list_recent(archive, 20)
    assert notes[0].testo == "banco 3\npresa rotta"


def test_delete_note(archive):
    call("add_note", {"text": "x"})
    assert call("delete_note", {"id": 1}) == (False, "Nota 1 eliminata: «x».")
    assert call("list_notes") == (False, "Nessuna nota salvata.")


@pytest.mark.parametrize("note_id", [7, 0, -1])
def test_delete_note_unknown(note_id):
    assert call("delete_note", {"id": note_id}) == (
        True,
        prefix("delete_note") + f"nessuna nota con id {note_id}. Usa list_notes per vedere gli id.",
    )


def test_delete_note_id_as_string(archive):
    archivio.add(archive, "x", NOW)
    assert call("delete_note", {"id": "1"}) == (False, "Nota 1 eliminata: «x».")


@pytest.mark.parametrize("case", ["senza percorso", "percorso cartella", "fuso non valido"])
def test_archive_unusable(case, tmp_path, monkeypatch):
    if case == "senza percorso":
        monkeypatch.delenv("NOTE_DB_PATH")
    elif case == "percorso cartella":
        monkeypatch.setenv("NOTE_DB_PATH", str(tmp_path))
    else:
        monkeypatch.setenv("NOTE_TIMEZONE", "Marte/Base")
    for name, args in (("add_note", {"text": "x"}), ("list_notes", {}), ("delete_note", {"id": 1})):
        if case == "fuso non valido" and name != "list_notes":
            continue  # il fuso serve solo a mostrare le date
        is_error, text = call(name, args)
        assert is_error, text
        assert text.startswith(prefix(name) + "archivio delle note non utilizzabile ("), text
        assert text.endswith("). " + NOTE_FAILURE_HINT), text
