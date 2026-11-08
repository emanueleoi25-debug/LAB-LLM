"""Inventario del laboratorio: caricamento e validazione del file JSON, ricerca e dettaglio.

Logica pura, senza FastAPI. Se il file non è valido `load_items` solleva `InventoryError` e il
servizio non parte; i dati dell'utente non validi sollevano `CatalogError`.
"""

import json
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

DATA_FILE = Path(__file__).with_name("inventario.json")
FIELDS = (
    "codice",
    "nome",
    "categoria",
    "parole_chiave",
    "descrizione",
    "posizione",
    "quantita",
    "stato",
    "note",
)
STATES = ("disponibile", "in manutenzione", "esaurito")
_CODE = re.compile(r"LAB-\d{3}")
# Campi di testo che non possono essere vuoti (le note sì).
_REQUIRED_TEXT = ("nome", "categoria", "descrizione", "posizione")
# Parole della query ignorate dalla ricerca (confrontate dopo la normalizzazione).
STOPWORDS = frozenset(
    "che chi con cui dal dai dei del della delle dello degli dove per tra fra una uno gli sul "
    "nel quale quali quanti quante quanto avete sono".split()
)
MAX_RESULTS = 10
_MIN_WORD = 3
_VOWELS = "aeiou"


class InventoryError(Exception):
    """File dell'inventario non valido: il servizio non parte."""


class CatalogError(Exception):
    """Dati dell'utente non validi (diventa una risposta 400)."""


@dataclass(frozen=True)
class Item:
    codice: str
    nome: str
    categoria: str
    parole_chiave: tuple[str, ...]
    descrizione: str
    posizione: str
    quantita: int
    stato: str
    note: str


def _is_text(value: object) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _problem(data: dict) -> str | None:
    """Primo problema di un articolo, oppure None se è valido (il controllo dei duplicati è a parte)."""
    missing = [name for name in FIELDS if name not in data]
    if missing:
        return f"campi mancanti: {', '.join(missing)}"
    extra = [name for name in data if name not in FIELDS]
    if extra:
        return f"campi in più: {', '.join(extra)}"
    invalid = None
    if not (isinstance(data["codice"], str) and _CODE.fullmatch(data["codice"])):
        invalid = "codice"
    elif not all(_is_text(data[name]) for name in _REQUIRED_TEXT):
        invalid = next(name for name in _REQUIRED_TEXT if not _is_text(data[name]))
    elif not (
        isinstance(data["parole_chiave"], list) and all(_is_text(k) for k in data["parole_chiave"])
    ):
        invalid = "parole_chiave"
    elif not (type(data["quantita"]) is int and data["quantita"] >= 0):
        invalid = "quantita"
    elif data["stato"] not in STATES:
        invalid = "stato"
    elif not isinstance(data["note"], str):
        invalid = "note"
    if invalid is not None:
        return f"campo '{invalid}' non valido"
    if data["stato"] == "esaurito" and data["quantita"] != 0:
        return f"stato 'esaurito' incoerente con quantita {data['quantita']}"
    if data["quantita"] == 0 and data["stato"] != "esaurito":
        return f"quantita 0 incoerente con stato '{data['stato']}'"
    return None


def load_items(path: Path | None = None) -> tuple[Item, ...]:
    """Legge e valida l'inventario (di norma `inventario.json` accanto a questo modulo)."""
    with open(path or DATA_FILE, encoding="utf-8") as file:
        content = json.load(file)
    if not isinstance(content, list) or not content:
        raise InventoryError("inventario non valido: serve una lista non vuota di articoli")
    items = []
    seen = set()
    for index, data in enumerate(content, start=1):
        label = data.get("codice") if isinstance(data, dict) else None
        label = label if isinstance(label, str) else f"n. {index}"
        problem = "non è un oggetto" if not isinstance(data, dict) else _problem(data)
        if problem is None and data["codice"] in seen:
            problem = "codice duplicato"
        if problem is not None:
            raise InventoryError(f"inventario non valido: articolo {label}: {problem}")
        seen.add(data["codice"])
        items.append(Item(**{**data, "parole_chiave": tuple(data["parole_chiave"])}))
    return tuple(items)


def categories(items: Sequence[Item]) -> list[str]:
    """Categorie presenti, nell'ordine di prima apparizione."""
    return list(dict.fromkeys(item.categoria for item in items))


@dataclass(frozen=True)
class SearchResult:
    items: tuple[Item, ...]  # al massimo MAX_RESULTS
    total: int  # numero di tutti i risultati
    category: str | None  # nome della categoria come nel file, o None


def normalize(text: str) -> list[str]:
    """Parole del testo: minuscole, senza accenti, solo lettere a-z e cifre."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    plain = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", plain).split()


def stem(word: str) -> str:
    """Radice grezza: toglie le vocali finali finché la parola è più lunga di 3 caratteri."""
    while len(word) > 3 and word[-1] in _VOWELS:
        word = word[:-1]
    return word


def query_stems(query: str) -> set[str]:
    """Radici delle parole utili della query; solleva CatalogError se non ce n'è nessuna."""
    stems = {
        stem(word)
        for word in normalize(query)
        if len(word) >= _MIN_WORD and word not in STOPWORDS
    }
    if not stems:
        raise CatalogError(
            "la ricerca non contiene parole utili (servono parole di almeno 3 lettere)."
        )
    return stems


def _item_stems(item: Item) -> set[str]:
    words = normalize(item.nome) + normalize(item.categoria)
    for keyword in item.parole_chiave:
        words += normalize(keyword)
    return {stem(word) for word in words}


def _resolve_category(items: Sequence[Item], category: str) -> str:
    wanted = " ".join(normalize(category))
    for name in categories(items):
        if " ".join(normalize(name)) == wanted:
            return name
    valid = ", ".join(categories(items))
    raise CatalogError(f"categoria '{category.strip()}' inesistente. Categorie valide: {valid}.")


def search(items: Sequence[Item], query: str, category: str | None = None) -> SearchResult:
    """Articoli che contengono almeno una radice della query, dal punteggio più alto."""
    name = None if category is None else _resolve_category(items, category)
    stems = query_stems(query)
    scored = []
    for item in items:
        if name is not None and item.categoria != name:
            continue
        score = len(stems & _item_stems(item))
        if score > 0:
            scored.append((-score, item.codice, item))
    scored.sort(key=lambda entry: entry[:2])
    found = [item for _, _, item in scored]
    return SearchResult(tuple(found[:MAX_RESULTS]), len(found), name)


def find(items: Sequence[Item], code: str) -> Item | None:
    """Articolo con il codice dato (spazi esterni e maiuscole indifferenti), oppure None."""
    wanted = code.strip().upper()
    return next((item for item in items if item.codice == wanted), None)
