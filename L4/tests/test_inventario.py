"""Test della logica del catalogo (servizio_catalogo/inventario.py): niente FastAPI, niente rete."""

import json
from collections import Counter

import pytest

from servizio_catalogo.inventario import InventoryError, Item, categories, load_items

ITEMS = load_items()


def article(**overrides):
    """Articolo valido di base, modificabile campo per campo."""
    data = {
        "codice": "LAB-001",
        "nome": "Multimetro digitale",
        "categoria": "Misura",
        "parole_chiave": ["tester"],
        "descrizione": "Misura tensione.",
        "posizione": "Armadio A, ripiano 1",
        "quantita": 6,
        "stato": "disponibile",
        "note": "",
    }
    data.update(overrides)
    return data


def write(tmp_path, content):
    path = tmp_path / "inventario.json"
    path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
    return path


# --- file vero ----------------------------------------------------------------------------------


def test_real_file_loads():
    assert len(ITEMS) == 32
    assert categories(ITEMS) == [
        "Misura",
        "Alimentazione",
        "Saldatura",
        "Microcontrollori",
        "Componenti",
        "Cavi e connettori",
        "Utensili",
        "Sicurezza",
    ]
    assert set(Counter(item.categoria for item in ITEMS).values()) == {4}
    assert [item.codice for item in ITEMS] == [f"LAB-{n:03d}" for n in range(1, 33)]
    by_code = {item.codice: item for item in ITEMS}
    assert by_code["LAB-002"].note == "Prenotare con il tecnico di laboratorio."
    for code in ("LAB-016", "LAB-023"):
        assert (by_code[code].stato, by_code[code].quantita) == ("esaurito", 0)
    for code in ("LAB-003", "LAB-012"):
        assert by_code[code].stato == "in manutenzione"
    assert not any("stampa" in item.nome.lower() for item in ITEMS)
    assert by_code["LAB-006"].parole_chiave == ("pile", "stilo")


# --- validazione --------------------------------------------------------------------------------


def test_valid_file_gives_items(tmp_path):
    items = load_items(write(tmp_path, [article()]))
    assert items == (
        Item(
            codice="LAB-001",
            nome="Multimetro digitale",
            categoria="Misura",
            parole_chiave=("tester",),
            descrizione="Misura tensione.",
            posizione="Armadio A, ripiano 1",
            quantita=6,
            stato="disponibile",
            note="",
        ),
    )


def _without_note():
    data = article()
    del data["note"]
    return [data]


@pytest.mark.parametrize(
    ("content", "match"),
    [
        ([], "lista non vuota"),
        ({}, "lista non vuota"),
        ([article(codice="LAB-1")], "'codice'"),
        ([article(), article()], "duplicato"),
        (_without_note(), "mancanti: note"),
        ([article(prezzo=3)], "in più: prezzo"),
        ([article(nome="")], "'nome'"),
        ([article(nome=5)], "'nome'"),
        ([article(quantita=-1)], "'quantita'"),
        ([article(quantita=True)], "'quantita'"),
        ([article(quantita=2.0)], "'quantita'"),
        ([article(stato="rotto")], "'stato'"),
        ([article(stato="esaurito", quantita=3)], "incoerente"),
        ([article(stato="disponibile", quantita=0)], "incoerente"),
        ([article(parole_chiave=["ok", ""])], "'parole_chiave'"),
        ([article(parole_chiave="tester")], "'parole_chiave'"),
        ([article(note=None)], "'note'"),
    ],
)
def test_invalid_file(tmp_path, content, match):
    with pytest.raises(InventoryError, match=match):
        load_items(write(tmp_path, content))


def test_error_names_the_item(tmp_path):
    with pytest.raises(InventoryError, match="LAB-002"):
        load_items(write(tmp_path, [article(), article(codice="LAB-002", quantita=-1)]))
    with pytest.raises(InventoryError, match="n. 1"):
        load_items(write(tmp_path, [article(codice=7)]))
