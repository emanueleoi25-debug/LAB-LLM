# Catalogo locale — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** il modello può cercare attrezzatura e materiale nell'inventario del laboratorio e leggere
la scheda di un articolo tramite due strumenti che chiamano il servizio FastAPI `servizio_catalogo`.

**Architecture:** `servizio_catalogo/inventario.py` contiene la logica pura (caricamento e
validazione di `inventario.json`, normalizzazione, radici, ricerca, dettaglio);
`servizio_catalogo/app.py` la espone con tre endpoint `GET`. `assistente/catalog.py` crea due
strumenti client (`httpx` sincrono) che chiamano il servizio e trasformano il JSON in testo.
`config.py` legge `CATALOGO_BASE_URL`, `cli.py` registra gli strumenti, Compose aggiunge il
servizio `catalogo`.

**Tech Stack:** Python 3.13 (venv) e 3.14 (Docker), FastAPI 0.159.1, uvicorn 0.54.0, httpx 0.28.1,
LangGraph, langchain-core, pytest.

**Spec:** `L4/docs/superpowers/specs/2026-11-08-catalogo-locale-design.md` (approvata il 2026-11-08).

Tutti i comandi si eseguono da `Es.1/L4` in PowerShell con il venv attivo
(`.\.venv\Scripts\Activate.ps1`); in Git Bash `./.venv/Scripts/python.exe -m pytest`.

## Global Constraints

- Branch `feat/catalogo-locale`; lavorare solo in `Es.1/L4` (più `Es.1/plan.md`, versionato: le sue
  modifiche vanno in un commit `docs:`). Merge in `dev` solo dopo l'ok dell'utente; push solo su
  richiesta, dopo la verifica completa rieseguita.
- Nessuna dipendenza nuova: `requirements.txt` e `requirements-dev.txt` invariati.
- `servizio_catalogo/` non importa nulla da `assistente/`; `inventario.py` non importa FastAPI.
- Testi esatti (descrizioni, frase del prompt, successi, errori, `detail`) come nella spec §2 e §3.5,
  copiati alla lettera.
- Ricerca come nella spec §3.3: solo nome, categoria e parole chiave; parole della query con almeno
  3 caratteri e non vuote; radice = vocali finali tolte finché la parola è più lunga di 3 caratteri;
  massimo 10 risultati; timeout del client 5 secondi.
- `dates.py`, `graph.py`, `model.py`, `tools.py`, `units.py`, `arithmetic.py`, `cities.py` e
  `servizio_giorni/` invariati.
- Test esistenti invariati, con tre eccezioni dovute alla spec: in `tests/test_config.py` `BASE` e il
  `.env` di `test_environment_wins_over_dotenv` ricevono `CATALOGO_BASE_URL`;
  `test_tools_include_all_local_tools` elenca 11 strumenti; `test_system_prompt_ends_with_service_failure_rule`
  diventa `test_system_prompt_contains_service_failure_rule` (controllo con `in`), perché la frase
  del catalogo va in coda (spec §2.2).
- Suite senza modello verde su 3.13 prima di ogni commit di codice; su 3.14 (container) almeno al
  Task 5 e nella verifica finale. Nessun test della suite richiede rete o LM Studio.
- Conventional Commits in italiano con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`;
  prima di ogni commit `git status`, diff, staging selettivo.

## Review Focus

- Il modello passa `category: ""` o `"  "`: lo strumento non invia `categoria` e cerca in tutto
  l'inventario, invece di rispondere «categoria '' inesistente» (Task 4).
- Query al plurale o con maiuscole e accenti («Batterie», «PILE», «Città»): la radice e la
  normalizzazione trovano gli articoli giusti, «batterie» → LAB-006 e LAB-008 (Task 2).
- Codice con spazi o minuscole (`" lab-002 "`) → scheda di LAB-002; codice malformato (`"LAB 002"`)
  → 404 con il messaggio, mai un 500 (Task 2, Task 3).
- Query di sole parole vuote o troppo corte («dove?», «3D») → errore 400 «nessuna parola utile»,
  non «nessun risultato» e non un 500 (Task 2, Task 3).
- Indirizzo del servizio sbagliato che risponde 404 `{"detail": "Not Found"}` a `/cerca`: testo
  «risposta non valida (HTTP 404)», non «Errore: Not Found» (Task 4).

---

### Task 1: inventario e validazione (`servizio_catalogo/inventario.py`, `inventario.json`)

**Files:**
- Create: `servizio_catalogo/__init__.py` (una docstring), `servizio_catalogo/inventario.py`,
  `servizio_catalogo/inventario.json`
- Test: `tests/test_inventario.py`

**Interfaces:**
- Produces:
  - `DATA_FILE: Path` = `Path(__file__).with_name("inventario.json")`
  - `FIELDS: tuple[str, ...]` = i nove campi nell'ordine della spec §3.1
  - `STATES = ("disponibile", "in manutenzione", "esaurito")`
  - `class InventoryError(Exception)`, `class CatalogError(Exception)`
  - `@dataclass(frozen=True) class Item` con i campi `codice, nome, categoria, parole_chiave:
    tuple[str, ...], descrizione, posizione, quantita: int, stato, note`
  - `load_items(path: Path | None = None) -> tuple[Item, ...]` (`None` → `DATA_FILE`)
  - `categories(items: Sequence[Item]) -> list[str]` (ordine di prima apparizione)

- [ ] **Step 1: test che falliscono** in `tests/test_inventario.py`, con un helper che scrive un
  inventario di prova in `tmp_path` e un articolo valido di base modificabile con `**overrides`:
  - `test_real_file_loads`: 32 articoli; `categories(items) == ["Misura", "Alimentazione",
    "Saldatura", "Microcontrollori", "Componenti", "Cavi e connettori", "Utensili", "Sicurezza"]`;
    ogni categoria ha 4 articoli; codici da `LAB-001` a `LAB-032` in ordine; LAB-002 ha `note ==
    "Prenotare con il tecnico di laboratorio."`; LAB-016 e LAB-023 sono `esaurito` con quantità 0;
    LAB-003 e LAB-012 sono `in manutenzione`; nessun nome contiene «stampa» (in minuscolo);
    `parole_chiave` di LAB-006 == `("pile", "stilo")`.
  - `test_valid_file_gives_items`: un articolo → `Item` con `parole_chiave` tupla.
  - `test_invalid_file` parametrizzato, `pytest.raises(InventoryError, match=…)`:
    | Modifica | `match` |
    |---|---|
    | file con `[]` | `lista non vuota` |
    | file con `{}` | `lista non vuota` |
    | `codice="LAB-1"` | `'codice'` |
    | due articoli con lo stesso codice | `duplicato` |
    | senza `note` | `mancanti: note` |
    | con `prezzo: 3` | `in più: prezzo` |
    | `nome=""` | `'nome'` |
    | `nome=5` | `'nome'` |
    | `quantita=-1` | `'quantita'` |
    | `quantita=True` | `'quantita'` |
    | `quantita=2.0` | `'quantita'` |
    | `stato="rotto"` | `'stato'` |
    | `stato="esaurito", quantita=3` | `incoerente` |
    | `stato="disponibile", quantita=0` | `incoerente` |
    | `parole_chiave=["ok", ""]` | `'parole_chiave'` |
    | `parole_chiave="tester"` | `'parole_chiave'` |
    | `note=None` | `'note'` |
  - `test_error_names_the_item`: con `quantita=-1` sul secondo articolo (codice `LAB-002`) il
    messaggio contiene `LAB-002`; con `codice=7` sul primo il messaggio contiene `n. 1`.

- [ ] **Step 2:** `python -m pytest tests/test_inventario.py -v` → FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: implementazione.** `inventario.json` con i 32 articoli della spec §3.2, alla lettera
  (UTF-8, `ensure_ascii=False`, rientro di 2 spazi, «—» = `[]` o `""`). `load_items` legge con
  `encoding="utf-8"`, controlla nell'ordine: lista non vuota; per ogni articolo oggetto con
  esattamente `FIELDS`; tipi e regole del §3.1; codici unici; coerenza `esaurito` ⇔ 0. Formato dei
  messaggi: `inventario non valido: serve una lista non vuota di articoli` oppure
  `inventario non valido: articolo {etichetta}: {problema}`, dove `etichetta` è il codice se è una
  stringa, altrimenti `n. {posizione da 1}`, e `problema` è uno fra `campi mancanti: a, b`,
  `campi in più: a`, `campo 'X' non valido`, `codice duplicato`, `stato 'esaurito' incoerente con
  quantita 3` (o `quantita 0 incoerente con stato 'disponibile'`). Un intero è valido solo se
  `type(v) is int`.

- [ ] **Step 4:** `python -m pytest tests/test_inventario.py -v` → PASS; poi `python -m pytest` →
  tutta la suite verde.

- [ ] **Step 5: commit** `feat(catalogo): inventario del laboratorio e validazione del file`
  (`servizio_catalogo/__init__.py`, `inventario.py`, `inventario.json`, `tests/test_inventario.py`).

---

### Task 2: ricerca e dettaglio (`servizio_catalogo/inventario.py`)

**Files:**
- Modify: `servizio_catalogo/inventario.py`
- Test: `tests/test_inventario.py`

**Interfaces:**
- Consumes: `Item`, `CatalogError`, `categories`, `load_items` (Task 1)
- Produces:
  - `STOPWORDS: frozenset[str]` = le 30 parole della spec §3.3
  - `MAX_RESULTS = 10`
  - `normalize(text: str) -> list[str]`
  - `stem(word: str) -> str`
  - `query_stems(query: str) -> set[str]` (solleva `CatalogError`)
  - `@dataclass(frozen=True) class SearchResult: items: tuple[Item, ...]; total: int; category:
    str | None` (`items` = al massimo 10; `category` = nome come nel file o `None`)
  - `search(items: Sequence[Item], query: str, category: str | None = None) -> SearchResult`
  - `find(items: Sequence[Item], code: str) -> Item | None`
  - Messaggi di `CatalogError` (testi della spec §3.5, senza «Errore: »):
    `"la ricerca non contiene parole utili (servono parole di almeno 3 lettere)."`,
    `f"categoria '{category.strip()}' inesistente. Categorie valide: {', '.join(categories(items))}."`

- [ ] **Step 1: test che falliscono** (sull'inventario vero, `ITEMS = load_items()`, salvo dove
  indicato):
  - `test_normalize`: `normalize("Città, PILE-AA!") == ["citta", "pile", "aa"]`; con «è» in forma
    NFD (`"è"`) → `["e"]`; `normalize("ESP32 0,8 mm") == ["esp32", "0", "8", "mm"]`.
  - `test_stem` parametrizzato: `resistenze`/`resistenza` → `resistenz`; `oscilloscopio`/
    `oscilloscopi` → `oscilloscop`; `cavo`/`cavi` → `cav`; `led` → `led`; `aria` → `ari`;
    `tester` → `tester`.
  - `test_query_stems`: `query_stems("Dove trovo i saldatori?") == {"trov", "saldator"}`;
    `query_stems("Arduino Uno") == {"arduin"}`; `"dove?"`, `"3D"`, `"   "`, `"per il"` → `CatalogError`
    con `match="parole utili"`.
  - `test_search_examples` parametrizzato su `(query, category, codici attesi)`:
    `("multimetro", None, ["LAB-001"])`; `("oscilloscopio", None, ["LAB-002", "LAB-024"])`;
    `("cavo usb", None, ["LAB-022", "LAB-008", "LAB-021", "LAB-023", "LAB-024"])`;
    `("resistenze", None, ["LAB-017"])`; `("batterie", None, ["LAB-006", "LAB-008"])`;
    `("PILE", None, ["LAB-006"])`; `("tester", None, ["LAB-001"])`; `("stampante 3d", None, [])`;
    `("pinza", None, ["LAB-003", "LAB-026"])`; `("pinza", "misura", ["LAB-003"])`;
    `("cavo", " CAVI E CONNETTORI ", ["LAB-021", "LAB-022", "LAB-023", "LAB-024"])`.
    Controlla anche `total == len(codici)`.
  - `test_search_category_name_as_in_file`: `search(ITEMS, "pinza", "misura").category == "Misura"`;
    senza categoria `category is None`.
  - `test_search_limit`: inventario di prova (oggetti `Item` costruiti nel test) con 12 articoli
    `LAB-001`…`LAB-012` che si chiamano tutti «Cavo …» e un tredicesimo «Cavo usb» con codice
    `LAB-013` → `total == 13`, `len(items) == 10`, il primo è `LAB-013` (punteggio 2 con «cavo usb»),
    poi `LAB-001`…`LAB-009`.
  - `test_search_unknown_category`: `search(ITEMS, "cavo", "stampanti")` → `CatalogError` con
    messaggio esatto `"categoria 'stampanti' inesistente. Categorie valide: Misura, Alimentazione,
    Saldatura, Microcontrollori, Componenti, Cavi e connettori, Utensili, Sicurezza."`
  - `test_find`: `find(ITEMS, " lab-002 ").codice == "LAB-002"`; `"LAB-12"`, `"12"`, `"LAB 002"`,
    `""` → `None`.

- [ ] **Step 2:** `python -m pytest tests/test_inventario.py -v` → i nuovi test FAIL (`ImportError`).

- [ ] **Step 3: implementazione** secondo la spec §3.3-3.4. `normalize`: `unicodedata.normalize("NFD",
  text.lower())`, scarta i caratteri di categoria `Mn`, `re.sub(r"[^a-z0-9]+", " ", …).split()`.
  Le radici di un articolo si calcolano da `normalize` di nome, categoria e di ogni parola chiave,
  senza filtri. Categoria: confronto fra `" ".join(normalize(…))`; il filtro si applica prima del
  punteggio. Ordinamento con chiave `(-punteggio, codice)`. Ordine dei controlli in `search`: prima
  la categoria, poi `query_stems` (con categoria inesistente e query vuota vince l'errore sulla
  categoria; nessun test dipende da questo ordine, ma resta fissato).

- [ ] **Step 4:** `python -m pytest tests/test_inventario.py -v` → PASS; `python -m pytest` → verde.

- [ ] **Step 5: commit** `feat(catalogo): ricerca per radici e dettaglio per codice`.

---

### Task 3: app FastAPI (`servizio_catalogo/app.py`)

**Files:**
- Create: `servizio_catalogo/app.py`
- Test: `tests/test_servizio_catalogo.py`

**Interfaces:**
- Consumes: `load_items`, `search`, `find`, `SearchResult`, `CatalogError` (Task 1-2)
- Produces: `app: FastAPI` (titolo «Servizio catalogo del laboratorio»), `ITEMS` caricati
  all'import; endpoint `GET /cerca(q: str, categoria: str | None = None)`,
  `GET /articolo(codice: str)`, `GET /salute` con le risposte della spec §3.5.

- [ ] **Step 1: test che falliscono** con `client = TestClient(app)`:
  - `test_cerca`: `/cerca?q= oscilloscopio ` → 200 e
    `{"query": "oscilloscopio", "categoria": None, "totale": 2, "articoli": [{"codice": "LAB-002",
    "nome": "Oscilloscopio a 2 canali", "posizione": "Armadio A, ripiano 2", "quantita": 2,
    "stato": "disponibile"}, {"codice": "LAB-024", "nome": "Sonde per oscilloscopio", "posizione":
    "Armadio A, ripiano 2", "quantita": 4, "stato": "disponibile"}]}`.
  - `test_cerca_con_categoria`: `q=pinza&categoria=misura` → `categoria == "Misura"`, `totale == 1`.
  - `test_cerca_senza_risultati`: `q=stampante 3d` → 200, `totale == 0`, `articoli == []`.
  - `test_cerca_errori` parametrizzato → 400 con `detail` esatto: `q` assente → `"parametro 'q'
    mancante o non valido."`; `q=3D` → `"la ricerca non contiene parole utili (servono parole di
    almeno 3 lettere)."`; `q=cavo&categoria=stampanti` → il testo di `test_search_unknown_category`.
  - `test_articolo`: `/articolo?codice=lab-002` → 200 e il dizionario completo di LAB-002 con
    `parole_chiave == ["scope"]` e tutti i nove campi.
  - `test_articolo_inesistente`: `codice= lab-12 ` → 404, `{"detail": "nessun articolo con codice
    'LAB-12'."}`; `codice=LAB 002` → 404.
  - `test_articolo_senza_codice`: parametro assente → 400 `"parametro 'codice' mancante o non valido."`
  - `test_salute`: `{"stato": "ok", "articoli": 32}`.

- [ ] **Step 2:** `python -m pytest tests/test_servizio_catalogo.py -v` → FAIL.

- [ ] **Step 3: implementazione**, stesso schema di `servizio_giorni/app.py`: gestore di
  `CatalogError` → 400 `{"detail": str(exc)}`; gestore di `RequestValidationError` → 400 con
  `exc.errors()[0]["loc"][-1]`; il 404 di `/articolo` è una `JSONResponse` restituita
  dall'endpoint; nel messaggio il codice è `codice.strip().upper()`. Articolo → dizionario con
  `dataclasses.asdict` (`parole_chiave` come lista).

- [ ] **Step 4:** `python -m pytest tests/test_servizio_catalogo.py -v` → PASS; poi la suite intera;
  poi prova a mano: `python -m uvicorn servizio_catalogo.app:app --port 8001` in un altro terminale,
  `curl.exe "http://127.0.0.1:8001/cerca?q=multimetro"` → JSON con LAB-001; fermare uvicorn.

- [ ] **Step 5: commit** `feat(catalogo): servizio FastAPI con ricerca, scheda e salute`.

---

### Task 4: configurazione e strumenti client (`assistente/catalog.py`)

**Files:**
- Create: `assistente/catalog.py`
- Modify: `assistente/config.py`, `.env.example`
- Test: `tests/test_catalog.py`, `tests/test_config.py`

**Interfaces:**
- Consumes: `servizio_catalogo.app.app` solo nei test di contratto
- Produces:
  - `Settings.catalogo_base_url: str = "http://localhost:8001"` (ultimo campo; `load_settings`
    richiede `CATALOGO_BASE_URL`, errore `"CATALOGO_BASE_URL mancante"`)
  - in `assistente/catalog.py`: `TIMEOUT = 5.0`, `CATALOG_FAILURE_HINT`, `SEARCH_DESCRIPTION`,
    `ITEM_DESCRIPTION`, `NOT_FOUND_HINT = "Usa search_catalog per trovare il codice."`,
    `make_catalog_tools(base_url: str, client: httpx.Client | None = None) -> list[BaseTool]`
    → `[search_catalog(query: str, category: str | None = None), get_catalog_item(code: str)]`

- [ ] **Step 1: test di configurazione che falliscono**: `BASE` riceve `"CATALOGO_BASE_URL":
  "http://localhost:8001"` e il `.env` di `test_environment_wins_over_dotenv` la riga
  `CATALOGO_BASE_URL=http://localhost:8001`; nuovi `test_missing_catalogo_base_url` (messaggio con
  `CATALOGO_BASE_URL mancante`) e `test_catalogo_base_url_is_read` (spazi tolti).

- [ ] **Step 2: test del client che falliscono** in `tests/test_catalog.py`, con un helper
  `make_tools(handler)` che passa `httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler))`
  e `BASE_URL = "http://127.0.0.1:8001"`:
  - `test_tool_names_and_descriptions`: nomi `search_catalog`, `get_catalog_item`; descrizioni
    uguali alla spec §2.1; schema: `query` obbligatorio, `category` facoltativo, `code` obbligatorio.
  - `test_default_client`: `TIMEOUT == 5.0`; con `monkeypatch.setattr(catalog.httpx, "Client", spia)`
    e `client` omesso, la spia riceve `base_url=BASE_URL` e `timeout=5.0`.
  - `test_requests` parametrizzato sui parametri inviati: `search_catalog(query="multimetro")` →
    `/cerca` con `{"q": "multimetro"}`; con `category="Misura"` → `{"q": …, "categoria": "Misura"}`;
    con `category=""` e `category="  "` → nessuna `categoria`; `get_catalog_item(code="LAB-002")` →
    `/articolo` con `{"codice": "LAB-002"}`.
  - `test_success_texts` parametrizzato sul JSON del servizio → testo esatto: i due articoli
    dell'esempio della spec §2.3; un risultato con quantità 1 → «Trovato 1 articolo per «…»:» e
    «1 pezzo»; con `categoria: "Misura"` → «… nella categoria Misura:»; `totale` 15 con 10
    articoli → 10 righe e «Altri 5 articoli non mostrati: restringi la ricerca.»; `totale` 11 →
    «Altro 1 articolo non mostrato: restringi la ricerca.»; quantità 0 → «0 pezzi».
  - `test_no_results`: `totale` 0 → «Nessun articolo trovato per «stampante 3d»: dillo all'utente e
    non inventare articoli.»; con categoria → «… per «x» nella categoria Misura: dillo …».
  - `test_item_text`: la scheda di LAB-002 della spec §2.3 alla lettera; con `note: ""` la riga
    «Note» manca; con quantità 1 → «Quantità: 1 pezzo».
  - `test_user_errors`: 400 `{"detail": "la ricerca …"}` → `"Errore: la ricerca …"`; 404 su
    `get_catalog_item` → `"Errore: nessun articolo con codice 'LAB-12'. Usa search_catalog per
    trovare il codice."`.
  - `test_invalid_responses` parametrizzato, entrambi gli strumenti dove ha senso → testo
    `"Errore: risposta non valida dal servizio catalogo (HTTP {codice}). " + CATALOG_FAILURE_HINT`:
    500 JSON; 200 non JSON; 200 con lista JSON; 200 con campi mancanti; 400 senza `detail`; 404 con
    `{"detail": "Not Found"}` su `search_catalog`.
  - `test_unreachable`: handler che solleva `httpx.ConnectError` → `"Errore: servizio catalogo non
    raggiungibile a http://127.0.0.1:8001. " + CATALOG_FAILURE_HINT`; `httpx.ReadTimeout` → stesso
    testo.
  - `test_http_error_without_status`: handler che solleva `httpx.DecodingError` → `"Errore: risposta
    non valida dal servizio catalogo. " + CATALOG_FAILURE_HINT`.
  - Test di contratto con `client=TestClient(app)` (`servizio_catalogo.app`), `base_url
    "http://testserver"`: `search_catalog(query="multimetro")` contiene
    «- LAB-001 Multimetro digitale: Armadio A, ripiano 1; 6 pezzi; disponibile»;
    `get_catalog_item(code="lab-002")` termina con «Note: Prenotare con il tecnico di laboratorio.»;
    `get_catalog_item(code="LAB-99")` → «Errore: nessun articolo con codice 'LAB-99'. Usa
    search_catalog …»; `search_catalog(query="cavo", category="stampanti")` inizia con
    «Errore: categoria 'stampanti' inesistente.».

- [ ] **Step 3:** `python -m pytest tests/test_config.py tests/test_catalog.py -v` → FAIL.

- [ ] **Step 4: implementazione.** `config.py`: `CATALOGO_BASE_URL` nel ciclo dei campi
  obbligatori dopo `GIORNI_BASE_URL`. `catalog.py`: `_call(path, params, formatter, not_found_hint)`
  con la struttura di `dates.py` (spec §4): `TransportError` → irraggiungibile; altro `HTTPError` →
  non valida senza codice; JSON non dizionario → non valida; 400 con `detail` stringa → errore
  utente; 404 con `detail` stringa e `not_found_hint` → errore utente + `" " + NOT_FOUND_HINT`;
  altro codice diverso da 200 → non valida; `KeyError`/`TypeError`/`ValueError` nel formatter →
  non valida. `.env.example`: dopo `GIORNI_BASE_URL`, commento «# Indirizzo del servizio catalogo
  (python -m uvicorn servizio_catalogo.app:app --port 8001; in Docker viene sostituito da
  compose.yaml).» e `CATALOGO_BASE_URL=http://127.0.0.1:8001`.

- [ ] **Step 5:** `python -m pytest tests/test_config.py tests/test_catalog.py -v` → PASS;
  `python -m pytest` → verde. Il `.env` locale non va toccato: aggiungere la riga è un'azione
  dell'utente, segnalata nel resoconto del Task 5.

- [ ] **Step 6: commit** `feat(catalogo): strumenti client search_catalog e get_catalog_item`
  (`assistente/catalog.py`, `assistente/config.py`, `.env.example`, `tests/test_catalog.py`,
  `tests/test_config.py`).

---

### Task 5: registrazione nell'agente e Docker

**Files:**
- Modify: `assistente/cli.py`, `compose.yaml`, `Dockerfile`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `make_catalog_tools` (Task 4), `Settings.catalogo_base_url`
- Produces: `make_tools(settings)` con 11 strumenti: i 7 attuali, poi `search_catalog`,
  `get_catalog_item`; `SYSTEM_PROMPT` che termina con la frase della spec §2.2.

- [ ] **Step 1: test che falliscono** in `tests/test_cli.py`:
  `test_tools_include_all_local_tools` con l'elenco di 11 nomi;
  `test_system_prompt_ends_with_service_failure_rule` rinominato
  `test_system_prompt_contains_service_failure_rule` con `in` al posto di `endswith` (stesso testo);
  nuovo `test_system_prompt_ends_with_catalog_rule`: `SYSTEM_PROMPT.endswith(" " + frase)` con la
  frase della spec §2.2 alla lettera.

- [ ] **Step 2:** `python -m pytest tests/test_cli.py -v` → FAIL sui due test nuovi o modificati.

- [ ] **Step 3: implementazione**: frase aggiunta in coda a `SYSTEM_PROMPT` (preceduta da uno
  spazio); `make_tools` aggiunge `*make_catalog_tools(settings.catalogo_base_url)` e la docstring
  cita il catalogo. `compose.yaml`: servizio `catalogo` come `giorni` (comando
  `["python", "-m", "uvicorn", "servizio_catalogo.app:app", "--host", "0.0.0.0", "--port", "8001"]`,
  porta `"127.0.0.1:8001:8001"` con lo stesso commento); in `assistente`
  `CATALOGO_BASE_URL: http://catalogo:8001` (commento «raggiunto per nome di servizio») e
  `depends_on: [giorni, catalogo]` in forma a lista. `Dockerfile`: `COPY servizio_catalogo/
  servizio_catalogo/` dopo `servizio_giorni/` negli stage `test` e `app`.

- [ ] **Step 4: verifiche**:
  - `python -m pytest` → verde (3.13);
  - `docker compose --profile test run --rm --build test` → verde, stesso numero di test (3.14);
  - `docker compose up -d --build catalogo`, poi `curl.exe http://127.0.0.1:8001/salute` →
    `{"stato":"ok","articoli":32}`; `docker compose stop catalogo`.

- [ ] **Step 5: commit** `feat(catalogo): strumenti del catalogo nell'agente e servizio in Compose`.
  Nel resoconto: chiedere all'utente di aggiungere `CATALOGO_BASE_URL=http://127.0.0.1:8001` al
  `.env` locale (senza, l'avvio locale fallisce con «CATALOGO_BASE_URL mancante»).

---

### Task 6: prove reali e documentazione

**Files:**
- Modify: `tests/integration/test_lmstudio.py`, `README.md`, `docs/registro-test.md`,
  `Es.1/plan.md`, `tests/test-manuali.txt` (non versionato); `CLAUDE.md` solo dopo l'ok dell'utente

- [ ] **Step 1: test reale** `test_real_model_uses_catalog`: se `GET <CATALOGO_BASE_URL>/salute`
  fallisce → `pytest.fail("servizio catalogo non avviato: …")`; «Dove trovo il multimetro?» → un
  `ToolMessage` di `search_catalog` contiene `LAB-001` e la risposta contiene «Armadio A». Con i due
  servizi avviati: `$env:RUN_LMSTUDIO_TESTS = "1"; python -m pytest -m lmstudio -v` → 7 PASS.
  Commit `test(catalogo): prova reale dello strumento search_catalog`.
- [ ] **Step 2: serie a mano** della spec §7 con uno script usa e getta nella scratchpad
  (`create_graph` + `ask`, sessione nuova per tentativo, JSONL con strumenti chiamati, argomenti,
  risultati, risposta, errore), servizi avviati: 10 tentativi per ciascuna delle quattro domande
  della spec §1. Criteri: (1) `search_catalog` chiamato e risposta con «Armadio A, ripiano 1»;
  (2) `search_catalog` e «12» nella risposta; (3) `get_catalog_item` con codice `LAB-002`
  (maiuscole indifferenti) e risposta che cita il tecnico; (4) `search_catalog` chiamato e risposta
  senza codici `LAB-`, posizioni o quantità. Soglia 8/10 ciascuna. Esito negativo: si riporta, non
  si corregge senza accordo con l'utente.
- [ ] **Step 3: servizio catalogo spento**: 10 tentativi di «Dove trovo il multimetro?»; conteggio
  delle risposte con una posizione (armadio, cassettiera, banco, ripiano). Nessuna soglia: esito
  riportato all'utente.
- [ ] **Step 4: checklist in Docker** (`"Dove trovo il multimetro?", "esci" | docker compose run
  --rm -T --build assistente`): risposta con la posizione; poi `docker compose stop giorni catalogo`.
- [ ] **Step 5: documentazione**: README (variabile `CATALOGO_BASE_URL` nella tabella di
  configurazione, sezione «Strumenti del catalogo» con avvio locale e in Docker, file
  dell'inventario, testi d'esempio dai log reali, diagnosi: servizio non raggiungibile, porta 8001
  occupata; solo comandi eseguiti in questo piano); `docs/registro-test.md` (sessione con tutte le
  verifiche); `tests/test-manuali.txt` (voci del catalogo); proposta all'utente per `CLAUDE.md`
  (struttura con `servizio_catalogo/` e `catalog.py`, `CATALOGO_BASE_URL` obbligatoria, comando del
  servizio, porta 8001, servizio Compose `catalogo`, prove reali con entrambi i servizi) applicata
  solo dopo il suo ok; esito in `Es.1/plan.md`. Commit `docs: catalogo locale nel README e nei
  registri`.
- [ ] **Step 6:** revisione finale del branch, poi chiedere all'utente l'ok per il merge in `dev`.
  Push solo su richiesta, dopo la verifica completa rieseguita (suite 3.13 e 3.14, LM Studio,
  checklist Docker).

---

## Correzione dopo la revisione finale (aggiunta del 2026-11-08, da approvare)

Spec §9. Stesse Global Constraints.

### Task 7: un 404 estraneo su `/articolo` è una risposta non valida (spec §9.1)

**Files:**
- Modify: `assistente/catalog.py`, `README.md` (riga di Diagnosi), `docs/registro-test.md`
- Test: `tests/test_catalog.py`

- [ ] **Step 1: test che fallisce**: in `test_invalid_responses` il caso
  `("get_catalog_item", {"code": "LAB-001"}, json_response({"detail": "Not Found"}, 404), 404)`.
  `python -m pytest tests/test_catalog.py -v` → FAIL su quel caso (oggi `Errore: Not Found Usa …`).
- [ ] **Step 2: correzione** in `_call`: il ramo 404 vale solo se `detail` è una stringa che inizia
  con `NOT_FOUND_PREFIX = "nessun articolo con codice "` (costante in `catalog.py`); altrimenti
  `invalid`. `test_user_errors` e `test_contract_unknown_code` restano invariati e verdi.
- [ ] **Step 3: verifiche**: `python -m pytest` e `docker compose --profile test run --rm --build test`
  → verdi (482 passed, 7 skipped).
- [ ] **Step 4: documentazione**: nella riga di Diagnosi del README «risposta non valida dal servizio
  catalogo» vale per entrambi gli strumenti; esito nel registro e in `Es.1/plan.md`. Commit
  `fix(catalogo): un 404 estraneo non è un codice inesistente` e `docs: …`.
