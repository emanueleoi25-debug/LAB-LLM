import json
from datetime import datetime, timezone

import pytest
from langchain_core.utils.function_calling import convert_to_openai_tool

from assistente.tools import convert_units, current_time, make_clock_tool, make_converter_tool

NOW = datetime(2026, 10, 26, 16, 5, tzinfo=timezone.utc)
MIAMI = "2026-10-26T12:05:00-04:00 (Miami, US, fuso America/New_York)"
TOKYO_IANA = "2026-10-27T01:05:00+09:00 (fuso Asia/Tokyo)"
ROME_DEFAULT = "2026-10-26T17:05:00+01:00 (fuso predefinito Europe/Rome)"


def test_time_in_city():
    assert current_time("Miami", "Europe/Rome", NOW) == MIAMI


@pytest.mark.parametrize("city", ["Asia/Tokyo", " asia/tokyo "])
def test_iana_name_is_accepted(city):
    assert current_time(city, "Europe/Rome", NOW) == TOKYO_IANA


@pytest.mark.parametrize("city", [None, "", "   "])
def test_missing_city_uses_default(city):
    assert current_time(city, "Europe/Rome", NOW) == ROME_DEFAULT


@pytest.mark.parametrize("city", ["Xyzville", "../etc/passwd"])
def test_unknown_city_returns_error_text(city):
    assert current_time(city, "Europe/Rome", NOW) == (
        f"Errore: città sconosciuta '{city}'. Indica il nome di una città, ad esempio 'Roma'."
    )


def test_tool_uses_injected_clock():
    tool = make_clock_tool("Europe/Rome", clock=lambda: NOW)
    assert tool.invoke({"city": "Miami"}) == MIAMI
    assert tool.invoke({}) == ROME_DEFAULT


def test_old_timezone_argument_falls_back_to_default():
    tool = make_clock_tool("Europe/Rome", clock=lambda: NOW)
    assert tool.invoke({"timezone": "Asia/Tokyo"}) == ROME_DEFAULT


def test_tool_schema():
    fn = convert_to_openai_tool(make_clock_tool("Europe/Rome"))["function"]
    assert fn["name"] == "get_current_time"
    properties = fn["parameters"]["properties"]
    assert set(properties) == {"city"}
    assert "city" not in fn["parameters"].get("required", [])
    assert "string" in json.dumps(properties["city"])


ALLOWED = ("lunghezza (mm, cm, m, km, in, ft, yd, mi); massa (mg, g, kg, t, oz, lb); "
           "volume (ml, cl, l, m³, gal, fl oz); temperatura (°C, °F, K); "
           "velocità (m/s, km/h, mph, kn); tempo (s, min, h, d, wk).")


@pytest.mark.parametrize("value, src, dst, expected", [
    (10, "mi", "km", "10 mi = 16.09 km (lunghezza)"),
    (2.5, "miglia", "Chilometri", "2.5 mi = 4.02 km (lunghezza)"),
    (100, "°C", "°F", "100 °C = 212.00 °F (temperatura)"),
    (-40, "c", "f", "-40 °C = -40.00 °F (temperatura)"),
    (-459.67, "°F", "K", "-459.67 °F = 0.00 K (temperatura)"),
    (5, "mg", "kg", "5 mg = 0.0000050 kg (massa)"),
    (-5, "mg", "kg", "-5 mg = -0.0000050 kg (massa)"),
    (1e-7, "km", "mm", "0.0000001 km = 0.10 mm (lunghezza)"),
    (0, "km", "m", "0 km = 0.00 m (lunghezza)"),
    (-0.0, "m", "km", "0 m = 0.00 km (lunghezza)"),
    (10.0, "km", "km", "10 km = 10.00 km (lunghezza)"),
    (1, "wk", "h", "1 wk = 168.00 h (tempo)"),
])
def test_convert_units(value, src, dst, expected):
    assert convert_units(value, src, dst) == expected


def test_unknown_unit_lists_allowed_units():
    assert convert_units(1, "parsec", "km") == f"Errore: unità sconosciuta 'parsec'. Unità ammesse: {ALLOWED}"
    assert convert_units(1, "km", "parsec") == f"Errore: unità sconosciuta 'parsec'. Unità ammesse: {ALLOWED}"


@pytest.mark.parametrize("src, dst, expected", [
    ("km", "kg", "Errore: unità incompatibili: 'km' è una lunghezza, 'kg' è una massa."),
    ("litri", "ore", "Errore: unità incompatibili: 'l' è un volume, 'h' è un tempo."),
])
def test_incompatible_units(src, dst, expected):
    assert convert_units(5, src, dst) == expected


def test_below_absolute_zero():
    assert convert_units(-300, "°C", "K") == "Errore: -300 °C è sotto lo zero assoluto."
    assert convert_units(-1, "kelvin", "°C") == "Errore: -1 K è sotto lo zero assoluto."


@pytest.mark.parametrize("value", [float("inf"), float("-inf"), float("nan")])
def test_non_finite_value(value):
    assert convert_units(value, "m", "km") == "Errore: il valore deve essere un numero finito."


def test_result_too_large():
    assert convert_units(1e308, "km", "mm") == "Errore: il risultato è troppo grande per essere rappresentato."


def test_converter_tool_accepts_numeric_string():
    tool = make_converter_tool()
    assert tool.invoke({"value": "10", "from_unit": "mi", "to_unit": "km"}) == "10 mi = 16.09 km (lunghezza)"


def test_converter_tool_schema():
    fn = convert_to_openai_tool(make_converter_tool())["function"]
    assert fn["name"] == "convert_units"
    properties = fn["parameters"]["properties"]
    assert set(properties) == {"value", "from_unit", "to_unit"}
    assert set(fn["parameters"]["required"]) == {"value", "from_unit", "to_unit"}
    assert "number" in json.dumps(properties["value"])
