"""Strumenti delle date: client sottili verso il servizio giorni (FastAPI, via HTTP).

Ogni strumento invia la richiesta al servizio e converte la risposta JSON in un testo per il
modello. «Oggi» è calcolato qui, nel fuso predefinito, e passato sempre al servizio. Gli
strumenti non sollevano mai eccezioni verso il grafo: ogni problema diventa un testo che
inizia con `Errore: `.
"""

from collections.abc import Callable
from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx
from langchain_core.tools import BaseTool, tool

from assistente.tools import utc_now

TIMEOUT = 5.0  # secondi
# Anni coperti dal file delle festività del servizio (servizio_giorni/festivita.json).
_YEARS = "2020-2040"
# Coda dei testi di guasto del servizio: senza, il modello rispondeva a mente (spec §10.1).
SERVICE_FAILURE_HINT = (
    "Non è possibile calcolare il risultato: dillo all'utente e non calcolarlo a mente."
)

DAYS_BETWEEN_DESCRIPTION = (
    "Conta i giorni tra due date: giorni di calendario e giorni lavorativi in Italia "
    "(esclusi sabati, domeniche e festività nazionali). Parametri: end, la data di arrivo; "
    "start, la data di partenza (omettilo per partire da oggi). Date come AAAA-MM-GG; se "
    "l'utente non dice l'anno passa MM-GG (es. '12-25' per Natale) e si usa la prossima "
    "occorrenza. Se una data non è valida restituisce un errore che spiega il motivo: "
    "chiamalo comunque, non rispondere a mente."
)

ADD_DAYS_DESCRIPTION = (
    "Calcola la data che si ottiene aggiungendo (o togliendo, con un numero negativo) "
    "giorni di calendario a una data. Parametri: days, il numero di giorni (es. 30, oppure "
    "-10 per '10 giorni fa'); start, la data di partenza come AAAA-MM-GG o MM-GG (omettilo "
    "per partire da oggi). Se i dati non sono validi restituisce un errore che spiega il "
    "motivo: chiamalo comunque, non rispondere a mente."
)

ADD_BUSINESS_DAYS_DESCRIPTION = (
    "Calcola una scadenza in giorni lavorativi in Italia (esclusi sabati, domeniche e "
    "festività nazionali): restituisce il giorno lavorativo che cade dopo days giorni "
    "lavorativi, senza contare la data di partenza. Parametri: days, il numero di giorni "
    "lavorativi (negativo per andare indietro); start, la data di partenza come AAAA-MM-GG "
    "o MM-GG (omettilo per partire da oggi). Se i dati non sono validi restituisce un "
    "errore che spiega il motivo: chiamalo comunque, non rispondere a mente."
)

DATE_INFO_DESCRIPTION = (
    "Dice che giorno della settimana è una data, se è una festività nazionale italiana "
    "(con il nome), se cade nel fine settimana e se è lavorativa. Parametro: date, come "
    "AAAA-MM-GG o MM-GG (omettilo per oggi). Se la data non è valida restituisce un errore "
    "che spiega il motivo: chiamalo comunque, non rispondere a mente."
)


def today(default_timezone: str, now: datetime) -> date:
    """Data corrente nel fuso indicato, a partire dall'istante `now`."""
    return now.astimezone(ZoneInfo(default_timezone)).date()


def _count(value: int, singular: str, plural: str) -> str:
    """Numero seguito dalla parola al singolare solo se il valore assoluto è 1."""
    return f"{value} {singular if abs(value) == 1 else plural}"


def _format_between(data: dict) -> str:
    head = (
        f"Dal {data['inizio']} ({data['giorno_inizio']}) "
        f"al {data['fine']} ({data['giorno_fine']}): "
        f"{_count(data['giorni'], 'giorno', 'giorni')} di calendario"
    )
    if data["lavorativi"] is None:
        return f"{head}; giorni lavorativi non disponibili fuori dagli anni {_YEARS}."
    working = _count(data["lavorativi"], "giorno lavorativo", "giorni lavorativi")
    return f"{head}, {working} (esclusa la partenza, inclusa la data di arrivo)."


def _format_add(data: dict, singular: str, plural: str) -> str:
    """Parte comune a `add_days` e `add_business_days`: «data (giorno) ± N giorni = risultato»."""
    days = data["giorni"]
    sign = "-" if days < 0 else "+"
    return (
        f"{data['data']} ({data['giorno_data']}) {sign} {_count(abs(days), singular, plural)} "
        f"= {data['risultato']} ({data['giorno_risultato']})"
    )


def _format_add_days(data: dict) -> str:
    return _format_add(data, "giorno", "giorni")


def _format_add_business_days(data: dict) -> str:
    text = _format_add(data, "giorno lavorativo", "giorni lavorativi")
    skipped = data["festivita_saltate"]
    if not skipped:
        return f"{text}; nessuna festività saltata."
    names = ", ".join(f"{h['data']} {h['nome']}" for h in skipped)
    return f"{text}; festività saltate: {names}."


def _format_info(data: dict) -> str:
    head = f"{data['data']} ({data['giorno']}):"
    holiday, working = data["festivita"], data["lavorativo"]
    if holiday is None and working is None:  # data fuori dagli anni del file
        return f"{head} festività non disponibili fuori dagli anni {_YEARS}."
    parts = []
    if holiday is not None:
        parts.append(f"festività, {holiday}")
    if data["fine_settimana"]:
        parts.append("fine settimana")
    if not working:
        parts.append("non lavorativo")
    elif not parts:
        return f"{head} giorno lavorativo."
    return f"{head} {'; '.join(parts)}."


def make_date_tools(
    base_url: str,
    default_timezone: str,
    clock: Callable[[], datetime] = utc_now,
    transport: httpx.BaseTransport | None = None,
) -> list[BaseTool]:
    """Crea i quattro strumenti delle date.

    `clock` fornisce l'istante corrente (iniettabile nei test); `transport` sostituisce il
    trasporto di rete e serve solo ai test.
    """
    client = httpx.Client(base_url=base_url, timeout=TIMEOUT, transport=transport)

    def _call(path: str, params: dict, formatter: Callable[[dict], str]) -> str:
        """Chiama il servizio e restituisce il testo di successo o il testo d'errore."""
        params = {"oggi": today(default_timezone, clock()).isoformat(), **params}
        try:
            response = client.get(path, params=params)
        except httpx.TransportError:
            return f"Errore: servizio giorni non raggiungibile a {base_url}. {SERVICE_FAILURE_HINT}"
        except httpx.HTTPError:
            # Errori non di trasporto (per esempio corpo non decodificabile): può mancare il codice.
            return f"Errore: risposta non valida dal servizio giorni. {SERVICE_FAILURE_HINT}"
        invalid = (
            f"Errore: risposta non valida dal servizio giorni (HTTP {response.status_code}). "
            f"{SERVICE_FAILURE_HINT}"
        )
        try:
            data = response.json()
        except ValueError:
            return invalid
        if not isinstance(data, dict):
            return invalid
        if response.status_code == 400 and isinstance(data.get("detail"), str):
            return f"Errore: {data['detail']}"
        if response.status_code != 200:
            return invalid
        try:
            return formatter(data)
        except (KeyError, TypeError, ValueError):
            return invalid

    def days_between(end: str, start: str | None = None) -> str:
        params = {"fine": end}
        if start is not None:
            params["inizio"] = start
        return _call("/giorni-tra", params, _format_between)

    def add_days(days: int, start: str | None = None) -> str:
        params = {"giorni": days}
        if start is not None:
            params["data"] = start
        return _call("/aggiungi-giorni", params, _format_add_days)

    def add_business_days(days: int, start: str | None = None) -> str:
        params = {"giorni": days}
        if start is not None:
            params["data"] = start
        return _call("/aggiungi-lavorativi", params, _format_add_business_days)

    def date_info(date: str | None = None) -> str:
        params = {} if date is None else {"data": date}
        return _call("/info-data", params, _format_info)

    return [
        tool("days_between", description=DAYS_BETWEEN_DESCRIPTION)(days_between),
        tool("add_days", description=ADD_DAYS_DESCRIPTION)(add_days),
        tool("add_business_days", description=ADD_BUSINESS_DAYS_DESCRIPTION)(add_business_days),
        tool("date_info", description=DATE_INFO_DESCRIPTION)(date_info),
    ]
