"""Test della logica del catalogo (servizio_catalogo/inventario.py): niente FastAPI, niente rete."""

import json
from collections import Counter

import pytest

from servizio_catalogo.inventario import (
    CatalogError,
    InventoryError,
    Item,
    categories,
    find,
    load_items,
    normalize,
    query_stems,
    search,
    stem,
)

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


# --- normalizzazione, radici, parole della query -----------------------------------------------


def test_normalize():
    assert normalize("Città, PILE-AA!") == ["citta", "pile", "aa"]
    assert normalize("e\u0300") == ["e"]  # «è» in forma NFD
    assert normalize("ESP32 0,8 mm") == ["esp32", "0", "8", "mm"]


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("resistenze", "resistenz"),
        ("resistenza", "resistenz"),
        ("oscilloscopio", "oscilloscop"),
        ("oscilloscopi", "oscilloscop"),
        ("cavo", "cav"),
        ("cavi", "cav"),
        ("led", "led"),
        ("aria", "ari"),
        ("tester", "tester"),
    ],
)
def test_stem(word, expected):
    assert stem(word) == expected


def test_query_stems():
    assert query_stems("Dove trovo i saldatori?") == {"trov", "saldator"}
    assert query_stems("Arduino Uno") == {"arduin"}


@pytest.mark.parametrize("query", ["dove?", "3D", "   ", "per il"])
def test_query_without_useful_words(query):
    with pytest.raises(CatalogError, match="parole utili"):
        query_stems(query)


# --- ricerca ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "category", "codes"),
    [
        ("multimetro", None, ["LAB-001"]),
        ("oscilloscopio", None, ["LAB-002", "LAB-024"]),
        ("cavo usb", None, ["LAB-022", "LAB-008", "LAB-021", "LAB-023", "LAB-024"]),
        ("resistenze", None, ["LAB-017"]),
        ("batterie", None, ["LAB-006", "LAB-008"]),
        ("PILE", None, ["LAB-006"]),
        ("tester", None, ["LAB-001"]),
        ("stampante 3d", None, []),
        ("pinza", None, ["LAB-003", "LAB-026"]),
        ("pinza", "misura", ["LAB-003"]),
        ("cavo", " CAVI E CONNETTORI ", ["LAB-021", "LAB-022", "LAB-023", "LAB-024"]),
    ],
)
def test_search_examples(query, category, codes):
    result = search(ITEMS, query, category)
    assert [item.codice for item in result.items] == codes
    assert result.total == len(codes)


def test_search_category_name_as_in_file():
    assert search(ITEMS, "pinza", "misura").category == "Misura"
    assert search(ITEMS, "pinza").category is None


def _item(code, name):
    return Item(code, name, "Prova", (), "Descrizione.", "Banco 1", 1, "disponibile", "")


def test_search_limit():
    items = [_item(f"LAB-{n:03d}", f"Cavo {n}") for n in range(1, 13)]
    items.append(_item("LAB-013", "Cavo usb"))
    result = search(items, "cavo usb")
    assert result.total == 13
    assert [item.codice for item in result.items] == ["LAB-013"] + [
        f"LAB-{n:03d}" for n in range(1, 10)
    ]


def test_search_unknown_category():
    with pytest.raises(CatalogError) as err:
        search(ITEMS, "cavo", "stampanti")
    assert str(err.value) == (
        "categoria 'stampanti' inesistente. Categorie valide: Misura, Alimentazione, "
        "Saldatura, Microcontrollori, Componenti, Cavi e connettori, Utensili, Sicurezza."
    )


# --- dettaglio ----------------------------------------------------------------------------------


def test_find():
    assert find(ITEMS, " lab-002 ").codice == "LAB-002"
    for code in ("LAB-12", "12", "LAB 002", ""):
        assert find(ITEMS, code) is None
