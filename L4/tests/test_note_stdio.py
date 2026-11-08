from assistente.notes import make_note_tools


def test_notes_over_stdio(tmp_path, monkeypatch):
    """Il server vero come sottoprocesso stdio, da una cartella corrente qualsiasi."""
    monkeypatch.chdir(tmp_path)
    tools = {t.name: t for t in make_note_tools(str(tmp_path / "note.db"), "Europe/Rome")}
    assert list(tools) == ["add_note", "list_notes", "delete_note"]
    assert tools["add_note"].invoke({"text": "presa rotta è «grave»"}) == (
        "Nota 1 salvata: «presa rotta è «grave»»."
    )
    assert "presa rotta è «grave»" in tools["list_notes"].invoke({})
    assert tools["delete_note"].invoke({"id": 1}).startswith("Nota 1 eliminata: ")
    assert tools["list_notes"].invoke({}) == "Nessuna nota salvata."
