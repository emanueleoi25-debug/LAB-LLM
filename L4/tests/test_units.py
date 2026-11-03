import pytest

from assistente.units import UNITS, _normalize, find_unit, from_base, to_base

CATEGORIES = ["lunghezza", "massa", "volume", "temperatura", "velocità", "tempo"]


@pytest.mark.parametrize("name, symbol", [
    ("km", "km"), ("Chilometri", "km"), ("  MIGLIA ", "mi"), ("°c", "°C"), ("celsius", "°C"),
    ("K", "K"), ("kelvin", "K"), ("fl oz", "fl oz"), ("oz", "oz"), ("m3", "m³"), ("nodi", "kn"),
    ("settimane", "wk"), ("km/h", "km/h"), ("chilometri all'ora", "km/h"),
    ("ºC", "°C"), ("° C", "°C"), ("lb.", "lb"), ("Chilometri  All'Ora", "km/h"),
])
def test_find_unit(name, symbol):
    assert find_unit(name).symbol == symbol


@pytest.mark.parametrize("name", ["parsec", "", "   "])
def test_unknown_unit_is_none(name):
    assert find_unit(name) is None


def test_names_are_unique():
    names = [_normalize(n) for unit in UNITS for n in (unit.symbol, *unit.aliases)]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    assert duplicates == []


def test_categories_in_order():
    seen = list(dict.fromkeys(unit.category for unit in UNITS))
    assert seen == CATEGORIES


def test_one_base_unit_per_category():
    for category in CATEGORIES:
        bases = [u.symbol for u in UNITS if u.category == category and u.scale == 1 and u.offset == 0]
        assert len(bases) == 1, (category, bases)


@pytest.mark.parametrize("value, src, dst, expected", [
    (1, "mi", "km", 1.609344), (1, "lb", "kg", 0.45359237), (1, "gal", "l", 3.785411784),
    (100, "°C", "°F", 212), (0, "K", "°C", -273.15), (1, "kn", "km/h", 1.852), (1, "wk", "h", 168),
    (-459.67, "°F", "K", 0),
])
def test_reference_conversions(value, src, dst, expected):
    base = to_base(find_unit(src), value)
    assert from_base(find_unit(dst), base) == pytest.approx(expected, abs=1e-9)
