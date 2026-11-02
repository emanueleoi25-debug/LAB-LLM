"""Ricerca del fuso orario di una città su un archivio locale (nessun accesso alla rete)."""

import functools
from typing import NamedTuple

from geonamescache import GeonamesCache

MIN_POPULATION = 5000


class City(NamedTuple):
    name: str
    country: str
    timezone: str


@functools.lru_cache(maxsize=1)
def _cities_by_name() -> dict[str, City]:
    """Indice nome → città, con nomi principali e alternativi; tra omonimi vince la più popolosa."""
    best: dict[str, tuple[int, City]] = {}
    for record in GeonamesCache(min_city_population=MIN_POPULATION).get_cities().values():
        city = City(record["name"], record["countrycode"], record["timezone"])
        population = record["population"]
        for name in {record["name"], *record["alternatenames"]}:
            key = name.strip().casefold()
            if key and (key not in best or best[key][0] < population):
                best[key] = (population, city)
    return {key: city for key, (_, city) in best.items()}


def find_city(name: str) -> City | None:
    """Città con questo nome, senza distinguere maiuscole e spazi; None se sconosciuta.

    Se il nome contiene una virgola («Miami, Florida») e non viene trovato intero, si riprova
    con la parte prima della virgola.
    """
    index = _cities_by_name()
    key = name.strip().casefold()
    if not key:
        return None
    if key in index:
        return index[key]
    head = key.split(",", 1)[0].strip()
    return index.get(head) if head else None
