# Note persistenti — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** il modello può salvare, elencare ed eliminare note persistenti tramite tre strumenti
dichiarati da un server MCP (`servizio_note`) che l'agente avvia come sottoprocesso stdio.

**Architecture:** `servizio_note/archivio.py` contiene l'SQL puro su SQLite; `servizio_note/server.py`
lo espone come `MCPServer` con tre strumenti. `assistente/mcp_client.py` è un client generico: legge
`list_tools` all'avvio e crea `StructuredTool` sincroni che aprono una sessione MCP per chiamata
(`asyncio.run`). `assistente/notes.py` prepara i parametri del sottoprocesso; `config.py` legge
`NOTE_DB_PATH`, `cli.py` registra gli strumenti, Docker monta un volume per l'archivio.

**Tech Stack:** Python 3.13 (venv) e 3.14 (Docker), `mcp==2.3.0` (`MCPServer`, `Client`,
`StdioServerParameters`), `sqlite3`, LangGraph, langchain-core, pytest.

**Spec:** `L4/docs/superpowers/specs/2026-11-08-note-persistenti-design.md` (approvata il 2026-11-08).

Tutti i comandi si eseguono da `Es.1/L4` in PowerShell con il venv attivo
(`.\.venv\Scripts\Activate.ps1`); in Git Bash `./.venv/Scripts/python.exe -m pytest`.

## Global Constraints

- Branch `feat/note-persistenti`; lavorare solo in `Es.1/L4` (più `Es.1/plan.md`, versionato: le sue
  modifiche vanno in un commit `docs:`). Merge in `dev` solo dopo l'ok dell'utente; push solo su
  richiesta, dopo la verifica completa rieseguita.
- Unica dipendenza nuova: `mcp==2.3.0` in `requirements.txt`. Nessun `pytest-asyncio`: i test
  asincroni girano dentro `asyncio.run`.
- `servizio_note/` non importa nulla da `assistente/`; `archivio.py` non importa `mcp`.
  `mcp_client.py` non contiene nulla di specifico delle note.
- Testi esatti (descrizioni, frase del prompt, successi, errori, `NOTE_FAILURE_HINT`) come nella
  spec §2, copiati alla lettera. Limiti: 1000 caratteri, 20 righe, tempo limite 10 s.
- Codice sincrono verso il grafo: l'asincronia resta dentro `mcp_client.py`.
- `graph.py`, `model.py`, `tools.py`, `dates.py`, `catalog.py`, `units.py`, `arithmetic.py`,
  `cities.py`, `servizio_giorni/`, `servizio_catalogo/` invariati.
- Test esistenti invariati, con le eccezioni dovute alla spec: in `tests/test_config.py` `BASE` e il
  `.env` di `test_environment_wins_over_dotenv` ricevono `NOTE_DB_PATH`;
  `test_tools_include_all_local_tools` elenca 12 strumenti e sostituisce `make_note_tools` con uno
  finto; `test_system_prompt_ends_with_catalog_rule` diventa
  `test_system_prompt_contains_catalog_rule` (controllo con `in`), perché la frase delle note va in
  coda (spec §2.2).
- Suite senza modello verde su 3.13 prima di ogni commit di codice; su 3.14 (container) al Task 5 e
  nella verifica finale. Nessun test della suite richiede rete o LM Studio; solo `test_note_stdio.py`
  e i test di avvio del Task 3 avviano sottoprocessi.
- Conventional Commits in italiano con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`;
  prima di ogni commit `git status`, diff, staging selettivo.

## Review Focus

- Il modello passa l'id come stringa (`{"id": "3"}`): l'SDK lo converte e la nota 3 viene
  eliminata, invece di un errore di validazione (Task 2).
- Testo con a capo («banco 3\npresa rotta»): salvato così com'è, ma in `list_notes` ogni nota resta
  su una riga, con gli a capo mostrati come spazi, così l'elenco non si rompe (Task 2).
- Confine dei 1000 caratteri contati dopo la pulizia: 1000 caratteri accettati, 1001 rifiutati, 1000
  caratteri più spazi esterni accettati (Task 2).
- Server che parte ma non risponde mai: l'avvio dell'app finisce entro il tempo limite con
  `MCPStartupError` («nessuna risposta entro …») e il sottoprocesso viene chiuso, invece di restare
  bloccato (Task 3).
- Comando del server inesistente: il motivo di `MCPStartupError` è il messaggio dell'errore vero,
  non «unhandled errors in a TaskGroup» del gruppo di eccezioni di anyio (Task 3).

---

### Task 1: archivio SQLite (`servizio_note/archivio.py`)

**Files:**
- Create: `servizio_note/__init__.py` (una docstring), `servizio_note/archivio.py`
- Test: `tests/test_archivio_note.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class Note`: `id: int`, `testo: str`, `creata: datetime` (aware, UTC)
  - `add(path: str | Path, text: str, now: datetime) -> Note` (salva `text` così com'è: la pulizia
    spetta al server)
  - `list_recent(path: str | Path, limit: int) -> tuple[list[Note], int]` (al massimo `limit` note
    per id decrescente, più il totale)
  - `delete(path: str | Path, note_id: int) -> Note | None`
  - gli `sqlite3.Error` (e gli `OSError` della creazione della cartella) salgono al chiamante

- [ ] **Step 1: test che falliscono** in `tests/test_archivio_note.py` (tutti su `tmp_path`, istante
  fisso `NOW = datetime(2026, 11, 8, 20, 40, 12, tzinfo=UTC)`):
  - `test_add_creates_folder_and_file`: `add(tmp_path / "a" / "b" / "note.db", "x", NOW)` → il file
    esiste; la nota ha `id == 1`, `testo == "x"`, `creata == NOW`;
  - `test_creata_is_stored_as_utc_iso`: con `sqlite3` diretto, la colonna `creata` vale
    `"2026-11-08T20:40:12+00:00"`; un `now` con offset `+01:00` viene salvato convertito in UTC;
  - `test_list_recent_newest_first_with_total`: 3 note → `list_recent(path, 2)` restituisce gli id
    `[3, 2]` e totale 3; archivio nuovo → `([], 0)`;
  - `test_delete_returns_deleted_note_or_none`: `delete` della 2 → la nota 2; di nuovo → `None`;
    `delete(path, 99)` → `None`;
  - `test_ids_are_not_reused`: aggiungi 1, 2, elimina 2, aggiungi → id 3;
  - `test_data_survives_new_connections`: `add` e poi `list_recent` (ogni funzione apre la sua
    connessione) → la nota c'è; il testo con accenti e «» torna identico.

- [ ] **Step 2:** `python -m pytest tests/test_archivio_note.py -v` → FAIL (`ModuleNotFoundError:
  servizio_note`).

- [ ] **Step 3: implementazione** di `servizio_note/archivio.py`: schema della spec §3.1 (`CREATE
  TABLE IF NOT EXISTS note (id INTEGER PRIMARY KEY AUTOINCREMENT, testo TEXT NOT NULL, creata TEXT
  NOT NULL)`), cartella creata con `Path(path).parent.mkdir(parents=True, exist_ok=True)`, una
  connessione per funzione chiusa in `finally` (o con `contextlib.closing`; `with sqlite3.connect`
  da solo non chiude la connessione), `creata` scritta con
  `now.astimezone(UTC).isoformat(timespec="seconds")` e riletta con `datetime.fromisoformat`.

- [ ] **Step 4:** `python -m pytest tests/test_archivio_note.py -v` → PASS; `python -m pytest` →
  verde.

- [ ] **Step 5: commit** `feat(note): archivio SQLite delle note`.

---

### Task 2: server MCP (`servizio_note/server.py`) e dipendenza `mcp`

**Files:**
- Create: `servizio_note/server.py`
- Modify: `requirements.txt` (riga `mcp==2.3.0`)
- Test: `tests/test_server_note.py`

**Interfaces:**
- Consumes: `archivio.add`, `archivio.list_recent`, `archivio.delete`, `Note` (Task 1)
- Produces:
  - `NOTE_FAILURE_HINT: str` = testo della spec §2.4, alla lettera
  - `ADD_DESCRIPTION`, `LIST_DESCRIPTION`, `DELETE_DESCRIPTION`: testi della spec §2.1
  - `MAX_TEXT = 1000`, `MAX_ROWS = 20`, `DEFAULT_TIMEZONE = "Europe/Rome"`
  - `server = MCPServer("note", log_level="WARNING")` con `add_note(text: str) -> str`,
    `list_notes() -> str`, `delete_note(id: int) -> str` registrati con
    `@server.tool(description=…)`
  - `_now() -> datetime` (istante UTC; i test lo sostituiscono con `monkeypatch`)
  - `main() -> None` (`server.run("stdio")`), chiamata sotto `if __name__ == "__main__":`

- [ ] **Step 1: dipendenza**: aggiungere `mcp==2.3.0` a `requirements.txt`, poi
  `python -m pip install -r requirements-dev.txt` e `python -m pip check` → «No broken requirements
  found».

- [ ] **Step 2: test che falliscono** in `tests/test_server_note.py`. Helper:
  `call(name, args=None) -> tuple[bool, str]` che esegue
  `asyncio.run(...)` con `async with Client(server) as c: r = await c.call_tool(name, args or {})`
  e restituisce `(r.is_error, testo dei blocchi uniti da "\n")`; fixture `autouse` che imposta
  `NOTE_DB_PATH` su `tmp_path / "note.db"`, toglie `NOTE_TIMEZONE` e sostituisce `server._now` con
  un istante fisso. `PREFIX = "Error executing tool {name}: "` (testo dell'SDK).
  - `test_list_tools_names_descriptions_schemas`: nomi `add_note`, `list_notes`, `delete_note`;
    descrizioni uguali alle costanti; `add_note` richiede `text` di tipo `string`, `delete_note`
    richiede `id` di tipo `integer`, `list_notes` senza proprietà richieste;
  - `test_add_note`: `"  calibrare il multimetro "` → `(False, "Nota 1 salvata: «calibrare il
    multimetro».")`;
  - `test_add_note_empty`: `""` e `"   "` → `(True, PREFIX + "il testo della nota è vuoto.")`;
  - `test_add_note_length_limit`: 1000 caratteri accettati; `" " + 1000 caratteri + " "` accettati;
    1001 → `(True, PREFIX + "il testo della nota supera 1000 caratteri.")`;
  - `test_list_notes_empty`: `(False, "Nessuna nota salvata.")`;
  - `test_list_notes_one`: `"1 nota salvata:\n- 1 (2026-11-08 21:40): x"` con `_now` =
    `2026-11-08 20:40 UTC` e fuso predefinito (Roma, UTC+1 in novembre);
  - `test_list_notes_many_newest_first`: 3 note → prima riga `3 note salvate, dalla più recente:`,
    righe con id 3, 2, 1;
  - `test_list_notes_row_limit`: 21 note → 20 righe (id 21…2) e ultima riga `Altra 1 nota non
    mostrata.`; 23 note → `Altre 3 note non mostrate.`; la prima riga riporta il totale (`21 note
    salvate, …`, `23 note salvate, …`);
  - `test_list_notes_timezone`: `NOTE_TIMEZONE=America/New_York`, `_now` = `2026-11-09 03:30 UTC`
    → `(2026-11-08 22:30)` (cambio di data rispetto a UTC);
  - `test_list_notes_newlines_shown_as_spaces`: nota `"banco 3\npresa rotta"` → riga
    `- 1 (…): banco 3 presa rotta` (Review Focus; il testo salvato resta con l'a capo);
  - `test_delete_note`: dopo un `add_note("x")` → `(False, "Nota 1 eliminata: «x».")`; la nota non
    compare più in `list_notes`;
  - `test_delete_note_unknown`: id 7, 0 e -1 → `(True, PREFIX + "nessuna nota con id 7. Usa
    list_notes per vedere gli id.")` (con il rispettivo id);
  - `test_delete_note_id_as_string`: `{"id": "1"}` elimina la nota 1 (Review Focus);
  - `test_archive_unusable`: con `NOTE_DB_PATH` tolta, con `NOTE_DB_PATH` = `tmp_path` (una
    cartella) e con `NOTE_TIMEZONE=Marte/Base` → `is_error` vero e testo che inizia con
    `PREFIX + "archivio delle note non utilizzabile ("` e finisce con `"). " + NOTE_FAILURE_HINT`.

- [ ] **Step 3:** `python -m pytest tests/test_server_note.py -v` → FAIL (`ModuleNotFoundError:
  servizio_note.server`).

- [ ] **Step 4: implementazione** di `servizio_note/server.py`. Gli strumenti leggono
  `NOTE_DB_PATH` e `NOTE_TIMEZONE` a ogni chiamata; errori previsti con
  `mcp.server.mcpserver.exceptions.ToolError`; `sqlite3.Error`, `OSError`, `NOTE_DB_PATH` mancante e
  `ZoneInfoNotFoundError` diventano `ToolError(f"archivio delle note non utilizzabile ({dettaglio}).
  {NOTE_FAILURE_HINT}")` (dettaglio: messaggio dell'eccezione, `NOTE_DB_PATH mancante`, `fuso
  NOTE_TIMEZONE non valido: '…'`). Righe dell'elenco:
  `f"- {n.id} ({n.creata.astimezone(zona):%Y-%m-%d %H:%M}): {' '.join(n.testo.split())}"`.

- [ ] **Step 5:** `python -m pytest tests/test_server_note.py -v` → PASS; `python -m pytest` →
  verde.

- [ ] **Step 6: commit** `feat(note): server MCP con add_note, list_notes e delete_note` (con
  `requirements.txt`).

---

### Task 3: client MCP generico (`assistente/mcp_client.py`)

**Files:**
- Create: `assistente/mcp_client.py`
- Test: `tests/test_mcp_client.py`

**Interfaces:**
- Produces:
  - `class MCPStartupError(Exception)`: il messaggio è il motivo leggibile
  - `load_mcp_tools(server: StdioServerParameters | MCPServer, failure_hint: str, label: str =
    "server MCP", timeout: float = 10.0) -> list[BaseTool]`
  - testo di guasto: `f"Errore: {label} non disponibile ({motivo}). {failure_hint}"`. `label` non è
    nella spec §4.1: serve a lasciare il client senza nulla delle note (vincolo della spec §4);
    `make_note_tools` passa `label="server delle note"` (Task 4), quindi il testo visto dal modello
    è esattamente quello della spec §2.4.
  - motivi: `nessuna risposta entro {timeout:g} s`; `errore interno del server`; altrimenti la prima
    riga del messaggio dell'eccezione, o il nome della classe se vuoto, dopo aver estratto la prima
    eccezione foglia da un eventuale `BaseExceptionGroup`.

- [ ] **Step 1: test che falliscono** in `tests/test_mcp_client.py`, con un `MCPServer("finto")`
  costruito nel test: strumento `echo(text: str) -> str` (restituisce `text`), `fail() -> str`
  (solleva `ToolError("andato storto")`), `crash() -> str` (solleva `RuntimeError("segreto")`),
  `slow() -> str` (`async`, `await asyncio.sleep(5)`). `HINT = "Coda di prova."`
  - `test_tools_mirror_server`: nomi, descrizioni e `args_schema` (dizionario con `text` richiesto
    per `echo`) uguali a quelli di `list_tools`;
  - `test_text_result`: `tools["echo"].invoke({"text": "ciao è"})` → `"ciao è"`;
  - `test_tool_error_prefix_removed`: `fail` → `"Errore: andato storto"`;
  - `test_crash_is_failure`: `crash` → `"Errore: server MCP non disponibile (errore interno del
    server). Coda di prova."` e `"segreto"` non compare;
  - `test_timeout_during_call`: con `timeout=0.5`, `slow` → `"Errore: server MCP non disponibile
    (nessuna risposta entro 0.5 s). Coda di prova."` in meno di 3 s;
  - `test_label_in_failure_text`: con `label="server delle note"` il testo di `crash` inizia con
    `"Errore: server delle note non disponibile ("`;
  - `test_startup_server_exits`: `StdioServerParameters(command=sys.executable, args=["-c",
    "import sys; sys.exit(3)"])` → `MCPStartupError`;
  - `test_startup_server_hangs`: `args=["-c", "import time; time.sleep(30)"]`, `timeout=1` →
    `MCPStartupError("nessuna risposta entro 1 s")` in meno di 10 s (Review Focus);
  - `test_startup_missing_command`: `command="comando-che-non-esiste"` → `MCPStartupError` il cui
    messaggio non contiene `TaskGroup` e non è vuoto (Review Focus).

- [ ] **Step 2:** `python -m pytest tests/test_mcp_client.py -v` → FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: implementazione**: `mcp.Client(server)` per entrambi i tipi di `server`; ogni
  sessione dentro `async with asyncio.timeout(timeout):`; `StructuredTool.from_function(func=…,
  name=…, description=…, args_schema=tool.input_schema)`, con `func(**kwargs) -> str` che esegue
  `asyncio.run` e cattura `Exception` (non `BaseException`: `KeyboardInterrupt` deve uscire);
  risultato: `r.is_error`, blocchi con attributo `text`.

- [ ] **Step 4:** `python -m pytest tests/test_mcp_client.py -v` → PASS; `python -m pytest` →
  verde.

- [ ] **Step 5: commit** `feat(note): client MCP generico con una sessione per chiamata`.

---

### Task 4: strumenti delle note nell'agente (`notes.py`, `config.py`, `cli.py`)

**Files:**
- Create: `assistente/notes.py`
- Modify: `assistente/config.py`, `assistente/cli.py`, `.env.example`, `.gitignore`
- Test: `tests/test_note_stdio.py`, `tests/test_config.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `load_mcp_tools`, `MCPStartupError` (Task 3); `servizio_note.server.NOTE_FAILURE_HINT`
  (Task 2, solo nei test)
- Produces:
  - `assistente.notes.NOTE_FAILURE_HINT` (copia identica), `PROJECT_DIR: Path` (cartella che contiene
    `assistente/`)
  - `make_note_tools(db_path: str, timezone: str, timeout: float = 10.0) -> list[BaseTool]`
    (`StdioServerParameters` della spec §4.2, `label="server delle note"`)
  - `Settings.note_db_path: str = "dati/note.db"`; `load_settings` richiede `NOTE_DB_PATH` e la
    rende assoluta con `os.path.abspath`
  - `make_tools(settings)` con `*make_note_tools(settings.note_db_path, settings.default_timezone)`
    in coda (12 strumenti); `main()` → `Server MCP delle note non avviabile: {exc}` su stderr e
    codice 1 se `create_graph` solleva `MCPStartupError`

- [ ] **Step 1: test che falliscono**:
  - `tests/test_note_stdio.py::test_notes_over_stdio`: `make_note_tools(str(tmp_path / "note.db"),
    "Europe/Rome")` → nomi `["add_note", "list_notes", "delete_note"]`; `add_note` con
    `"presa rotta è «grave»"` → `"Nota 1 salvata: «presa rotta è «grave»»."`; `list_notes` contiene
    `presa rotta è «grave»`; `delete_note` 1 → `"Nota 1 eliminata: …"`; `list_notes` →
    `"Nessuna nota salvata."`. Eseguito con `monkeypatch.chdir(tmp_path)` per provare il `cwd` del
    sottoprocesso.
  - `tests/test_config.py`: `BASE` e il `.env` di `test_environment_wins_over_dotenv` ricevono
    `NOTE_DB_PATH`; `test_missing_note_db_path` (mancante → `ConfigError` con `NOTE_DB_PATH`);
    `test_note_db_path_is_absolute` (`"dati/note.db"` → `os.path.abspath("dati/note.db")`).
  - `tests/test_cli.py`: in `test_tools_include_all_local_tools` `monkeypatch.setattr(cli,
    "make_note_tools", finto)` (il finto restituisce tre `StructuredTool` con i nomi delle note) e
    12 nomi attesi, distinti; `test_system_prompt_ends_with_notes_rule` (frase della spec §2.2 con
    `endswith`); `test_system_prompt_contains_catalog_rule` sostituisce
    `test_system_prompt_ends_with_catalog_rule` (stesso testo, controllo con `in`);
    `test_main_exits_when_notes_server_fails` (`load_settings` sostituita con `Settings(...)`,
    `check_model` con una funzione vuota, `make_note_tools` che solleva `MCPStartupError("boom")` →
    `main() == 1` e stderr contiene `Server MCP delle note non avviabile: boom`);
    `test_failure_hints_match` (`assistente.notes.NOTE_FAILURE_HINT ==
    servizio_note.server.NOTE_FAILURE_HINT`).

- [ ] **Step 2:** `python -m pytest tests/test_note_stdio.py tests/test_config.py tests/test_cli.py
  -v` → FAIL sui test nuovi.

- [ ] **Step 3: implementazione**: `notes.py`, `config.py`, `cli.py` (frase in coda a
  `SYSTEM_PROMPT`, `make_tools`, `main`). `.env.example`: riga
  `NOTE_DB_PATH=dati/note.db` preceduta da `# Archivio SQLite delle note (relativo alla cartella da
  cui avvii l'app; in Docker viene sostituito da compose.yaml).`. `.gitignore`: `dati/` e `*.db`.

- [ ] **Step 4:** `python -m pytest -v` → verde (i test esistenti invariati, salvo le eccezioni dei
  Global Constraints).

- [ ] **Step 5: prova manuale dalla venv** (`NOTE_DB_PATH` nell'ambiente del comando se il `.env`
  non ce l'ha): `python -m assistente` parte; con LM Studio attivo «Annota che il banco 3 ha la
  presa rotta», `esci`, nuovo avvio e «Quali note ho?» → la nota c'è (persistenza dalla venv, spec
  §7); con `NOTE_DB_PATH` mancante esce con codice 2;
  con un server rotto (per esempio `PROJECT_DIR` sostituito in uno script usa e getta) esce con
  codice 1 e il messaggio. Esiti annotati per il registro del Task 6.

- [ ] **Step 6: commit** `feat(note): strumenti delle note nell'agente`.

---

### Task 5: Docker (volume dell'archivio)

**Files:**
- Modify: `Dockerfile`, `compose.yaml`, `.dockerignore`

- [ ] **Step 1: modifiche** della spec §5: `COPY servizio_note/ servizio_note/` negli stage `test`
  e `app`; nello stage `app`, prima di `USER assistente`, `RUN mkdir -p /app/dati && chown
  assistente /app/dati`; in `compose.yaml`, servizio `assistente`: `NOTE_DB_PATH:
  /app/dati/note.db` con un commento, `volumes: - note:/app/dati`, e `volumes: note:` in fondo;
  `.dockerignore`: `dati`.

- [ ] **Step 2:** `docker compose --profile test run --rm --build test` → verde su Python 3.14.9
  (compreso `test_note_stdio.py` nel container).

- [ ] **Step 3: persistenza** (LM Studio attivo): `"Annota che il banco 3 ha la presa rotta",
  "esci" | docker compose run --rm -T --build assistente` → `add_note` nei log e risposta di
  conferma; `"Quali note ho?", "esci" | docker compose run --rm -T assistente` → `list_notes` e la
  nota nella risposta; nessuna riga `Tool '…' failed` su stderr; poi `docker compose stop giorni
  catalogo`.

- [ ] **Step 4: commit** `build(note): servizio note nell'immagine e volume per l'archivio`.

---

### Task 6: prove reali e documentazione

**Files:**
- Modify: `tests/integration/test_lmstudio.py`, `README.md`, `docs/registro-test.md`,
  `Es.1/plan.md`, `tests/test-manuali.txt` (non versionato); `CLAUDE.md` solo dopo l'ok dell'utente

- [ ] **Step 1: test reale** `test_real_model_uses_notes(tmp_path)`: grafo proprio con
  `create_graph(dataclasses.replace(load_settings(), note_db_path=str(tmp_path / "note.db")))`;
  sessione 1 «Annota che il banco 3 ha la presa rotta» → un `ToolMessage` di `add_note` che inizia
  con `Nota `; sessione 2 (nuova cronologia, stesso grafo) «Quali note ho?» → un `ToolMessage` di
  `list_notes` con «presa» e «presa» nella risposta. Con i servizi giorni e catalogo avviati:
  `$env:RUN_LMSTUDIO_TESTS = "1"; python -m pytest -m lmstudio -v` → 8 PASS. Commit
  `test(note): prova reale degli strumenti delle note`.
- [ ] **Step 2: serie a mano** della spec §7 con uno script usa e getta nella scratchpad
  (`create_graph` con un archivio temporaneo preparato con `servizio_note.archivio.add`, `ask`,
  cronologia nuova per tentativo, JSONL con strumenti, argomenti, risultati, risposta, errore): 10
  tentativi per ciascuna delle quattro domande della spec §1. Criteri: (1) `add_note` con «presa»
  nel testo; (2) `list_notes` e risposta che cita le note preparate; (3) `list_notes`, poi
  `delete_note` con l'id della nota sulla presa e la nota assente dall'archivio; (4) `delete_note`
  con 99 e risposta senza «eliminat». Soglia 8/10 ciascuna. Esito negativo: si riporta, non si
  corregge senza accordo con l'utente.
- [ ] **Step 3: archivio inutilizzabile** (`NOTE_DB_PATH` = una cartella): 10 tentativi di «Annota
  che il banco 3 ha la presa rotta»; conteggio delle risposte che dicono che la nota è salvata.
  Nessuna soglia: esito riportato all'utente.
- [ ] **Step 4: documentazione**: README (variabile `NOTE_DB_PATH` nella tabella di configurazione,
  sezione «Strumenti delle note» con server MCP, sottoprocesso stdio, archivio, volume Docker,
  `docker compose down -v`, archivi separati venv/Docker, testi d'esempio dai log reali; diagnosi:
  server non avviabile, archivio non utilizzabile, tempo limite; solo comandi eseguiti in questo
  piano); `docs/registro-test.md` (sessione con tutte le verifiche, comprese quelle dei Task 4-5);
  `tests/test-manuali.txt` (voci delle note); proposta all'utente per `CLAUDE.md` (spec §8)
  applicata solo dopo il suo ok; esito in `Es.1/plan.md`. Commit `docs: note persistenti nel README
  e nei registri`.
- [ ] **Step 5:** revisione finale del branch (subagent sul modello più capace), poi chiedere
  all'utente l'ok per il merge in `dev`. Push solo su richiesta, dopo la verifica completa
  rieseguita (suite 3.13 e 3.14, LM Studio, checklist Docker di tutti gli strumenti).
