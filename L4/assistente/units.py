"""Tabella chiusa delle unità di misura e conversione affine verso l'unità base."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Unit:
    """Unità di misura: `base = valore × scale + offset` nella categoria."""

    symbol: str
    category: str
    scale: float
    offset: float = 0.0
    aliases: tuple[str, ...] = ()


UNITS: tuple[Unit, ...] = (
    # Lunghezza (base: m)
    Unit("mm", "lunghezza", 0.001, aliases=(
        "millimetro", "millimetri", "millimeter", "millimeters", "millimetre", "millimetres")),
    Unit("cm", "lunghezza", 0.01, aliases=(
        "centimetro", "centimetri", "centimeter", "centimeters", "centimetre", "centimetres")),
    Unit("m", "lunghezza", 1, aliases=("metro", "metri", "meter", "meters", "metre", "metres")),
    Unit("km", "lunghezza", 1000, aliases=(
        "chilometro", "chilometri", "kilometro", "kilometri",
        "kilometer", "kilometers", "kilometre", "kilometres")),
    Unit("in", "lunghezza", 0.0254, aliases=("pollice", "pollici", "inch", "inches")),
    Unit("ft", "lunghezza", 0.3048, aliases=("piede", "piedi", "foot", "feet")),
    Unit("yd", "lunghezza", 0.9144, aliases=("iarda", "iarde", "yard", "yards")),
    Unit("mi", "lunghezza", 1609.344, aliases=("miglio", "miglia", "mile", "miles")),
    # Massa (base: kg)
    Unit("mg", "massa", 0.000001, aliases=("milligrammo", "milligrammi", "milligram", "milligrams")),
    Unit("g", "massa", 0.001, aliases=("grammo", "grammi", "gram", "grams")),
    Unit("kg", "massa", 1, aliases=(
        "chilogrammo", "chilogrammi", "chilo", "chili", "kilogrammo", "kilogrammi",
        "kilo", "kilogram", "kilograms")),
    Unit("t", "massa", 1000, aliases=("tonnellata", "tonnellate", "tonne", "tonnes")),
    Unit("oz", "massa", 0.028349523125, aliases=("oncia", "once", "ounce", "ounces")),
    Unit("lb", "massa", 0.45359237, aliases=("libbra", "libbre", "pound", "pounds", "lbs")),
    # Volume (base: l)
    Unit("ml", "volume", 0.001, aliases=(
        "millilitro", "millilitri", "milliliter", "milliliters", "millilitre", "millilitres")),
    Unit("cl", "volume", 0.01, aliases=(
        "centilitro", "centilitri", "centiliter", "centiliters", "centilitre", "centilitres")),
    Unit("l", "volume", 1, aliases=("litro", "litri", "liter", "liters", "litre", "litres")),
    Unit("m³", "volume", 1000, aliases=(
        "m3", "mc", "metro cubo", "metri cubi",
        "cubic meter", "cubic meters", "cubic metre", "cubic metres")),
    Unit("gal", "volume", 3.785411784, aliases=("gallone", "galloni", "gallon", "gallons")),
    Unit("fl oz", "volume", 0.0295735295625, aliases=(
        "floz", "oncia fluida", "once fluide", "fluid ounce", "fluid ounces")),
    # Temperatura (base: K)
    Unit("°C", "temperatura", 1, 273.15, aliases=(
        "c", "celsius", "grado celsius", "gradi celsius", "centigradi")),
    Unit("°F", "temperatura", 5 / 9, 273.15 - 32 * 5 / 9, aliases=(
        "f", "fahrenheit", "grado fahrenheit", "gradi fahrenheit")),
    Unit("K", "temperatura", 1, aliases=("kelvin",)),
    # Velocità (base: m/s)
    Unit("m/s", "velocità", 1, aliases=(
        "mps", "metro al secondo", "metri al secondo", "meters per second", "metres per second")),
    Unit("km/h", "velocità", 1 / 3.6, aliases=(
        "kmh", "kph", "km/ora", "chilometri orari", "chilometri all'ora",
        "kilometers per hour", "kilometres per hour")),
    Unit("mph", "velocità", 0.44704, aliases=("miglia orarie", "miglia all'ora", "miles per hour")),
    Unit("kn", "velocità", 1852 / 3600, aliases=("nodo", "nodi", "knot", "knots", "kt")),
    # Tempo (base: s)
    Unit("s", "tempo", 1, aliases=("sec", "secondo", "secondi", "second", "seconds")),
    Unit("min", "tempo", 60, aliases=("minuto", "minuti", "minute", "minutes")),
    Unit("h", "tempo", 3600, aliases=("hr", "ora", "ore", "hour", "hours")),
    Unit("d", "tempo", 86400, aliases=("giorno", "giorni", "day", "days")),
    Unit("wk", "tempo", 604800, aliases=("settimana", "settimane", "week", "weeks")),
)


def _normalize(name: str) -> str:
    """Minuscole, spazi compattati, `º` → `°`, `° C` → `°c`, senza punto finale."""
    text = " ".join(name.replace("º", "°").casefold().split())
    return text.replace("° ", "°").rstrip(".")


_BY_NAME: dict[str, Unit] = {
    _normalize(name): unit for unit in UNITS for name in (unit.symbol, *unit.aliases)
}


def find_unit(name: str) -> Unit | None:
    """Unità con quel simbolo o sinonimo; None se il nome è vuoto o sconosciuto."""
    return _BY_NAME.get(_normalize(name))


def to_base(unit: Unit, value: float) -> float:
    return value * unit.scale + unit.offset


def from_base(unit: Unit, base: float) -> float:
    return (base - unit.offset) / unit.scale
