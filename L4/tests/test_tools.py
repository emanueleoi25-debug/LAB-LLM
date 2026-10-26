import json
from datetime import datetime, timezone

import pytest
from langchain_core.utils.function_calling import convert_to_openai_tool

from assistente.tools import current_time, make_clock_tool

NOW = datetime(2026, 10, 26, 16, 5, tzinfo=timezone.utc)
TOKYO = "2026-10-27T01:05:00+09:00 (Asia/Tokyo)"
ROME = "2026-10-26T17:05:00+01:00 (Europe/Rome)"


def test_time_in_requested_zone():
    assert current_time("Asia/Tokyo", "Europe/Rome", NOW) == TOKYO


@pytest.mark.parametrize("tz", [None, "", "   "])
def test_missing_zone_uses_default(tz):
    assert current_time(tz, "Europe/Rome", NOW) == ROME


def test_zone_name_is_case_and_space_insensitive():
    assert current_time(" asia/tokyo ", "Europe/Rome", NOW) == TOKYO


@pytest.mark.parametrize("tz", ["Marte/Base", "../etc/passwd"])
def test_unknown_zone_returns_error_text(tz):
    assert current_time(tz, "Europe/Rome", NOW) == (
        f"Errore: fuso orario sconosciuto '{tz}'. Usa un nome IANA come 'Europe/Rome'."
    )


def test_tool_uses_injected_clock():
    tool = make_clock_tool("Europe/Rome", clock=lambda: NOW)
    assert tool.invoke({"timezone": "Asia/Tokyo"}) == TOKYO
    assert tool.invoke({}) == ROME


def test_tool_schema():
    fn = convert_to_openai_tool(make_clock_tool("Europe/Rome"))["function"]
    assert fn["name"] == "get_current_time"
    prop = fn["parameters"]["properties"]["timezone"]
    assert "timezone" not in fn["parameters"].get("required", [])
    assert "string" in json.dumps(prop)
