"""Strumenti che il modello può richiedere: orologio, convertitore di unità e calcolatrice."""

import functools
import math
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo, available_timezones

from langchain_core.tools import BaseTool, tool

from assistente.arithmetic import CalcError, Problem, evaluate
from assistente.cities import find_city
from assistente.units import UNITS, find_unit, from_base, to_base

CLOCK_DESCRIPTION = (
    "Restituisce la data e l'ora attuali in una città. Parametro city: il nome della città "
    "citata dall'utente, così come l'ha scritta (es. 'Miami', 'Nuova York'). Se l'utente non "
    "nomina una città, omettilo e si usa il fuso predefinito."
)

CONVERTER_DESCRIPTION = (
    "Converte un valore tra due unità di misura della stessa categoria: lunghezza, massa, "
    "volume, temperatura, velocità, tempo. Parametri: value, il numero da convertire; "
    "from_unit e to_unit, il simbolo o il nome dell'unità (es. 'km', 'miglia', '°C', 'libbre')."
)

CALCULATOR_DESCRIPTION = (
    "Calcola un'espressione aritmetica e restituisce il risultato. Operatori: + - * /, "
    "// (divisione intera), % (resto), ^ o ** (potenza), parentesi. Parole: 'per' e 'x' "
    "indicano la moltiplicazione (3,5 per 2 → 3.5 * 2), 'diviso' la divisione. Usa il punto "
    "per i decimali: se l'utente scrive 3,5 passa 3.5. Esempi: '(3.5 + 2) * 4', '2^10', "
    "'17 % 5'."
)

_ARTICLES = {
    "lunghezza": "una lunghezza",
    "massa": "una massa",
    "volume": "un volume",
    "temperatura": "una temperatura",
    "velocità": "una velocità",
    "tempo": "un tempo",
}
# Intervallo gestito per valori e risultati diversi da zero (in valore assoluto): dentro
# l'intervallo i numeri si scrivono in poche cifre senza notazione scientifica.
_MIN_ABS = 1e-15
_MAX_ABS = 1e15
# Scarto in kelvin entro cui un valore sotto zero è ancora lo zero assoluto (rumore dei float).
_ABSOLUTE_ZERO_TOLERANCE = 1e-9
_ALLOWED_UNITS = "; ".join(
    f"{category} ({', '.join(u.symbol for u in UNITS if u.category == category)})"
    for category in dict.fromkeys(u.category for u in UNITS)
) + "."


def utc_now() -> datetime:
    return datetime.now(UTC)


@functools.lru_cache(maxsize=1)
def _timezones_by_lower_name() -> dict[str, str]:
    return {name.lower(): name for name in available_timezones()}


def canonical_timezone(name: str) -> str | None:
    """Nome IANA canonico, senza distinguere maiuscole e minuscole; None se sconosciuto.

    Il confronto avviene sull'elenco dei fusi noti, così il risultato non dipende dal file
    system (Windows non distingue le maiuscole, Linux sì).
    """
    name = name.strip()
    by_lower = _timezones_by_lower_name()
    if name in by_lower.values():
        return name
    return by_lower.get(name.lower())


def current_time(city: str | None, default_timezone: str, now: datetime) -> str:
    """Istante `now` in ISO 8601, seguito da città e fuso usati.

    `city` può essere un nome di città o un nome IANA; se manca si usa il fuso predefinito.
    """
    if city is None or not city.strip():
        timezone, used = default_timezone, f"fuso predefinito {default_timezone}"
    elif (iana := canonical_timezone(city)) is not None:
        timezone, used = iana, f"fuso {iana}"
    elif (found := find_city(city)) is not None:
        timezone, used = found.timezone, f"{found.name}, {found.country}, fuso {found.timezone}"
    else:
        return f"Errore: città sconosciuta '{city}'. Indica il nome di una città, ad esempio 'Roma'."
    local = now.astimezone(ZoneInfo(timezone))
    return f"{local.isoformat(timespec='seconds')} ({used})"


def make_clock_tool(
    default_timezone: str, clock: Callable[[], datetime] = utc_now
) -> BaseTool:
    """Crea lo strumento `get_current_time` con fuso predefinito e orologio iniettabile."""

    def get_current_time(city: str | None = None) -> str:
        return current_time(city, default_timezone, clock())

    return tool("get_current_time", description=CLOCK_DESCRIPTION)(get_current_time)


def _format_input(value: float) -> str:
    """Valore di partenza in notazione decimale, senza zeri inutili: 10.0 → "10", -0.0 → "0"."""
    text = format(Decimal(repr(value)).normalize(), "f")
    return "0" if text in ("-0", "0") else text


def _format_result(value: float) -> str:
    """Due decimali; 2 cifre significative se il valore diventerebbe 0.00; mai -0.00."""
    if value == 0:
        return "0.00"
    if round(value, 2) == 0:  # 2 cifre significative, senza notazione scientifica
        return f"{value:.{1 - math.floor(math.log10(abs(value)))}f}"
    return f"{value:.2f}"


def convert_units(value: float, from_unit: str, to_unit: str) -> str:
    """Converte `value` da `from_unit` a `to_unit`; un testo `Errore: …` se non si può."""
    if not math.isfinite(value):
        return "Errore: il valore deve essere un numero finito."
    if value != 0 and not _MIN_ABS <= abs(value) <= _MAX_ABS:
        return (
            "Errore: il valore deve essere 0 oppure, in valore assoluto, compreso tra "
            f"{_format_input(_MIN_ABS)} e {_format_input(_MAX_ABS)}."
        )
    src, dst = find_unit(from_unit), find_unit(to_unit)
    for name, unit in ((from_unit, src), (to_unit, dst)):
        if unit is None:
            return f"Errore: unità sconosciuta '{name}'. Unità ammesse: {_ALLOWED_UNITS}"
    if src.category != dst.category:
        return (
            f"Errore: unità incompatibili: '{src.symbol}' è {_ARTICLES[src.category]}, "
            f"'{dst.symbol}' è {_ARTICLES[dst.category]}."
        )
    base = to_base(src, value)
    if src.category == "temperatura":
        if base < -_ABSOLUTE_ZERO_TOLERANCE:
            return f"Errore: {_format_input(value)} {src.symbol} è sotto lo zero assoluto."
        base = max(base, 0.0)  # −459.67 °F dà −2.8e-14 K per il rumore dei float: è lo zero assoluto
    result = from_base(dst, base)
    if abs(result) > _MAX_ABS:
        return "Errore: il risultato è troppo grande per essere rappresentato."
    if result != 0 and abs(result) < _MIN_ABS:
        return "Errore: il risultato è troppo piccolo per essere rappresentato."
    return (
        f"{_format_input(value)} {src.symbol} = {_format_result(result)} {dst.symbol} "
        f"({src.category})"
    )


def make_converter_tool() -> BaseTool:
    """Crea lo strumento `convert_units`."""

    def convert(value: float, from_unit: str, to_unit: str) -> str:
        return convert_units(value, from_unit, to_unit)

    return tool("convert_units", description=CONVERTER_DESCRIPTION)(convert)


_CALC_ERRORS = {
    Problem.EMPTY: "l'espressione è vuota.",
    Problem.TOO_LONG: "l'espressione supera i 200 caratteri.",
    Problem.COMMA: "usa il punto come separatore decimale (es. 3.5), non la virgola.",
    Problem.CHARACTER: (
        "carattere non ammesso '{char}'. Ammessi: cifre, punto decimale, + - * / // % ^ **, "
        "parentesi."
    ),
    Problem.SYNTAX: "espressione non valida. Esempio corretto: '(3.5 + 2) * 4'.",
    Problem.NUMBER_RANGE: (
        "i numeri devono essere 0 oppure, in valore assoluto, compresi tra "
        "0.000000000000001 e 1000000000000000."
    ),
    Problem.DIVISION_BY_ZERO: "divisione per zero.",
    Problem.NOT_REAL: "potenza non reale (base negativa con esponente non intero).",
    Problem.TOO_BIG: "il risultato è troppo grande per essere rappresentato.",
    Problem.TOO_SMALL: "il risultato è troppo piccolo per essere rappresentato.",
}


def _format_number(value: float) -> str:
    """15 cifre significative, senza notazione scientifica né zeri finali; mai -0."""
    if value == 0:
        return "0"
    return format(Decimal(format(value, ".15g")).normalize(), "f")


def calculate(expression: str) -> str:
    """Risultato di `expression` come `<espressione> = <risultato>`; un testo `Errore: …` se non si può."""
    try:
        result = evaluate(expression)
    except CalcError as exc:
        return "Errore: " + _CALC_ERRORS[exc.problem].format(char=exc.char)
    return f"{expression.strip()} = {_format_number(result)}"


def make_calculator_tool() -> BaseTool:
    """Crea lo strumento `calculate`."""

    def calculate_tool(expression: str) -> str:
        return calculate(expression)

    return tool("calculate", description=CALCULATOR_DESCRIPTION)(calculate_tool)
