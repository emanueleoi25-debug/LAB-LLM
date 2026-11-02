import json
from datetime import datetime, timezone

import pytest
from langchain_core.utils.function_calling import convert_to_openai_tool

from assistente.tools import current_time, make_clock_tool

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
