"""Ricerca del fuso orario di una città su un archivio locale (nessun accesso alla rete)."""

import functools
import unicodedata
from typing import NamedTuple

from geonamescache import GeonamesCache

MIN_POPULATION = 5000
# Un nome alternativo vince sul nome principale di un'altra città solo se la sua città è almeno
# così tante volte più popolosa («Roma» → Rome, non Roma in Lesotho; «Zaragoza» resta in Spagna).
ALTERNATE_NAME_FACTOR = 10

Index = dict[str, tuple[int, "City"]]


class City(NamedTuple):
    name: str
    country: str
    timezone: str


def _without_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def _add(index: Index, name: str, population: int, city: City) -> None:
    """Registra `name` → `city`; tra omonimi resta la città più popolosa."""
    key = name.strip().casefold()
    if key and (key not in index or index[key][0] < population):
        index[key] = (population, city)


@functools.lru_cache(maxsize=1)
def _indexes() -> tuple[Index, Index]:
    """Due indici nome → (popolazione, città): nomi principali (anche senza accenti) e alternativi."""
    main: Index = {}
    alternate: Index = {}
    for record in GeonamesCache(min_city_population=MIN_POPULATION).get_cities().values():
        city = City(record["name"], record["countrycode"], record["timezone"])
        population = record["population"]
        for name in {record["name"], _without_accents(record["name"])}:
            _add(main, name, population, city)
        for name in record["alternatenames"]:
            _add(alternate, name, population, city)
    return main, alternate


def _lookup(key: str) -> City | None:
    main, alternate = _indexes()
    by_main, by_alternate = main.get(key), alternate.get(key)
    if by_main and (not by_alternate or by_alternate[0] < ALTERNATE_NAME_FACTOR * by_main[0]):
        return by_main[1]
    return by_alternate[1] if by_alternate else None


def find_city(name: str) -> City | None:
    """Città con questo nome, senza distinguere maiuscole e spazi iniziali o finali; None se sconosciuta.

    Il nome principale di una città prevale sul nome alternativo di un'altra, salvo che questa sia
    molto più popolosa (`ALTERNATE_NAME_FACTOR`). Se il nome contiene una virgola («Miami, Florida»)
    e non viene trovato intero, si riprova con la parte prima della virgola.
    """
    key = name.strip().casefold()
    if not key:
        return None
    if (city := _lookup(key)) is not None:
        return city
    head = key.split(",", 1)[0].strip()
    return _lookup(head) if head else None
