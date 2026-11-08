# Giorni e scadenze — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** il modello può contare giorni tra date, calcolare scadenze in giorni di calendario o
lavorativi e chiedere informazioni su una data tramite quattro strumenti che chiamano il servizio
FastAPI `servizio_giorni`.

**Architecture:** `servizio_giorni/calendario.py` contiene la logica pura sulle date e le festività
lette da `festivita.json`; `servizio_giorni/app.py` la espone con cinque endpoint `GET`.
`assistente/dates.py` crea quattro strumenti client (`httpx` sincrono) che calcolano «oggi» nel
fuso predefinito, chiamano il servizio e trasformano il JSON in testo. `config.py` legge
`GIORNI_BASE_URL`, `cli.py` registra gli strumenti, Compose aggiunge il servizio `giorni`.

**Tech Stack:** Python 3.13 (venv) e 3.14 (Docker), FastAPI 0.159.1, uvicorn 0.54.0, httpx 0.28.1,
LangGraph, langchain-core, pytest.

**Spec:** `L4/docs/superpowers/specs/2026-11-05-giorni-scadenze-design.md` (approvata il 2026-11-05).

Tutti i comandi si eseguono da `Es.1/L4` in PowerShell con il venv attivo
(`.\.venv\Scripts\Activate.ps1`); in Git Bash `./.venv/Scripts/python.exe -m pytest`.

## Global Constraints

- Branch `feat/giorni-scadenze`; lavorare solo in `Es.1/L4` (più `Es.1/plan.md`, versionato:
  le sue modifiche vanno in un commit `docs:`). Merge in `dev` solo dopo l'ok dell'utente; push
  solo su richiesta, dopo la verifica completa rieseguita.
- Dipendenze nuove solo `fastapi==0.159.1`, `uvicorn==0.54.0`, `httpx==0.28.1`, in
  `requirements.txt`. Nessun'altra.
- `servizio_giorni/` non importa nulla da `assistente/`; `calendario.py` non importa FastAPI.
- Il servizio non legge mai l'orologio: «oggi» arriva sempre nel parametro `oggi`.
- Testi esatti (descrizioni, prompt, successi, errori) come nella spec §2 e §4, copiati alla
  lettera.
- Limiti: anni 1900-2100; festività 2020-2040 (dal file); `giorni` ±36500; lavorativi ±366 e
  diverso da 0; timeout del client 5 secondi.
- `graph.py`, `model.py`, `units.py`, `arithmetic.py`, `cities.py` invariati.
- `make_date_tools` chiama `clock` il parametro dell'orologio, come `make_clock_tool` (la spec §5
  scrive `now_fn`: stesso significato, nome allineato al codice esistente); aggiunge `transport`
  solo per i test.
- Suite senza modello verde su 3.13 e 3.14 prima di ogni commit di codice. Nessun test della suite
  usa la rete (servizio via `TestClient`, client via `httpx.MockTransport`).
- Prove reali solo con `google/gemma-4-e2b`.
- Conventional Commits in italiano; `git status`, controllo del diff, staging selettivo; firma
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Mai `.env` nei commit.

## Review Focus

- `MM-GG` di oggi: «Quanti giorni mancano al 5 novembre?» detto il 5 novembre deve dare 0, non 365
  (riferimento incluso) (Task 1).
- `oggi` calcolato nel fuso predefinito: alle 23:30 UTC del 31 dicembre a Roma è già il 1° gennaio;
  lo strumento deve passare la data di Roma, non quella UTC (Task 3).
- Festività che cade di sabato o domenica (4 ottobre 2026, domenica): `add_business_days` non la
  elenca tra le festività saltate e il conteggio non cambia (Task 1).
- Il modello passa `days` come stringa (`"30"`) o una data con spazi (` 2026-12-25 `): lo schema
  dello strumento converte o rifiuta, il servizio toglie gli spazi; nessun 500 (Task 1, Task 3).
- Servizio avviato ma che risponde 500 o con un corpo non JSON: testo
  `Errore: risposta non valida dal servizio giorni (HTTP <codice>).`, la chat continua (Task 3).

---

### Task 1: calendario e festività (`servizio_giorni/calendario.py`)

**Files:**
- Create: `servizio_giorni/__init__.py` (vuoto con docstring), `servizio_giorni/calendario.py`,
  `servizio_giorni/festivita.json`
- Test: `tests/test_calendario.py`

**Interfaces:**
- Produces (usate dal Task 2):
  - `class DateError(Exception)`: il messaggio (`str(exc)`) è il `detail` della spec §4, senza
    `Errore:`.
  - `@dataclass(frozen=True) class Holidays`: `first_year: int`, `last_year: int`, metodi
    `covers(day: date) -> bool` e `name(day: date) -> str | None`.
  - `load_holidays(path: Path = HOLIDAYS_FILE) -> Holidays`; file non valido → `ValueError` con il
    motivo.
  - `parse_today(text: str) -> date`; `parse_date(text: str, reference: date) -> date`.
  - `weekday_name(day: date) -> str` (`"lunedì"` … `"domenica"`).
  - `is_working_day(day: date, holidays: Holidays) -> bool`.
  - `days_between(start: date, end: date, holidays: Holidays) -> tuple[int, int | None]`.
  - `add_days(start: date, days: int) -> date`.
  - `add_business_days(start: date, days: int, holidays: Holidays) -> tuple[date, list[tuple[date, str]]]`.
  - `date_info(day: date, holidays: Holidays) -> DateInfo` con
    `@dataclass(frozen=True) class DateInfo: holiday: str | None; weekend: bool; working: bool | None`.
  - Costanti: `MIN_YEAR = 1900`, `MAX_YEAR = 2100`, `MAX_DAYS = 36500`, `MAX_BUSINESS_DAYS = 366`.

- [ ] **Step 1: scrivere `festivita.json`** come nella spec §3.2: `"anni": [2020, 2040]`, le 11
  fisse con `dal` (2026 solo per `10-04` «San Francesco d'Assisi», 2020 per le altre), `"mobili"`
  con le chiavi `"2020"` … `"2040"`, ciascuna con Pasqua e «Lunedì dell'Angelo». Le date di Pasqua
  si prendono dall'algoritmo del test (Step 2), non a memoria.

- [ ] **Step 2: scrivere i test** in `tests/test_calendario.py` (fixture `holidays =
  load_holidays()` e `TODAY = date(2026, 11, 5)`):

```python
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
```

  Altri test, con asserzioni esatte:
  - `test_fixed_holidays`: `name(date(2027, 6, 2)) == "Festa della Repubblica"`,
    `name(date(2026, 12, 8)) == "Immacolata Concezione"`, `name(date(2026, 11, 5)) is None`.
  - `test_san_francesco_from_2026`: `name(date(2025, 10, 4)) is None`,
    `name(date(2026, 10, 4)) == name(date(2027, 10, 4)) == "San Francesco d'Assisi"`,
    `is_working_day(date(2027, 10, 4), h) is False` (lunedì).
  - `test_invalid_file_raises` (parametrizzato, file in `tmp_path`): anno mancante nelle mobili,
    data mobile fuori dal suo anno, `giorno` `"02-30"` → `pytest.raises(ValueError)`.
  - `test_parse_date`: `"2026-12-25"` → `date(2026,12,25)`; `" 12-25 "` con riferimento TODAY →
    `date(2026,12,25)`; `"11-05"` → `date(2026,11,5)` (riferimento incluso); `"11-04"` →
    `date(2027,11,4)`; `"02-29"` → `date(2028,2,29)`.
  - `test_parse_date_errors` (parametrizzato, messaggio esatto):
    `"2026-02-30"`, `"2026-2-3"`, `""`, `"domani"`, `"02-30"` →
    `"data non valida '<valore>'. Usa AAAA-MM-GG o MM-GG."` (valore senza spazi esterni);
    `"1899-12-31"` → `"anno 1899 fuori intervallo: ammessi 1900-2100."`; `"2101-01-01"` idem con 2101;
    `parse_today("11-05")` → `"data non valida '11-05'. Usa AAAA-MM-GG."`.
  - `test_days_between`: `(TODAY, date(2026,12,25))` → `(50, 34)`; stessa data → `(0, 0)`;
    `(date(2026,12,25), TODAY)` → `(-50, -34)`; `(date(2019,1,1), date(2019,12,31))` → `(364, None)`.
  - `test_add_days`: `+30` → `date(2026,12,5)`; `-10` → `date(2026,10,26)`; `36500` accettato;
    `36501` e `-36501` → `"il numero di giorni deve essere compreso tra -36500 e 36500."`;
    `add_days(date(2100,12,1), 31)` → `"anno 2101 fuori intervallo: ammessi 1900-2100."`.
  - `test_add_business_days`: `(date(2026,11,27), 10)` →
    `(date(2026,12,14), [(date(2026,12,8), "Immacolata Concezione")])`; partenza sabato
    `(date(2026,11,7), 1)` → `(date(2026,11,9), [])`; `(date(2026,12,14), -10)` →
    `(date(2026,11,27), [(date(2026,12,8), "Immacolata Concezione")])`; `(date(2026,10,2), 1)` →
    `(date(2026,10,5), [])` (4 ottobre di domenica non elencato); `0`, `367`, `-367` →
    `"il numero di giorni lavorativi deve essere diverso da 0 e compreso tra -366 e 366."`;
    `(date(2040,12,28), 5)` e `(date(2019,12,31), 1)` →
    `"giorni lavorativi e festività disponibili solo per gli anni 2020-2040."`.
  - `test_date_info`: `2027-06-02` → `DateInfo("Festa della Repubblica", False, False)`;
    `2026-10-04` → `DateInfo("San Francesco d'Assisi", True, False)`; `2026-11-07` →
    `DateInfo(None, True, False)`; `2026-11-05` → `DateInfo(None, False, True)`;
    `2019-06-02` → `DateInfo(None, True, None)`.
  - `test_weekday_name`: `weekday_name(date(2026,11,5)) == "giovedì"`, `date(2026,11,8)` → `"domenica"`.

- [ ] **Step 3:** `python -m pytest tests/test_calendario.py -v` → FAIL per `ModuleNotFoundError:
  servizio_giorni`.

- [ ] **Step 4: implementare `calendario.py`.** Scelte non determinate dai test:
  - formati con `re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text, re.ASCII)` e
    `r"(\d{2})-(\d{2})"` dopo `strip()`; poi `date(...)` dentro `try` → `DateError`;
  - `MM-GG`: anno del riferimento, poi anni successivi finché la data esiste ed è ≥ riferimento;
    controllo dell'anno dopo la risoluzione;
  - lavorativi contati iterando i giorni (al massimo 366 lavorativi o un intervallo di 21 anni:
    costo trascurabile);
  - `festivita_saltate`: festività con `weekday() < 5` attraversate, in ordine di data.

- [ ] **Step 5:** `python -m pytest` → tutto PASS (attesi 261 + i test nuovi, 5 skipped).

- [ ] **Step 6: commit** `feat(servizio): calendario con festività nazionali italiane`
  (`git add servizio_giorni/ tests/test_calendario.py`).

### Task 2: dipendenze e app FastAPI (`servizio_giorni/app.py`)

**Files:**
- Modify: `requirements.txt`
- Create: `servizio_giorni/app.py`
- Test: `tests/test_servizio.py`

**Interfaces:**
- Consumes: tutto il blocco Produces del Task 1.
- Produces: `app: FastAPI` in `servizio_giorni.app`; endpoint, parametri e campi JSON della
  spec §3.3, errori 400 `{"detail": ...}` della spec §4.

- [ ] **Step 1: dipendenze.** Aggiungere a `requirements.txt` `fastapi==0.159.1`,
  `uvicorn==0.54.0`, `httpx==0.28.1`; `python -m pip install -r requirements-dev.txt` → nessun
  errore; `python -c "import fastapi, uvicorn, httpx; print(fastapi.__version__, uvicorn.__version__, httpx.__version__)"`
  → `0.159.1 0.54.0 0.28.1`; `python -m pytest` → stessa conta del Task 1.
- [ ] **Step 2: commit** `build: aggiunge fastapi, uvicorn e httpx` (`git add requirements.txt`).
- [ ] **Step 3: scrivere i test** in `tests/test_servizio.py` con `client = TestClient(app)`;
  `OGGI = "2026-11-05"`:
  - `test_giorni_tra`: `GET /giorni-tra?oggi=2026-11-05&fine=12-25` → 200 e
    `{"inizio": "2026-11-05", "fine": "2026-12-25", "giorno_inizio": "giovedì", "giorno_fine": "venerdì", "giorni": 50, "lavorativi": 34}`.
  - `test_giorni_tra_fuori_file`: `inizio=2019-01-01&fine=2019-12-31` → `"lavorativi": None`.
  - `test_aggiungi_giorni`: `giorni=30` senza `data` → `{"data": "2026-11-05", "giorno_data": "giovedì", "giorni": 30, "risultato": "2026-12-05", "giorno_risultato": "sabato"}`.
  - `test_aggiungi_lavorativi`: `data=2026-11-27&giorni=10` → `risultato` `"2026-12-14"`,
    `festivita_saltate == [{"data": "2026-12-08", "nome": "Immacolata Concezione"}]`.
  - `test_info_data`: `data=2027-06-02` → `{"data": "2027-06-02", "giorno": "mercoledì", "festivita": "Festa della Repubblica", "fine_settimana": False, "lavorativo": False}`.
  - `test_salute`: `GET /salute` → `{"stato": "ok", "anni_festivita": [2020, 2040]}`.
  - `test_errori_400` (parametrizzato, `status_code == 400` e `detail` esatto):
    `/info-data?oggi=2026-11-05&data=02-30` → `"data non valida '02-30'. Usa AAAA-MM-GG o MM-GG."`;
    `/aggiungi-lavorativi?oggi=2026-11-05&giorni=0` → testo lavorativi del §4;
    `/aggiungi-giorni?oggi=2026-11-05&giorni=40000` → testo giorni del §4;
    `/info-data?oggi=11-05` → `"data non valida '11-05'. Usa AAAA-MM-GG."`.
  - `test_validazione_diventa_400`: `/aggiungi-giorni?oggi=2026-11-05&giorni=trenta` → 400,
    `"parametro 'giorni' mancante o non valido."`; `/giorni-tra?oggi=2026-11-05` → 400,
    `"parametro 'fine' mancante o non valido."`.
- [ ] **Step 4:** `python -m pytest tests/test_servizio.py -v` → FAIL (`servizio_giorni.app` assente).
- [ ] **Step 5: implementare `app.py`**: `HOLIDAYS = load_holidays()` all'import; parametri date
  come `str` (`oggi` obbligatorio, `inizio`/`data` `str | None = None`), `giorni: int`; ordine dei
  controlli della spec §4 (`oggi`, partenza, `fine`, `giorni`, risultato); handler di `DateError`
  → `JSONResponse(400, {"detail": str(exc)})`; handler di `RequestValidationError` → 400 con il
  nome preso da `exc.errors()[0]["loc"][-1]`.
- [ ] **Step 6:** `python -m pytest` → tutto PASS. Prova a mano:
  `python -m uvicorn servizio_giorni.app:app --port 8000` e, da un altro terminale,
  `Invoke-RestMethod "http://localhost:8000/info-data?oggi=2026-11-05&data=2027-06-02"` →
  `festivita : Festa della Repubblica`. Fermare il servizio.
- [ ] **Step 7: commit** `feat(servizio): app FastAPI per giorni e scadenze`
  (`git add servizio_giorni/app.py tests/test_servizio.py`).

### Task 3: configurazione e strumenti client (`assistente/dates.py`)

**Files:**
- Modify: `assistente/config.py`, `.env.example`, `tests/test_config.py`
- Create: `assistente/dates.py`
- Test: `tests/test_dates.py`

**Interfaces:**
- Consumes: endpoint e campi JSON del Task 2 (solo via HTTP: `dates.py` non importa
  `servizio_giorni`); `utc_now` da `assistente.tools`.
- Produces:
  - `Settings.giorni_base_url: str = "http://localhost:8000"` (valore predefinito solo per i
    test che costruiscono `Settings` a mano; `load_settings` richiede `GIORNI_BASE_URL`).
  - `make_date_tools(base_url: str, default_timezone: str, clock: Callable[[], datetime] = utc_now, transport: httpx.BaseTransport | None = None) -> list[BaseTool]`,
    nell'ordine `days_between`, `add_days`, `add_business_days`, `date_info`.
  - Costanti `DAYS_BETWEEN_DESCRIPTION`, `ADD_DAYS_DESCRIPTION`, `ADD_BUSINESS_DAYS_DESCRIPTION`,
    `DATE_INFO_DESCRIPTION`, `TIMEOUT = 5.0`.

- [ ] **Step 1: test della configurazione** in `tests/test_config.py`: i dizionari di ambiente dei
  test esistenti che si aspettano successo ricevono `GIORNI_BASE_URL`; nuovo
  `test_missing_giorni_base_url`: senza la variabile → `ConfigError` il cui testo contiene
  `GIORNI_BASE_URL mancante`; nuovo `test_giorni_base_url_is_read`: valore con spazi esterni →
  `settings.giorni_base_url == "http://localhost:8000"`.
- [ ] **Step 2: test degli strumenti** in `tests/test_dates.py`. Aiuto di test: un `MockTransport`
  che registra le richieste e restituisce la risposta preparata; `tools = {t.name: t for t in
  make_date_tools("http://giorni.test", "Europe/Rome", clock=lambda: NOW, transport=...)}` con
  `NOW = datetime(2026, 11, 5, 10, 0, tzinfo=UTC)`.
  - `test_today_in_default_timezone`: con `clock` = 2026-12-31 23:30 UTC la richiesta di
    `date_info` ha `oggi=2027-01-01` e nessun `data`.
  - `test_requests` (parametrizzato): `days_between` `{"end": "12-25"}` → `GET /giorni-tra` con
    `oggi=2026-11-05&fine=12-25` (senza `inizio`); `add_days` `{"days": 30, "start": "2026-11-27"}`
    → `/aggiungi-giorni` con `data=2026-11-27&giorni=30`; `add_business_days` `{"days": -3}` →
    `/aggiungi-lavorativi` con `giorni=-3`; `date_info` `{"date": "2027-06-02"}` → `/info-data`
    con `data=2027-06-02`.
  - `test_success_texts` (parametrizzato): le risposte JSON del Task 2 producono esattamente i
    testi della spec §2: i due di `days_between` (con lavorativi 34 e con `null`), il caso
    negativo `-3 giorni di calendario, -2 giorni lavorativi`, i singolari (`1 giorno di
    calendario, 1 giorno lavorativo`), `add_days` + e - , `add_business_days` con festività, con
    `nessuna festività saltata.` e con due festività separate da `, `, i cinque `date_info`.
  - `test_400_becomes_error_text`: risposta 400 `{"detail": "data non valida '02-30'. Usa AAAA-MM-GG o MM-GG."}`
    → `"Errore: data non valida '02-30'. Usa AAAA-MM-GG o MM-GG."`.
  - `test_unexpected_response` (parametrizzato): 500 con JSON, 200 con corpo `"ciao"` non JSON →
    `"Errore: risposta non valida dal servizio giorni (HTTP 500)."` / `(HTTP 200)`.
  - `test_unreachable` (parametrizzato): il transport solleva `httpx.ConnectError("rifiutata")`
    o `httpx.ReadTimeout("lento")` → `"Errore: servizio giorni non raggiungibile a http://giorni.test."`.
  - `test_schemas`: con `convert_to_openai_tool`, per ogni strumento nome, descrizione uguale
    alla costante e testo esatto della spec §2 (`test_descriptions_are_exact`), parametri
    (`days_between`: `end` obbligatorio, `start` facoltativo; `add_days` e `add_business_days`:
    `days` intero obbligatorio; `date_info`: nessun obbligatorio).
- [ ] **Step 3:** `python -m pytest tests/test_config.py tests/test_dates.py -v` → FAIL
  (`assistente.dates` assente, `GIORNI_BASE_URL` non letto).
- [ ] **Step 4: implementare** `config.py` (variabile obbligatoria, errore raccolto con gli altri)
  e `dates.py`: un `httpx.Client(base_url=..., timeout=TIMEOUT, transport=transport)` creato in
  `make_date_tools`; una funzione `_call(path, params) -> dict | str` che restituisce il JSON o il
  testo d'errore (`httpx.TransportError` → non raggiungibile; 400 con `detail` → `Errore: <detail>`;
  altro o JSON non valido → risposta non valida); funzioni pure di formato per i quattro testi;
  strumenti con `tool(name, description=...)` come in `tools.py`. Aggiungere
  `GIORNI_BASE_URL=http://localhost:8000` (con commento) a `.env.example` e, fuori da Git, al
  `.env` locale.
- [ ] **Step 5:** `python -m pytest` → tutto PASS.
- [ ] **Step 6: commit** `feat(strumenti): strumenti delle date verso il servizio giorni`
  (`git add assistente/config.py assistente/dates.py .env.example tests/test_config.py tests/test_dates.py`).

### Task 4: registrazione nell'agente

**Files:**
- Modify: `assistente/cli.py` (`make_tools`, `SYSTEM_PROMPT`)
- Test: `tests/test_cli.py`, `tests/test_graph.py`

**Interfaces:**
- Consumes: `make_date_tools` e `Settings.giorni_base_url` del Task 3.
- Produces: `make_tools(settings)` con i nomi `["get_current_time", "convert_units", "calculate", "days_between", "add_days", "add_business_days", "date_info"]`.

- [ ] **Step 1: test**: `test_tools_include_all_local_tools` aggiornato ai 7 nomi;
  `test_system_prompt_asks_to_call_tools_anyway` da `endswith` a `in`; nuovo
  `test_system_prompt_mentions_date_tools`: `SYSTEM_PROMPT.endswith(" " + frase della spec §2)`;
  in `tests/test_graph.py` nuovo `test_date_tool_call_returns_service_text`: `ScriptedModel` con
  una chiamata `date_info {"date": "2027-06-02"}` e poi `AIMessage("È festivo.")`, strumenti da
  `make_date_tools(..., transport=MockTransport)` con la risposta JSON del Task 2; il
  `ToolMessage` è `"2027-06-02 (mercoledì): festività, Festa della Repubblica; non lavorativo."`.
- [ ] **Step 2:** `python -m pytest tests/test_cli.py tests/test_graph.py -v` → FAIL sui test nuovi
  e su quello dei 7 nomi.
- [ ] **Step 3: implementare**: `make_tools` aggiunge
  `make_date_tools(settings.giorni_base_url, settings.default_timezone)` dopo la calcolatrice;
  frase in coda a `SYSTEM_PROMPT` preceduta da uno spazio.
- [ ] **Step 4:** `python -m pytest` → tutto PASS.
- [ ] **Step 5: commit** `feat(strumenti): registra gli strumenti delle date nell'agente`
  (`git add assistente/cli.py tests/test_cli.py tests/test_graph.py`).

### Task 5: Docker

**Files:**
- Modify: `Dockerfile`, `compose.yaml`

- [ ] **Step 1:** `Dockerfile`: negli stage `test` e `app` `COPY servizio_giorni/ servizio_giorni/`.
  `compose.yaml`: servizio `giorni` (`build: {context: ., target: app}`, `command: ["python", "-m",
  "uvicorn", "servizio_giorni.app:app", "--host", "0.0.0.0", "--port", "8000"]`, `ports:
  ["127.0.0.1:8000:8000"]`); in `assistente` `depends_on: [giorni]` e
  `GIORNI_BASE_URL: http://giorni:8000` in `environment`.
- [ ] **Step 2:** `docker compose --profile test run --rm --build test` → stessa conta della suite
  locale, 5 skipped, su Python 3.14.9.
- [ ] **Step 3:** `docker compose up -d --build giorni`, poi
  `Invoke-RestMethod "http://localhost:8000/salute"` → `stato : ok`; `docker compose stop giorni`.
- [ ] **Step 4: commit** `build: servizio giorni in Docker Compose` (`git add Dockerfile compose.yaml`).

### Task 6: prove reali e documentazione

**Files:**
- Modify: `tests/integration/test_lmstudio.py`, `README.md`, `docs/registro-test.md`,
  `Es.1/plan.md`; `CLAUDE.md` solo dopo l'ok dell'utente

- [ ] **Step 1: test reale** `test_real_model_uses_date_info` in `tests/integration/test_lmstudio.py`:
  se `GET <GIORNI_BASE_URL>/salute` fallisce → `pytest.fail("servizio giorni non avviato: …")`;
  «Il 2 giugno 2027 è festivo?» → un `ToolMessage` di `date_info` contiene `Festa della Repubblica`.
  Con il servizio avviato: `$env:RUN_LMSTUDIO_TESTS = "1"; python -m pytest -m lmstudio -v` → 6 PASS.
  Commit `test(strumenti): prova reale dello strumento date_info`.
- [ ] **Step 2: serie a mano** della spec §7 con uno script usa e getta nella scratchpad
  (`create_graph` + `ask`, una sessione nuova per tentativo, JSONL con chiamate, argomenti,
  risultati, risposta, chiamata scritta come testo, errore), servizio avviato. Criterio: almeno
  8 su 10 per ciascuna delle quattro domande e per «30 febbraio»; controlli invariati. Esito
  negativo: si riporta, non si corregge senza accordo.
- [ ] **Step 3: servizio spento**: una domanda sulle date con il servizio fermo → `risultato
  strumento: Errore: servizio giorni non raggiungibile a http://localhost:8000.` nei log e la
  chat continua con la domanda successiva.
- [ ] **Step 4: checklist in Docker** (`… | docker compose run --rm -T --build assistente`): la
  checklist precedente più «Quanti giorni mancano a Natale?» e «Il 2 giugno 2027 è festivo?»;
  poi `docker compose stop giorni`.
- [ ] **Step 5: documentazione**: README (servizio e strumenti, avvio in due terminali e in
  Docker, file delle festività, esempi dai log reali, diagnosi della spec §8, solo comandi
  eseguiti in questo piano); `docs/registro-test.md` (sessione con tutte le verifiche); proposta
  all'utente per `CLAUDE.md` (struttura con `servizio_giorni/` e `dates.py`, comando del
  servizio, `GIORNI_BASE_URL`) applicata solo dopo il suo ok; esito in `Es.1/plan.md`. Commit
  `docs: giorni e scadenze nel README e nei registri`.
- [ ] **Step 6:** chiedere all'utente l'ok per il merge in `dev`. Push solo su richiesta, dopo la
  verifica completa rieseguita (suite 3.13 e 3.14, LM Studio, checklist Docker).

---

## Correzioni dopo la revisione finale (aggiunta del 2026-11-05)

Stato: proposta del 2026-11-05, **approvata** dall'utente il 2026-11-06 (esecuzione inline).

Spec §9. Stessi Global Constraints del piano. Suite attuale: 379 passed, 6 skipped.

### Task 7: nessuna eccezione HTTP dagli strumenti (spec §9.1)

**Files:**
- Modify: `assistente/dates.py` (`_call`)
- Test: `tests/test_dates.py`

- [ ] **Step 1: test** `test_http_error_becomes_invalid_response` (parametrizzato sui quattro
  strumenti con argomenti validi): il transport solleva `httpx.DecodingError("corpo illeggibile")`
  → risultato esattamente `"Errore: risposta non valida dal servizio giorni."`.
- [ ] **Step 2:** `python -m pytest tests/test_dates.py -v` → FAIL (l'eccezione esce dallo strumento).
- [ ] **Step 3: implementare**: in `_call`, dopo `except httpx.TransportError` (invariato), un
  `except httpx.HTTPError` → `"Errore: risposta non valida dal servizio giorni."`. La lettura della
  risposta (`response.json()`) resta dentro la gestione già presente. Aggiornare la docstring se
  elenca i casi.
- [ ] **Step 4:** `python -m pytest` → 383 passed, 6 skipped (379 + 4 casi del test nuovo).
- [ ] **Step 5: commit** `fix(strumenti): nessuna eccezione HTTP dagli strumenti delle date`
  (`git add assistente/dates.py tests/test_dates.py`).

### Task 8: indirizzo locale 127.0.0.1 e verifica (spec §9.2-9.3)

**Files:**
- Modify: `.env.example`, `README.md`, `docs/registro-test.md`, `Es.1/plan.md`; `.env` locale fuori
  da Git

- [ ] **Step 1: misura prima della modifica**: servizio locale acceso
  (`python -m uvicorn servizio_giorni.app:app --port 8000`); tempo di 3 chiamate a `date_info`
  tramite `make_date_tools("http://localhost:8000", "Europe/Rome")` e di 3 tramite
  `make_date_tools("http://127.0.0.1:8000", "Europe/Rome")` (script usa e getta nella scratchpad).
- [ ] **Step 2: modifica**: `GIORNI_BASE_URL=http://127.0.0.1:8000` in `.env.example` e nel `.env`
  locale; nel README la riga della variabile, i comandi `Invoke-RestMethod`/`curl.exe` su
  `http://127.0.0.1:8000/salute` e il rimedio a `GIORNI_BASE_URL mancante`. Gli esempi di log reali
  con `localhost` si sostituiscono con quelli nuovi dello Step 3.
- [ ] **Step 3: verifica**: `python -m pytest` (3.13) e
  `docker compose --profile test run --rm --build test` (3.14) → 383 passed, 6 skipped (379 + 4 casi del test nuovo); con il
  servizio acceso `$env:RUN_LMSTUDIO_TESTS = "1"; python -m pytest -m lmstudio -v` → 6 PASS; con il
  servizio spento, una domanda sulle date dà nel log
  `Errore: servizio giorni non raggiungibile a http://127.0.0.1:8000.` e la chat continua.
  Fermare il servizio e lasciare libera la porta 8000.
- [ ] **Step 4: commit** `fix(config): indirizzo locale 127.0.0.1 per il servizio giorni`
  (`git add .env.example README.md`).
- [ ] **Step 5: registro e piano**: in `docs/registro-test.md` una sessione con i tempi dello Step 1,
  gli esiti dello Step 3 e, tra le cose da provare o da decidere, il rischio `GG-MM` (spec §9),
  il comportamento a servizio spento e lo stesso possibile ritardo di `LMSTUDIO_BASE_URL`; esito in
  `Es.1/plan.md`. Commit `docs: esito delle correzioni dopo la revisione finale`.

## Aggiunte prima del merge in `dev` (2026-11-08)

Stato: proposta del 2026-11-08, **approvata** dall'utente il 2026-11-08 (esecuzione Native, inline).

Spec §10 (approvata il 2026-11-08). Stessi Global Constraints del piano. Suite attuale: 383 passed,
6 skipped; i Task 9-10 cambiano testi attesi di test esistenti, senza test nuovi, quindi le conte
restano 383/6. Serie sui modelli: solo `google/gemma-4-e2b`, script usa e getta nella scratchpad
(`create_graph` + `ask`, una sessione nuova per tentativo), esiti nel registro. Un esito sotto il
criterio si riporta all'utente e non si corregge senza accordo. Il servizio locale e quello Docker
non vanno mai avviati insieme; a fine prova la porta 8000 resta libera.

### Task 9: il testo dei guasti del servizio chiede di non rispondere a mente (spec §10.1)

**Files:**
- Modify: `assistente/dates.py` (`_call`), `README.md` (tabella degli errori, esempio con il
  servizio spento, riga di diagnosi)
- Test: `tests/test_dates.py`

- [ ] **Step 1: misura prima**: serie con il servizio spento, «Quanti giorni mancano a Natale?», 10
  tentativi sul codice attuale (già avviata il 2026-11-08 prima del piano). Conta le risposte senza
  un numero di giorni.
- [ ] **Step 2: test**: in `test_unreachable`, `test_unexpected_response` e
  `test_http_error_becomes_invalid_response` i testi attesi finiscono con
  `" Non è possibile calcolare il risultato: dillo all'utente e non calcolarlo a mente."`, per
  esempio `"Errore: servizio giorni non raggiungibile a http://giorni.test. Non è possibile
  calcolare il risultato: dillo all'utente e non calcolarlo a mente."`. `test_400_becomes_error_text`
  resta invariato (nessuna coda sugli errori di validazione).
- [ ] **Step 3:** `python -m pytest tests/test_dates.py -v` → FAIL nei tre test modificati.
- [ ] **Step 4: implementare**: in `assistente/dates.py` una costante
  `SERVICE_FAILURE_HINT = "Non è possibile calcolare il risultato: dillo all'utente e non calcolarlo a mente."`,
  aggiunta (dopo uno spazio) ai tre testi «non raggiungibile», «risposta non valida (HTTP …)» e
  «risposta non valida» senza codice. Il ramo del 400 non cambia.
- [ ] **Step 5:** `python -m pytest` → 383 passed, 6 skipped.
- [ ] **Step 6: misura dopo**: stessa serie dello Step 1 (servizio spento, 10 tentativi). Criterio:
  almeno 8 risposte su 10 senza un numero di giorni; un numero conta come fallimento anche se
  esatto. Una domanda successiva nella stessa sessione («Quanto fa 2 + 2?») → `calculate`, la chat
  continua.
- [x] **Esito Step 1 e 6 (2026-11-08):** prima 0 su 8 senza numero; dopo (solo testo d'errore) 0
  su 5; criterio mancato, riferito all'utente. Spike con la regola in coda al prompt (solo nello
  script): 7 su 10. Scelta dell'utente: regola nel prompt e 7 su 10 accettato (spec §10.1.1).
- [ ] **Step 6a: test** (spec §10.1.1) in `tests/test_cli.py`: `test_system_prompt_ends_with_service_failure_rule`
  → `SYSTEM_PROMPT.endswith(" Se uno strumento risponde che il servizio giorni non è raggiungibile o che la sua risposta non è valida, di' all'utente che il calcolo non è disponibile e non dare risultati calcolati a mente o con altri strumenti.")`;
  in `test_system_prompt_mentions_date_tools` `endswith(...)` diventa `... in SYSTEM_PROMPT`.
- [ ] **Step 6b:** `python -m pytest tests/test_cli.py -v` → FAIL solo nel test nuovo.
- [ ] **Step 6c: implementare**: la frase in coda a `SYSTEM_PROMPT` in `assistente/cli.py`.
- [ ] **Step 6d:** `python -m pytest` → 384 passed, 6 skipped (383 + il test nuovo). Poi
  `python -m assistente` con il servizio spento: «Quanti giorni mancano a Natale?», «Quanto fa 2 +
  2?», `esci`; log e risposte per lo Step 7 (la chat continua con `calculate`).
- [ ] **Step 7: README**: righe «servizio spento» e «risposta inattesa» della tabella degli errori
  con il testo nuovo; esempio di log con il servizio spento preso dalla serie dello Step 6 (con il
  commento aggiornato all'esito, circa 7 su 10 con gemma); riga di diagnosi «servizio giorni non
  raggiungibile».
- [ ] **Step 8: commit** `fix(strumenti): i guasti del servizio giorni chiedono di non rispondere a mente`
  (`git add assistente/dates.py tests/test_dates.py assistente/cli.py tests/test_cli.py README.md`).

### Task 10: `days_between` non aggiunge l'anno alle date senza anno (spec §10.3)

**Files:**
- Modify: `assistente/dates.py` (`DAYS_BETWEEN_DESCRIPTION`)
- Test: `tests/test_dates.py` (`DESCRIPTIONS`)

- [ ] **Step 1: test**: in `DESCRIPTIONS["days_between"]` il letterale diventa il testo esatto della
  spec §10.3 (cambia solo «… passa MM-GG (es. '12-25' per Natale) senza aggiungere tu l'anno: si usa
  la prossima occorrenza.»).
- [ ] **Step 2:** `python -m pytest tests/test_dates.py -k descriptions -v` → FAIL su `days_between`.
- [ ] **Step 3: implementare**: `DAYS_BETWEEN_DESCRIPTION` uguale al letterale. Le altre tre
  descrizioni e il prompt di sistema non cambiano.
- [ ] **Step 4:** `python -m pytest` → 383 passed, 6 skipped.
- [ ] **Step 5: serie** (servizio locale acceso, `python -m uvicorn servizio_giorni.app:app --port 8000`):
  «Quanti giorni mancano all'11 febbraio?», 10 tentativi. Criterio: nessuna data di arrivo già
  passata (`end` `02-11` o nell'anno successivo) in 10 su 10; sotto, la frase resta se almeno 8 su
  10 (come lo spike) e l'esito si annota. Controlli: «Quanti giorni mancano a Natale?» e «Il 2
  giugno 2027 è festivo?», 2 tentativi ciascuno, come nella serie del 2026-11-05.
- [ ] **Step 6: commit** `fix(strumenti): days_between non aggiunge l'anno alle date senza anno`
  (`git add assistente/dates.py tests/test_dates.py`).
- [x] **Esito (2026-11-08):** Steps 1-4 fatti (RED 1 fallito, GREEN 384/6); serie dello Step 5
  fermata a 9 tentativi: 7 su 9 con data passata, 1 su 9 giusto, 1 su 9 con `start` sbagliato
  (spike: 8 su 10 giusti). Criterio mancato: per scelta dell'utente modifica annullata
  (`git restore`), nessun commit dello Step 6 (spec §10.3.1).

### Task 11: fuso dei log in Docker e 127.0.0.1 per LM Studio (spec §10.2)

**Files:**
- Modify: `compose.yaml` (servizio `assistente`), `.env.example`, `README.md` (tabella delle
  variabili, comando `Invoke-RestMethod` di LM Studio, sezione Docker Compose); `.env` locale fuori
  da Git

- [ ] **Step 1: misura prima**: tempo della prima richiesta `GET /v1/models` con httpx (client
  nuovo per ogni misura, 3 misure per indirizzo) verso `http://localhost:1234/v1` e
  `http://127.0.0.1:1234/v1` (script usa e getta nella scratchpad).
- [ ] **Step 2: 127.0.0.1**: `LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1` in `.env.example` e nel
  `.env` locale; nel README l'esempio della tabella, con la stessa spiegazione di `GIORNI_BASE_URL`
  (LM Studio ascolta solo su `127.0.0.1`, `localhost` prova prima `::1`), e il comando
  `Invoke-RestMethod http://127.0.0.1:1234/v1/models …`.
- [ ] **Step 3: verifica 127.0.0.1**: `python -m pytest` → 383/6; con il servizio acceso
  `$env:RUN_LMSTUDIO_TESTS = "1"; python -m pytest -m lmstudio -v` → 6 PASS; il comando
  `Invoke-RestMethod` del README elenca il modello. Commit
  `fix(config): indirizzo 127.0.0.1 per LM Studio` (`git add .env.example README.md`).
- [ ] **Step 4: TZ**: in `compose.yaml`, nell'`environment` di `assistente`, `TZ: Europe/Rome` con un
  commento (solo l'ora dei log; l'orologio usa `DEFAULT_TIMEZONE`); una frase nella sezione Docker
  Compose del README.
- [ ] **Step 5: verifica TZ**: `docker compose --profile test run --rm --build test` → 383/6 (3.14);
  `"Che ore sono?", "esci" | docker compose run --rm -T --build assistente`: il timestamp dei log
  coincide con l'ora di Roma (`Get-Date`) e il risultato dello strumento dice ancora
  `fuso predefinito Europe/Rome`; poi `docker compose stop giorni`. Commit
  `build: fuso Europe/Rome per i log del container` (`git add compose.yaml README.md`).
- [ ] **Step 6: registro e piano**: in `docs/registro-test.md` una sessione (10) con lo spike della
  spec §10.3, le serie dei Task 9-10, i tempi dello Step 1, la verifica TZ e le cose rimaste da
  provare (checklist in Docker nella verifica completa, checklist con terminale interattivo
  vero); esito in `Es.1/plan.md`. Commit `docs: esito delle aggiunte prima del merge`.
- [ ] **Step 7:** chiedere all'utente l'ok per il merge in `dev`. Push solo su richiesta, dopo la
  verifica completa rieseguita (suite 3.13 e 3.14, LM Studio, checklist Docker).
