"""App FastAPI del servizio giorni: strato sottile sopra `calendario`.

«Oggi» arriva sempre nel parametro `oggi`: il servizio non legge mai l'orologio. Gli errori
dovuti ai dati dell'utente diventano risposte 400 con `{"detail": ...}`.
"""

from datetime import date

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from servizio_giorni import calendario
from servizio_giorni.calendario import DateError

HOLIDAYS = calendario.load_holidays()  # se il file non è valido il servizio non parte

app = FastAPI(title="Servizio giorni e scadenze")


@app.exception_handler(DateError)
def date_error_handler(request: Request, exc: DateError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(RequestValidationError)
def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    name = exc.errors()[0]["loc"][-1]
    return JSONResponse(
        status_code=400, content={"detail": f"parametro '{name}' mancante o non valido."}
    )


def _start_date(today_text: str, start_text: str | None) -> date:
    """Controlla `oggi`, poi risolve la data di partenza (senza partenza vale oggi)."""
    today = calendario.parse_today(today_text)
    return today if start_text is None else calendario.parse_date(start_text, today)


@app.get("/giorni-tra")
def giorni_tra(oggi: str, fine: str, inizio: str | None = None) -> dict:
    start = _start_date(oggi, inizio)
    end = calendario.parse_date(fine, start)
    days, working = calendario.days_between(start, end, HOLIDAYS)
    return {
        "inizio": start.isoformat(),
        "fine": end.isoformat(),
        "giorno_inizio": calendario.weekday_name(start),
        "giorno_fine": calendario.weekday_name(end),
        "giorni": days,
        "lavorativi": working,
    }


@app.get("/aggiungi-giorni")
def aggiungi_giorni(oggi: str, giorni: int, data: str | None = None) -> dict:
    start = _start_date(oggi, data)
    result = calendario.add_days(start, giorni)
    return {
        "data": start.isoformat(),
        "giorno_data": calendario.weekday_name(start),
        "giorni": giorni,
        "risultato": result.isoformat(),
        "giorno_risultato": calendario.weekday_name(result),
    }


@app.get("/aggiungi-lavorativi")
def aggiungi_lavorativi(oggi: str, giorni: int, data: str | None = None) -> dict:
    start = _start_date(oggi, data)
    result, skipped = calendario.add_business_days(start, giorni, HOLIDAYS)
    return {
        "data": start.isoformat(),
        "giorno_data": calendario.weekday_name(start),
        "giorni": giorni,
        "risultato": result.isoformat(),
        "giorno_risultato": calendario.weekday_name(result),
        "festivita_saltate": [{"data": day.isoformat(), "nome": name} for day, name in skipped],
    }


@app.get("/info-data")
def info_data(oggi: str, data: str | None = None) -> dict:
    day = _start_date(oggi, data)
    info = calendario.date_info(day, HOLIDAYS)
    return {
        "data": day.isoformat(),
        "giorno": calendario.weekday_name(day),
        "festivita": info.holiday,
        "fine_settimana": info.weekend,
        "lavorativo": info.working,
    }


@app.get("/salute")
def salute() -> dict:
    return {"stato": "ok", "anni_festivita": [HOLIDAYS.first_year, HOLIDAYS.last_year]}
