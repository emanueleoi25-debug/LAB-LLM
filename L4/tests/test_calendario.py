"""Test del calendario: festività, analisi delle date, conteggi e scadenze (senza FastAPI)."""

import json
from datetime import date, timedelta

import pytest

from servizio_giorni.calendario import (
    HOLIDAYS_FILE,
    DateError,
    DateInfo,
    add_business_days,
    add_days,
    date_info,
    days_between,
    is_working_day,
    load_holidays,
    parse_date,
    parse_today,
    weekday_name,
)

TODAY = date(2026, 11, 5)
OUT_OF_RANGE = "anno {} fuori intervallo: ammessi 1900-2100."
DAYS_LIMIT = "il numero di giorni deve essere compreso tra -36500 e 36500."
BUSINESS_LIMIT = "il numero di giorni lavorativi deve essere diverso da 0 e compreso tra -366 e 366."
NO_HOLIDAYS = "giorni lavorativi e festività disponibili solo per gli anni 2020-2040."


@pytest.fixture
def holidays():
    return load_holidays()


def easter(year):  # algoritmo gregoriano anonimo (Meeus/Jones/Butcher), solo nei test
    a, b, c = year % 19, year // 100, year % 100
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


@pytest.mark.parametrize("year", range(2020, 2041))
def test_easter_and_monday_match_algorithm(holidays, year):
    assert holidays.name(easter(year)) == "Pasqua"
    assert holidays.name(easter(year) + timedelta(days=1)) == "Lunedì dell'Angelo"


def test_holidays_cover_file_years(holidays):
    assert (holidays.first_year, holidays.last_year) == (2020, 2040)
    assert holidays.covers(date(2020, 1, 1)) and holidays.covers(date(2040, 12, 31))
    assert not holidays.covers(date(2019, 12, 31)) and not holidays.covers(date(2041, 1, 1))


def test_fixed_holidays(holidays):
    assert holidays.name(date(2027, 6, 2)) == "Festa della Repubblica"
    assert holidays.name(date(2026, 12, 8)) == "Immacolata Concezione"
    assert holidays.name(date(2026, 11, 5)) is None


def test_san_francesco_from_2026(holidays):
    assert holidays.name(date(2025, 10, 4)) is None
    assert holidays.name(date(2026, 10, 4)) == holidays.name(date(2027, 10, 4)) == (
        "San Francesco d'Assisi"
    )
    assert is_working_day(date(2027, 10, 4), holidays) is False  # lunedì


def _write_variant(tmp_path, change):
    data = json.loads(HOLIDAYS_FILE.read_text(encoding="utf-8"))
    change(data)
    path = tmp_path / "festivita.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _missing_year(data):
    del data["mobili"]["2030"]


def _date_outside_year(data):
    data["mobili"]["2030"][0]["data"] = "2031-04-21"


def _impossible_day(data):
    data["fisse"][0]["giorno"] = "02-30"


@pytest.mark.parametrize("change", [_missing_year, _date_outside_year, _impossible_day])
def test_invalid_file_raises(tmp_path, change):
    with pytest.raises(ValueError):
        load_holidays(_write_variant(tmp_path, change))


def test_parse_date(holidays):
    assert parse_date("2026-12-25", TODAY) == date(2026, 12, 25)
    assert parse_date(" 12-25 ", TODAY) == date(2026, 12, 25)
    assert parse_date("11-05", TODAY) == date(2026, 11, 5)  # il riferimento è incluso
    assert parse_date("11-04", TODAY) == date(2027, 11, 4)
    assert parse_date("02-29", TODAY) == date(2028, 2, 29)


@pytest.mark.parametrize(
    "text",
    ["2026-02-30", "2026-2-3", "", "domani", "02-30"],
)
def test_parse_date_errors(text):
    with pytest.raises(DateError) as error:
        parse_date(text, TODAY)
    assert str(error.value) == f"data non valida '{text}'. Usa AAAA-MM-GG o MM-GG."


def test_parse_date_strips_spaces_in_error():
    with pytest.raises(DateError) as error:
        parse_date("  domani ", TODAY)
    assert str(error.value) == "data non valida 'domani'. Usa AAAA-MM-GG o MM-GG."


@pytest.mark.parametrize("text, year", [("1899-12-31", 1899), ("2101-01-01", 2101)])
def test_parse_date_year_out_of_range(text, year):
    with pytest.raises(DateError) as error:
        parse_date(text, TODAY)
    assert str(error.value) == OUT_OF_RANGE.format(year)


def test_parse_today():
    assert parse_today("2026-11-05") == TODAY
    with pytest.raises(DateError) as error:
        parse_today("11-05")
    assert str(error.value) == "data non valida '11-05'. Usa AAAA-MM-GG."


def test_days_between(holidays):
    assert days_between(TODAY, date(2026, 12, 25), holidays) == (50, 34)
    assert days_between(TODAY, TODAY, holidays) == (0, 0)
    assert days_between(date(2026, 12, 25), TODAY, holidays) == (-50, -34)
    assert days_between(date(2019, 1, 1), date(2019, 12, 31), holidays) == (364, None)


def test_add_days():
    assert add_days(TODAY, 30) == date(2026, 12, 5)
    assert add_days(TODAY, -10) == date(2026, 10, 26)
    # il limite di 36500 giorni è accettato (nei limiti degli anni ammessi)
    assert add_days(date(1900, 1, 1), 36500) == date(1900, 1, 1) + timedelta(days=36500)
    assert add_days(date(2100, 12, 31), -36500) == date(2100, 12, 31) - timedelta(days=36500)
    for days in (36501, -36501):
        with pytest.raises(DateError) as error:
            add_days(TODAY, days)
        assert str(error.value) == DAYS_LIMIT
    with pytest.raises(DateError) as error:
        add_days(date(2100, 12, 1), 31)
    assert str(error.value) == OUT_OF_RANGE.format(2101)


def test_add_business_days(holidays):
    assert add_business_days(date(2026, 11, 27), 10, holidays) == (
        date(2026, 12, 14),
        [(date(2026, 12, 8), "Immacolata Concezione")],
    )
    assert add_business_days(date(2026, 11, 7), 1, holidays) == (date(2026, 11, 9), [])
    assert add_business_days(date(2026, 12, 14), -10, holidays) == (
        date(2026, 11, 27),
        [(date(2026, 12, 8), "Immacolata Concezione")],
    )
    # il 4 ottobre 2026 è domenica: non si elenca
    assert add_business_days(date(2026, 10, 2), 1, holidays) == (date(2026, 10, 5), [])


@pytest.mark.parametrize("days", [0, 367, -367])
def test_add_business_days_limits(holidays, days):
    with pytest.raises(DateError) as error:
        add_business_days(TODAY, days, holidays)
    assert str(error.value) == BUSINESS_LIMIT


@pytest.mark.parametrize("start, days", [(date(2040, 12, 28), 5), (date(2019, 12, 31), 1)])
def test_add_business_days_outside_holiday_years(holidays, start, days):
    with pytest.raises(DateError) as error:
        add_business_days(start, days, holidays)
    assert str(error.value) == NO_HOLIDAYS


def test_date_info(holidays):
    assert date_info(date(2027, 6, 2), holidays) == DateInfo("Festa della Repubblica", False, False)
    assert date_info(date(2026, 10, 4), holidays) == DateInfo("San Francesco d'Assisi", True, False)
    assert date_info(date(2026, 11, 7), holidays) == DateInfo(None, True, False)
    assert date_info(date(2026, 11, 5), holidays) == DateInfo(None, False, True)
    assert date_info(date(2019, 6, 2), holidays) == DateInfo(None, True, None)


def test_weekday_name():
    assert weekday_name(date(2026, 11, 5)) == "giovedì"
    assert weekday_name(date(2026, 11, 8)) == "domenica"
