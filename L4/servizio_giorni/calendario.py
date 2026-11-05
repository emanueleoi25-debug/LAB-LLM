"""Calendario: festività nazionali italiane, analisi delle date, conteggi e scadenze.

Logica pura, senza FastAPI e senza orologio: «oggi» arriva sempre come parametro. Gli errori
dovuti ai dati dell'utente sono `DateError`, il cui messaggio è il `detail` della risposta 400;
un file delle festività non valido solleva invece `ValueError`.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

HOLIDAYS_FILE = Path(__file__).with_name("festivita.json")

MIN_YEAR = 1900
MAX_YEAR = 2100
MAX_DAYS = 36500
MAX_BUSINESS_DAYS = 366

_WEEKDAYS = ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica")
_FULL_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})", re.ASCII)
_MONTH_DAY = re.compile(r"(\d{2})-(\d{2})", re.ASCII)
_MOVABLE_NAMES = ["Pasqua", "Lunedì dell'Angelo"]
# Anno bisestile di appoggio per verificare i giorni `MM-GG` (consente il 29 febbraio).
_LEAP_YEAR = 2000


class DateError(Exception):
    """Dati dell'utente non validi; `str(exc)` è il testo del `detail` (senza `Errore:`)."""


@dataclass(frozen=True)
class Holidays:
    """Festività dal file, per gli anni da `first_year` a `last_year` compresi."""

    first_year: int
    last_year: int
    _names: dict[date, str] = field(default_factory=dict, repr=False, compare=False)

    def covers(self, day: date) -> bool:
        return self.first_year <= day.year <= self.last_year

    def name(self, day: date) -> str | None:
        """Nome della festività, `None` se il giorno non lo è (o è fuori dagli anni del file)."""
        return self._names.get(day)


@dataclass(frozen=True)
class DateInfo:
    holiday: str | None
    weekend: bool
    working: bool | None  # None se la data è fuori dagli anni del file


def load_holidays(path: Path = HOLIDAYS_FILE) -> Holidays:
    """Legge e valida il file delle festività; se non è valido solleva `ValueError`."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return _build_holidays(data)
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f"file delle festività non valido: struttura inattesa ({exc!r})") from exc


def _build_holidays(data: dict) -> Holidays:
    first, last = data["anni"]
    if not (isinstance(first, int) and isinstance(last, int) and first <= last):
        raise ValueError(f"file delle festività non valido: anni {data['anni']!r}")
    names: dict[date, str] = {}
    for item in data["fisse"]:
        month_day, name, since = item["giorno"], item["nome"], item["dal"]
        match = _MONTH_DAY.fullmatch(month_day)
        try:
            month, day = (int(part) for part in match.groups())
            date(_LEAP_YEAR, month, day)
        except (AttributeError, ValueError):
            raise ValueError(f"file delle festività non valido: giorno {month_day!r}") from None
        for year in range(max(first, since), last + 1):
            try:
                names[date(year, month, day)] = name
            except ValueError:  # 29 febbraio in un anno non bisestile
                continue
    mobili = data["mobili"]
    if sorted(mobili) != [str(year) for year in range(first, last + 1)]:
        raise ValueError("file delle festività non valido: anni delle festività mobili")
    for year in range(first, last + 1):
        items = mobili[str(year)]
        if [item["nome"] for item in items] != _MOVABLE_NAMES:
            raise ValueError(f"file delle festività non valido: mobili del {year}")
        for item in items:
            try:
                day = date.fromisoformat(item["data"])
            except ValueError:
                raise ValueError(f"file delle festività non valido: data {item['data']!r}") from None
            if day.year != year:
                raise ValueError(f"file delle festività non valido: {item['data']} non è del {year}")
            names[day] = item["nome"]  # le mobili prevalgono sulle fisse nello stesso giorno
    return Holidays(first, last, names)


def _check_year(year: int) -> None:
    if not MIN_YEAR <= year <= MAX_YEAR:
        raise DateError(f"anno {year} fuori intervallo: ammessi {MIN_YEAR}-{MAX_YEAR}.")


def _invalid(text: str, formats: str) -> DateError:
    return DateError(f"data non valida '{text}'. Usa {formats}.")


def _parse_full(text: str, formats: str) -> date:
    match = _FULL_DATE.fullmatch(text)
    if match is None:
        raise _invalid(text, formats)
    try:
        day = date(*(int(part) for part in match.groups()))
    except ValueError:
        raise _invalid(text, formats) from None
    _check_year(day.year)
    return day


def parse_today(text: str) -> date:
    """Interpreta il parametro `oggi`, solo `AAAA-MM-GG`."""
    return _parse_full(text.strip(), "AAAA-MM-GG")


def parse_date(text: str, reference: date) -> date:
    """`AAAA-MM-GG`, oppure `MM-GG` = prossima occorrenza da `reference` (incluso)."""
    text = text.strip()
    match = _MONTH_DAY.fullmatch(text)
    if match is None:
        return _parse_full(text, "AAAA-MM-GG o MM-GG")
    month, day = (int(part) for part in match.groups())
    try:
        date(_LEAP_YEAR, month, day)
    except ValueError:
        raise _invalid(text, "AAAA-MM-GG o MM-GG") from None
    year = reference.year
    while True:
        try:
            resolved = date(year, month, day)
        except ValueError:  # 29 febbraio in un anno non bisestile
            resolved = None
        if resolved is not None and resolved >= reference:
            break
        year += 1
    _check_year(resolved.year)
    return resolved


def weekday_name(day: date) -> str:
    return _WEEKDAYS[day.weekday()]


def is_working_day(day: date, holidays: Holidays) -> bool:
    """Lunedì-venerdì e non festività (fuori dagli anni del file le festività non si conoscono)."""
    return day.weekday() < 5 and holidays.name(day) is None


def _count_working(after: date, until: date, holidays: Holidays) -> int:
    """Giorni lavorativi `d` con `after < d <= until`."""
    return sum(
        is_working_day(after + timedelta(days=offset), holidays)
        for offset in range(1, (until - after).days + 1)
    )


def days_between(start: date, end: date, holidays: Holidays) -> tuple[int, int | None]:
    """Giorni di calendario e lavorativi da `start` a `end`, con segno.

    I lavorativi sono `None` se una delle due date è fuori dagli anni del file.
    """
    calendar = (end - start).days
    if not (holidays.covers(start) and holidays.covers(end)):
        return calendar, None
    if end >= start:
        return calendar, _count_working(start, end, holidays)
    return calendar, -_count_working(end, start, holidays)


def add_days(start: date, days: int) -> date:
    if abs(days) > MAX_DAYS:
        raise DateError(f"il numero di giorni deve essere compreso tra -{MAX_DAYS} e {MAX_DAYS}.")
    result = start + timedelta(days=days)
    _check_year(result.year)
    return result


def add_business_days(
    start: date, days: int, holidays: Holidays
) -> tuple[date, list[tuple[date, str]]]:
    """L'`days`-esimo giorno lavorativo dopo (o prima, se negativo) `start`, esclusa la partenza.

    Restituisce anche le festività di lunedì-venerdì attraversate, in ordine di data.
    """
    if days == 0 or abs(days) > MAX_BUSINESS_DAYS:
        raise DateError(
            "il numero di giorni lavorativi deve essere diverso da 0 e compreso tra "
            f"-{MAX_BUSINESS_DAYS} e {MAX_BUSINESS_DAYS}."
        )
    unavailable = DateError(
        "giorni lavorativi e festività disponibili solo per gli anni "
        f"{holidays.first_year}-{holidays.last_year}."
    )
    if not holidays.covers(start):
        raise unavailable
    step = timedelta(days=1 if days > 0 else -1)
    current, remaining = start, abs(days)
    skipped: list[tuple[date, str]] = []
    while remaining:
        current += step
        if not holidays.covers(current):
            raise unavailable
        if is_working_day(current, holidays):
            remaining -= 1
        elif current.weekday() < 5:  # giorno feriale non lavorativo = festività
            skipped.append((current, holidays.name(current)))
    return current, sorted(skipped)


def date_info(day: date, holidays: Holidays) -> DateInfo:
    weekend = day.weekday() >= 5
    working = is_working_day(day, holidays) if holidays.covers(day) else None
    return DateInfo(holidays.name(day), weekend, working)
