import sqlite3
from datetime import UTC, datetime, timedelta, timezone

from servizio_note import archivio

NOW = datetime(2026, 11, 8, 20, 40, 12, tzinfo=UTC)


def test_add_creates_folder_and_file(tmp_path):
    path = tmp_path / "a" / "b" / "note.db"
    note = archivio.add(path, "x", NOW)
    assert path.is_file()
    assert (note.id, note.testo, note.creata) == (1, "x", NOW)


def test_creata_is_stored_as_utc_iso(tmp_path):
    path = tmp_path / "note.db"
    archivio.add(path, "x", NOW)
    archivio.add(path, "y", datetime(2026, 11, 8, 21, 40, 12, tzinfo=timezone(timedelta(hours=1))))
    connection = sqlite3.connect(path)
    try:
        rows = connection.execute("SELECT creata FROM note ORDER BY id").fetchall()
    finally:
        connection.close()
    assert rows == [("2026-11-08T20:40:12+00:00",), ("2026-11-08T20:40:12+00:00",)]


def test_list_recent_newest_first_with_total(tmp_path):
    path = tmp_path / "note.db"
    assert archivio.list_recent(path, 2) == ([], 0)
    for text in ("uno", "due", "tre"):
        archivio.add(path, text, NOW)
    notes, total = archivio.list_recent(path, 2)
    assert [n.id for n in notes] == [3, 2]
    assert total == 3


def test_delete_returns_deleted_note_or_none(tmp_path):
    path = tmp_path / "note.db"
    for text in ("uno", "due"):
        archivio.add(path, text, NOW)
    deleted = archivio.delete(path, 2)
    assert (deleted.id, deleted.testo, deleted.creata) == (2, "due", NOW)
    assert archivio.delete(path, 2) is None
    assert archivio.delete(path, 99) is None


def test_ids_are_not_reused(tmp_path):
    path = tmp_path / "note.db"
    archivio.add(path, "uno", NOW)
    archivio.add(path, "due", NOW)
    archivio.delete(path, 2)
    assert archivio.add(path, "tre", NOW).id == 3


def test_data_survives_new_connections(tmp_path):
    path = tmp_path / "note.db"
    archivio.add(path, "presa rotta è «grave»", NOW)
    notes, _ = archivio.list_recent(path, 20)
    assert [n.testo for n in notes] == ["presa rotta è «grave»"]
