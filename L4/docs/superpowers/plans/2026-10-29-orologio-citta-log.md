# Orologio per città e log dei messaggi — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** lo strumento orologio trova da solo il fuso di una città nominata dall'utente e i log
mostrano i messaggi scambiati con il modello.

**Architecture:** nuovo modulo `assistente/cities.py` (ricerca città → fuso su archivio locale);
`tools.py` cambia il parametro dello strumento da `timezone` a `city`; il nodo `modello` di
`graph.py` registra i messaggi in entrata e in uscita. Grafo, instradamento e CLI restano invariati
salvo il prompt di sistema.

**Tech Stack:** Python 3.13 (venv) e 3.14 (Docker), LangGraph, langchain-core, `zoneinfo` +
`tzdata`, nuova dipendenza `geonamescache==3.0.2`, pytest.

**Spec:** `L4/docs/superpowers/specs/2026-10-29-orologio-citta-log-design.md` (estende
`2026-10-26-assistente-langgraph-design.md`).

Tutti i comandi si eseguono da `Es.1/L4` in PowerShell con il venv attivo (`.\.venv\Scripts\Activate.ps1`).

## Global Constraints

- Lavorare solo in `Es.1/L4` (più l'aggiunta del piano a `Es.1/plan.md`); branch corrente `main`.
- Dipendenze con versione fissata (`==`); `geonamescache==3.0.2` in `requirements.txt`.
- Nessun accesso alla rete per la ricerca delle città.
- `DEFAULT_TIMEZONE` invariato, predefinito `Europe/Rome`.
- Testi esatti dello strumento:
  - città: `<ISO> (<nome>, <paese>, fuso <IANA>)`, es. `2026-10-29T05:30:24-04:00 (Miami, US, fuso America/New_York)`
  - nome IANA: `<ISO> (fuso <IANA>)`
  - predefinito: `<ISO> (fuso predefinito <IANA>)`
  - errore: `Errore: città sconosciuta '<city>'. Indica il nome di una città, ad esempio 'Roma'.`
- Log INFO sul logger `assistente.graph` con i prefissi esatti `→ modello [sistema]`,
  `→ modello [utente]`, `→ modello [strumento <nome>]`, `← modello [chiamata]`,
  `← modello [chiamata non valida]`, `← modello [risposta]`; a capo resi come `\n`.
- Suite senza modello verde su 3.13 (`python -m pytest`) e 3.14
  (`docker compose --profile test run --rm --build test`) prima di ogni commit.
- Conventional Commits in italiano; `git status`, controllo del diff, staging selettivo; firma
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Nessun push senza l'ok dell'utente.

## Review Focus

- Il modello passa città e paese insieme («Miami, Florida», «Paris, France»): l'utente si aspetta
  che la città sia trovata → `find_city` riprova con la parte prima della prima virgola (Task 1).
- Il modello passa ancora il vecchio argomento (`{'timezone': 'Asia/Tokyo'}`): l'argomento
  sconosciuto viene ignorato e il risultato dichiara `fuso predefinito Europe/Rome`, così modello
  e log mostrano la ricaduta (Task 1).
- Nomi con o senza accenti («Città del Messico», «Citta del Messico», «Sao Paulo») devono essere
  trovati (Task 1).
- Una risposta del modello con contenuto a blocchi (lista invece di stringa) va registrata come
  testo, senza eccezioni nel nodo (Task 2).
- Alla seconda domanda della sessione i log mostrano solo il nuovo messaggio dell'utente, non
  sistema e scambi precedenti (Task 2).

---

### Task 1: Ricerca delle città e strumento con il parametro `city`

**Files:**
- Create: `assistente/cities.py`, `tests/test_cities.py`
- Modify: `assistente/tools.py`, `assistente/cli.py` (`SYSTEM_PROMPT`), `requirements.txt`
- Test: `tests/test_tools.py`, `tests/test_graph.py` (costanti e scenari), `tests/test_cli.py`,
  `tests/integration/test_lmstudio.py`

**Interfaces:**
- Produces: `cities.City(NamedTuple)` con `name: str`, `country: str`, `timezone: str`;
  `cities.find_city(name: str) -> City | None`;
  `tools.current_time(city: str | None, default_timezone: str, now: datetime) -> str`;
  `tools.make_clock_tool(default_timezone: str, clock=utc_now) -> BaseTool` con lo strumento
  `get_current_time(city: str | None = None)`. `canonical_timezone` resta invariata.

- [ ] **Step 1: Dipendenza.** Aggiungi `geonamescache==3.0.2` in coda a `requirements.txt`;
  `python -m pip install -r requirements-dev.txt`; `python -m pip check` → nessun conflitto.

- [ ] **Step 2: Test che falliscono — `tests/test_cities.py`**

```python
@pytest.mark.parametrize("name, expected", [
    ("Miami", ("Miami", "US", "America/New_York")),
    ("Nuova York", ("New York City", "US", "America/New_York")),
    ("pechino", ("Beijing", "CN", "Asia/Shanghai")),
    ("Città del Messico", ("Mexico City", "MX", "America/Mexico_City")),
    ("Citta del Messico", ("Mexico City", "MX", "America/Mexico_City")),
    ("  KYOTO ", ("Kyoto", "JP", "Asia/Tokyo")),
])
def test_find_city(name, expected):
    assert tuple(find_city(name)) == expected

def test_homonyms_pick_most_populous():
    assert find_city("Paris").country == "FR"

@pytest.mark.parametrize("name", ["Miami, Florida", "Miami, USA"])
def test_country_after_comma_is_ignored(name):
    assert find_city(name).timezone == "America/New_York"

@pytest.mark.parametrize("name", ["Xyzville", "", "   ", ","])
def test_unknown_or_empty_city(name):
    assert find_city(name) is None
```

- [ ] **Step 3: Test che falliscono — `tests/test_tools.py`** (sostituisce i test sul parametro
  `timezone`; `NOW = datetime(2026, 10, 26, 16, 5, tzinfo=timezone.utc)` invariato)

```python
MIAMI = "2026-10-26T12:05:00-04:00 (Miami, US, fuso America/New_York)"
TOKYO_IANA = "2026-10-27T01:05:00+09:00 (fuso Asia/Tokyo)"
ROME_DEFAULT = "2026-10-26T17:05:00+01:00 (fuso predefinito Europe/Rome)"

def test_time_in_city(): assert current_time("Miami", "Europe/Rome", NOW) == MIAMI
@pytest.mark.parametrize("city", ["Asia/Tokyo", " asia/tokyo "])
def test_iana_name_is_accepted(city): assert current_time(city, "Europe/Rome", NOW) == TOKYO_IANA
@pytest.mark.parametrize("city", [None, "", "   "])
def test_missing_city_uses_default(city): assert current_time(city, "Europe/Rome", NOW) == ROME_DEFAULT
@pytest.mark.parametrize("city", ["Xyzville", "../etc/passwd"])
def test_unknown_city_returns_error_text(city):
    assert current_time(city, "Europe/Rome", NOW) == (
        f"Errore: città sconosciuta '{city}'. Indica il nome di una città, ad esempio 'Roma'.")
def test_tool_uses_injected_clock():
    tool = make_clock_tool("Europe/Rome", clock=lambda: NOW)
    assert tool.invoke({"city": "Miami"}) == MIAMI
    assert tool.invoke({}) == ROME_DEFAULT
def test_old_timezone_argument_falls_back_to_default():
    tool = make_clock_tool("Europe/Rome", clock=lambda: NOW)
    assert tool.invoke({"timezone": "Asia/Tokyo"}) == ROME_DEFAULT
def test_tool_schema():  # proprietà "city" di tipo stringa, non obbligatoria; nessuna "timezone"
```

- [ ] **Step 4: Adegua i test esistenti al nuovo formato.**
  - `tests/test_graph.py`: `TOKYO = "2026-10-27T01:05:00+09:00 (Tokyo, JP, fuso Asia/Tokyo)"`; negli
    scenari gli argomenti `{"timezone": "Asia/Tokyo"}` diventano `{"city": "Tokyo"}` (anche nelle
    stringhe attese da `test_tool_calls_are_logged`); in `test_malformed_tool_args_return_error`
    gli argomenti diventano `{"city": ["Tokyo"]}`.
  - `tests/test_cli.py`: nuovo `test_system_prompt_mentions_city_parameter` →
    `"parametro city" in SYSTEM_PROMPT`.
  - `tests/integration/test_lmstudio.py`: `test_real_model_uses_clock_tool` chiede
    «Che ore sono adesso a Miami?» e verifica che una `ToolMessage` di `get_current_time` contenga
    `"America/New_York"`.

- [ ] **Step 5: Verifica che falliscano** — `python -m pytest -v` → FAIL (modulo `assistente.cities`
  mancante, formati nuovi assenti).

- [ ] **Step 6: Implementa `assistente/cities.py`.** Indice costruito una volta con
  `functools.lru_cache(maxsize=1)` da `GeonamesCache(min_city_population=5000).get_cities()`:
  per ogni città, chiavi `casefold()` di nome e `alternatenames`, valore la città più popolosa.
  `find_city`: cerca `name.strip().casefold()`; se non trova e c'è una virgola, riprova con la
  parte prima della prima virgola; chiave vuota → `None`.

- [ ] **Step 7: Implementa lo strumento in `assistente/tools.py`.** `current_time` risolve in
  quest'ordine: `city` vuota o `None` → predefinito; `canonical_timezone(city)` → fuso IANA;
  `find_city(city)` → fuso della città; altrimenti testo d'errore. `CLOCK_DESCRIPTION`:

```python
CLOCK_DESCRIPTION = (
    "Restituisce la data e l'ora attuali in una città. Parametro city: il nome della città "
    "citata dall'utente, così come l'ha scritta (es. 'Miami', 'Nuova York'). Se l'utente non "
    "nomina una città, omettilo e si usa il fuso predefinito."
)
```

- [ ] **Step 8: Prompt di sistema in `assistente/cli.py`** — aggiungi in coda a `SYSTEM_PROMPT`:
  `" Se l'utente chiede l'ora di una città, passa il nome della città nel parametro city."`

- [ ] **Step 9: Verifica su 3.13 e 3.14** — `python -m pytest` e
  `docker compose --profile test run --rm --build test` → tutti passed, 3 skipped.

- [ ] **Step 10: Prova reale** — con LM Studio attivo:
  `$env:RUN_LMSTUDIO_TESTS = "1"; python -m pytest -m lmstudio -v; Remove-Item Env:RUN_LMSTUDIO_TESTS`
  → 3 passed. Poi «Che ore sono a Miami?» ripetuta 5 volte in sessioni nuove
  (`python -m assistente`): annota per ciascuna gli argomenti ricevuti dallo strumento.
  Una prova reale fallita non si corregge con una risposta simulata: si riporta all'utente.

- [ ] **Step 11: Commit**

```bash
git add L4/requirements.txt L4/assistente/cities.py L4/assistente/tools.py L4/assistente/cli.py L4/tests/test_cities.py L4/tests/test_tools.py L4/tests/test_graph.py L4/tests/test_cli.py L4/tests/integration/test_lmstudio.py
git commit -m "feat(strumenti): trova il fuso orario dal nome della città"
```

---

### Task 2: Log dei messaggi scambiati con il modello

**Files:**
- Modify: `assistente/graph.py` (`call_model` e funzioni di supporto private)
- Test: `tests/test_graph.py`

**Interfaces:**
- Consumes: `make_clock_tool` e il formato `TOKYO` del Task 1.
- Produces: nessuna interfaccia pubblica nuova; solo righe di log.

- [ ] **Step 1: Test che falliscono** (con `caplog.set_level(logging.INFO, logger="assistente.graph")`)

```python
def test_model_exchange_is_logged(caplog):
    build_graph(tokyo_scenario(), [clock]).invoke(start("ora a Tokyo?"))
    assert "→ modello [utente] ora a Tokyo?" in caplog.text
    assert "← modello [chiamata] get_current_time {'city': 'Tokyo'}" in caplog.text
    assert f"→ modello [strumento get_current_time] {TOKYO}" in caplog.text
    assert "← modello [risposta] Sono le 01:05" in caplog.text

def test_system_prompt_logged_only_on_first_question(caplog):
    # due domande con ask(); "→ modello [sistema]" compare una volta;
    # dopo la seconda domanda l'unica riga "→ modello" nuova è "[utente] grazie"

def test_newlines_are_escaped_in_logs(caplog):
    # risposta "riga1\nriga2" → nel log "← modello [risposta] riga1\\nriga2"

def test_invalid_call_is_logged(caplog):
    # AIMessage con invalid_call("c1") → riga che inizia con "← modello [chiamata non valida] get_current_time"

def test_block_content_is_logged_as_text(caplog):
    # AIMessage(content=[{"type": "text", "text": "ciao"}]) → "← modello [risposta] ciao"
```

- [ ] **Step 2: Verifica che falliscano** — `python -m pytest tests/test_graph.py -v` → FAIL sui
  test nuovi.

- [ ] **Step 3: Implementa in `graph.py`.** In `call_model`: messaggi nuovi = quelli dopo
  l'ultima `AIMessage` della cronologia (tutti, se non ce n'è una); per ciascuno una riga
  `→ modello [<ruolo>] <testo>` con ruolo `sistema` / `utente` / `strumento <name>`; dopo
  `model.invoke` una riga per ogni `tool_call` e `invalid_tool_call` e, se `message.text` non è
  vuoto, `← modello [risposta] <testo>`. Testo da `message.text`, con `"\n"` sostituito da `"\\n"`.
  Aggiorna la docstring del modulo solo se il diagramma cambia (non cambia).

- [ ] **Step 4: Verifica su 3.13 e 3.14** — come Task 1 Step 9.

- [ ] **Step 5: Prova manuale** — `python -m assistente`, «Che ore sono a Miami?»: a schermo le
  righe `→ modello` / `← modello` nell'ordine dell'esempio della spec §4.

- [ ] **Step 6: Commit**

```bash
git add L4/assistente/graph.py L4/tests/test_graph.py
git commit -m "feat(grafo): registra i messaggi scambiati con il modello"
```

---

### Task 3: Documentazione, registri e verifica completa

**Files:**
- Create: `docs/registro-modifiche.md`
- Modify: `README.md`, `CLAUDE.md`, `docs/registro-test.md`

- [ ] **Step 1: Verifica completa da capo** sullo stato dopo il Task 2:
  1. `python -m pytest -v` (3.13) e `docker compose --profile test run --rm --build test` (3.14);
  2. prove reali con LM Studio (comando del Task 1 Step 10);
  3. checklist in Docker (`docker compose run --rm --build assistente`): «Che ore sono a Miami?»,
     «Quale città ti ho chiesto prima?», nuova sessione con la stessa domanda, «Che ore sono?»;
  4. serie di città in sessioni nuove, annotando argomenti e risposta: Miami ×5, Bari, Kyoto,
     Pechino, Nuova York, Monaco di Baviera, San Francisco, Buenos Aires, Mumbai, Dubai, Sydney,
     Città del Messico, Chioggia.

- [ ] **Step 2: `docs/registro-test.md`** — nuova sessione in cima con data, commit, riepilogo
  (superati / non superati / skipped), test nuovi per nome, checklist e serie di città. Includi
  anche la sessione di base del 2026-10-29 prima della modifica: suite 57 passed / 3 skipped su
  3.13 e 3.14, prove reali 3 passed, checklist Tokyo superata, Miami 1 risposta giusta su 5
  (4 chiamate `{}`), Bari `{}` (giusta per caso), Kyoto / Pechino / Nuova York con fuso corretto.

- [ ] **Step 3: `docs/registro-modifiche.md`** — una voce per modifica, dalla più recente, con
  campi *Data*, *Che cosa non era giusto*, *Causa*, *Soluzione*, *Commit*, *Verifica*:
  1. log dei messaggi al modello (commit del Task 2);
  2. strumento per città (commit del Task 1; dati di base del Step 2);
  3. `302f4a8`: una chiamata allo strumento con argomenti non interpretabili lasciava nella
     cronologia una chiamata senza risposta e la sessione si rompeva; ora anche le
     `invalid_tool_calls` ricevono una `ToolMessage` d'errore e la CLI scarta la domanda senza
     uscire;
  4. `1471fe2`: `openai` non era fissato e venv e container installavano versioni diverse; ora
     `openai==3.38.0`.

- [ ] **Step 4: README** — sezione «Strumento orologio…»: parametro `city` (anche nome IANA),
  formati del risultato, esempio di log con le righe `→ modello` / `← modello`; «Verifica
  completa» con Miami al posto di Tokyo; «Diagnosi»: righe per `Errore: città sconosciuta…` e per
  `strumento richiesto: get_current_time {}` seguito da `fuso predefinito` (il modello non ha
  passato la città: riformulare citando la città). Link a `docs/registro-test.md` e
  `docs/registro-modifiche.md`. Solo comandi verificati nello Step 1.

- [ ] **Step 5: `L4/CLAUDE.md`** — in «Struttura e comandi» aggiungi `cities.py` (ricerca città →
  fuso) all'elenco del pacchetto e i due registri in `docs/`.

- [ ] **Step 6: Commit**

```bash
git add L4/README.md L4/CLAUDE.md L4/docs/registro-test.md L4/docs/registro-modifiche.md
git commit -m "docs: documenta l'orologio per città, i log e il registro delle modifiche"
```

- [ ] **Step 7: Resoconto** — che cosa è stato eseguito, con quale esito e che cosa resta da
  provare; poi rifare tutte le verifiche dello Step 1 prima di proporre il push e aspettare l'ok.
