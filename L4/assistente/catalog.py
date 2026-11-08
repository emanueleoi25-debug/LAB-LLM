"""Strumenti del catalogo: client sottili verso il servizio catalogo (FastAPI, via HTTP).

Ogni strumento invia la richiesta al servizio e converte la risposta JSON in un testo per il
modello. Gli strumenti non sollevano mai eccezioni verso il grafo: ogni problema diventa un testo
che inizia con `Errore: `.
"""

from collections.abc import Callable

import httpx
from langchain_core.tools import BaseTool, tool

TIMEOUT = 5.0  # secondi
# Coda dei testi di guasto del servizio (come per il servizio giorni, spec §2.4).
CATALOG_FAILURE_HINT = (
    "Non è possibile consultare l'inventario: dillo all'utente e non rispondere a mente."
)
# Aggiunto ai 404 di get_catalog_item: il servizio non conosce i nomi degli strumenti.
NOT_FOUND_HINT = "Usa search_catalog per trovare il codice."

SEARCH_DESCRIPTION = (
    "Cerca attrezzatura e materiale nell'inventario del laboratorio e restituisce codice, nome, "
    "posizione, quantità e stato degli articoli trovati. Parametri: query, 1-3 parole chiave in "
    "italiano (es. 'multimetro', 'cavo usb'); category, facoltativo, una categoria "
    "dell'inventario. Usalo per sapere se un articolo c'è, dove si trova e quanti pezzi ci sono: "
    "non rispondere a mente."
)

ITEM_DESCRIPTION = (
    "Restituisce la scheda completa di un articolo dell'inventario (descrizione, posizione, "
    "quantità, stato, note) dato il suo codice, es. 'LAB-012'. Se non conosci il codice usa "
    "prima search_catalog."
)


def _count(value: int, singular: str, plural: str) -> str:
    """Numero seguito dalla parola al singolare solo se il valore è 1."""
    return f"{value} {singular if value == 1 else plural}"


def _pieces(quantity: int) -> str:
    return _count(quantity, "pezzo", "pezzi")


def _format_search(data: dict) -> str:
    where = f"per «{data['query']}»"
    if data["categoria"] is not None:
        where += f" nella categoria {data['categoria']}"
    total, articles = data["totale"], data["articoli"]
    if total == 0:
        return f"Nessun articolo trovato {where}: dillo all'utente e non inventare articoli."
    found = "Trovato" if total == 1 else "Trovati"
    lines = [f"{found} {_count(total, 'articolo', 'articoli')} {where}:"]
    lines += [
        f"- {a['codice']} {a['nome']}: {a['posizione']}; {_pieces(a['quantita'])}; {a['stato']}"
        for a in articles
    ]
    hidden = total - len(articles)
    if hidden == 1:
        lines.append("Altro 1 articolo non mostrato: restringi la ricerca.")
    elif hidden > 1:
        lines.append(f"Altri {hidden} articoli non mostrati: restringi la ricerca.")
    return "\n".join(lines)


def _format_item(data: dict) -> str:
    lines = [
        f"{data['codice']} {data['nome']} ({data['categoria']})",
        f"Posizione: {data['posizione']}",
        f"Quantità: {_pieces(data['quantita'])}",
        f"Stato: {data['stato']}",
        f"Descrizione: {data['descrizione']}",
    ]
    if data["note"]:
        lines.append(f"Note: {data['note']}")
    return "\n".join(lines)


def make_catalog_tools(base_url: str, client: httpx.Client | None = None) -> list[BaseTool]:
    """Crea i due strumenti del catalogo.

    `client` sostituisce il client HTTP e serve solo ai test (servizio finto o TestClient
    dell'app vera); `base_url` compare anche nel testo «non raggiungibile».
    """
    if client is None:
        client = httpx.Client(base_url=base_url, timeout=TIMEOUT)

    def _call(
        path: str, params: dict, formatter: Callable[[dict], str], not_found_hint: bool = False
    ) -> str:
        """Chiama il servizio e restituisce il testo di successo o il testo d'errore."""
        try:
            response = client.get(path, params=params)
        except httpx.TransportError:
            return f"Errore: servizio catalogo non raggiungibile a {base_url}. {CATALOG_FAILURE_HINT}"
        except httpx.HTTPError:
            # Errori non di trasporto (per esempio corpo non decodificabile): può mancare il codice.
            return f"Errore: risposta non valida dal servizio catalogo. {CATALOG_FAILURE_HINT}"
        invalid = (
            f"Errore: risposta non valida dal servizio catalogo (HTTP {response.status_code}). "
            f"{CATALOG_FAILURE_HINT}"
        )
        try:
            data = response.json()
        except ValueError:
            return invalid
        if not isinstance(data, dict):
            return invalid
        detail = data.get("detail")
        if response.status_code == 400 and isinstance(detail, str):
            return f"Errore: {detail}"
        if response.status_code == 404 and not_found_hint and isinstance(detail, str):
            return f"Errore: {detail} {NOT_FOUND_HINT}"
        if response.status_code != 200:
            return invalid
        try:
            return formatter(data)
        except (KeyError, TypeError, ValueError):
            return invalid

    def search_catalog(query: str, category: str | None = None) -> str:
        params = {"q": query}
        if category is not None and category.strip():
            params["categoria"] = category
        return _call("/cerca", params, _format_search)

    def get_catalog_item(code: str) -> str:
        return _call("/articolo", {"codice": code}, _format_item, not_found_hint=True)

    return [
        tool("search_catalog", description=SEARCH_DESCRIPTION)(search_catalog),
        tool("get_catalog_item", description=ITEM_DESCRIPTION)(get_catalog_item),
    ]
