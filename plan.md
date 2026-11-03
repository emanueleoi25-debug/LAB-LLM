# Piani approvati

## 2026-10-26 — L4: assistente con grafo LangGraph

Approvato il 2026-10-26. Spec: `L4/docs/superpowers/specs/2026-10-26-assistente-langgraph-design.md`.
Fonte: `L4/docs/superpowers/plans/2026-10-26-assistente-langgraph.md`.

### Assistente del laboratorio — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** chat da terminale in Python con grafo LangGraph esplicito, modello in LM Studio sull'host,
cronologia di sessione, strumento orologio con limite di passaggi, avvio con Docker Compose.

**Architecture:** pacchetto `assistente/` con moduli piccoli: `config` (variabili d'ambiente),
`tools` (orologio), `model` (ChatOpenAI verso LM Studio), `graph` (stato, nodi `modello` /
`strumenti` / `limite`, instradamento), `cli` (ciclo, cronologia, log). Il grafo riceve il modello
come parametro, così i test usano uno stub e non serve LM Studio.

**Tech Stack:** Python 3.13 (venv locale) e 3.14 (Docker), `langgraph`, `langchain-core`,
`langchain-openai`, `python-dotenv`, `tzdata`, `pytest`, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-10-26-assistente-langgraph-design.md`

#### Incrementi

| Incremento | Task | Risultato verificabile |
|---|---|---|
| 1. Grafo con risposta fissa | 1, 2 | `python -m assistente` risponde con un testo fisso passando dal grafo |
| 2. LM Studio e cronologia | 3, 4 | risposte reali dal modello, contesto conservato tra le domande |
| 3. Orologio e instradamento | 5, 6 | il modello chiede l'ora, il grafo esegue lo strumento, log e limite |
| 4. Docker Compose | 7 | app e test girano nel container con Python 3.14 |
| 5. Verifica completa | 8 | tutte le prove eseguite, README definitivo, resoconto |

Ogni task distingue:
- **Test senza modello**: `pytest`, girano con LM Studio spento.
- **Prove con LM Studio**: test `lmstudio` attivati con `RUN_LMSTUDIO_TESTS=1` e prove manuali.
- **Prove con Docker**: richiedono Docker Desktop attivo.

#### Global Constraints

- Radice del progetto `Es.1/L4`; ogni comando si esegue da lì. Non si toccano `L3/`, gli altri
  file di `Es.1/` (tranne `Es.1/plan.md`) e `Es.1/__pycache__/`, che non va mai messo in stage.
- Python locale 3.13 (`py -3.13`); immagine Docker `python:3.14.<patch>-slim`, con patch fissata nel Task 1.
- Codice compatibile con 3.13 e 3.14: vietati template string `t"..."`, `except A, B:` senza
  parentesi, `annotationlib`, introspezione manuale delle annotazioni. Codice sincrono.
- Dipendenze con `==`; prima di fissarle si verificano le wheel per cp313 (installazione locale)
  e per cp314 linux (`pip download`, vedi Task 1).
- Variabili d'ambiente: `LMSTUDIO_BASE_URL`, `LMSTUDIO_MODEL` (obbligatorie, senza default),
  `DEFAULT_TIMEZONE` (`Europe/Rome`), `MAX_TOOL_STEPS` (`3`), `LOG_LEVEL` (`INFO`).
- Chiave API passata a LM Studio: costante `lm-studio`, non configurabile.
- Log su stderr, formato `%(asctime)s %(levelname)s %(name)s: %(message)s`; `httpx`, `httpcore`,
  `openai` a WARNING. Risposte su stdout con prefisso `Assistente> `, prompt `Tu> `.
- Compose: `name: assistente-laboratorio`, servizi `assistente` e `test` (profilo `test`).
- Nomi interni solo con minuscole, cifre, `-`, `_`. Nei comandi PowerShell i percorsi assoluti
  vanno tra virgolette (il percorso contiene `Road to 10k`).
- Git: Conventional Commits in italiano; prima di ogni commit `git status`, `git diff`, staging
  selettivo; mai `.env`, `.venv`, cache; nessun push.
- README con soli comandi verificati, anche per PowerShell.
- Un task è chiuso solo se la suite passa su 3.13 **e** su 3.14. Fino al Task 7 la verifica su
  3.14 si fa con il comando ad hoc riportato sotto.

**Verifica ad hoc su 3.14** (senza modello, richiede Docker):
```powershell
docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v "${PWD}:/app" -w /app python:3.14.<patch>-slim sh -c "pip install -q -r requirements-dev.txt && python -m pytest -p no:cacheprovider"
```

#### Review Focus

1. Il modello passa il fuso con maiuscole o spazi diversi (`" asia/tokyo "`): ci si aspetta lo
   stesso risultato su Windows e su Linux, dove i file di zoneinfo distinguono maiuscole e minuscole → Task 5.
2. Il modello passa `timezone` vuoto o `null`: ci si aspetta il fuso predefinito, non un errore → Task 5.
3. Il modello passa argomenti malformati allo strumento (es. `{"timezone": ["Asia/Tokyo"]}`):
   ci si aspetta una `ToolMessage` d'errore, non un crash → Task 6.
4. Il modello risponde con testo vuoto e senza `tool_calls`: ci si aspetta un segnaposto
   leggibile, non una riga vuota → Task 2.
5. Ctrl+C mentre si attende la risposta: ci si aspetta un'uscita pulita senza traceback → Task 2.

---

#### Incremento 1 — Grafo con risposta fissa

##### Task 1: Preparazione del progetto e grafo minimo

**Files:**
- Delete: `main.py` (vuoto in HEAD)
- Create: `.gitignore`, `requirements.txt`, `requirements-dev.txt`, `pytest.ini`
- Create: `assistente/__init__.py`, `assistente/graph.py`, `assistente/model.py`
- Create: `tests/__init__.py`, `tests/fakes.py`, `tests/test_graph.py`, `tests/test_model.py`

**Interfaces:**
- Produces:
  - `assistente.graph.AssistantState` (TypedDict): `messages: Annotated[list[AnyMessage], add_messages]`, `tool_steps: int`
  - `assistente.graph.ChatModel` (Protocol): `invoke(messages: list[BaseMessage]) -> AIMessage`
  - `assistente.graph.build_graph(model: ChatModel) -> CompiledStateGraph`, con nodo `"modello"`
    e archi `START → modello → END`
  - `assistente.model.FIXED_REPLY: str` e `assistente.model.FixedReplyModel` (temporanei, rimossi nel Task 4)
  - `tests.fakes.ScriptedModel(responses: list[AIMessage | BaseException])`, con attributo
    `calls: list[list[BaseMessage]]`. `invoke` registra una copia dei messaggi e restituisce la
    risposta successiva; se la risposta è un'eccezione la solleva; a risposte esaurite solleva
    `AssertionError`.

- [x] **Step 1: Pulizia e `.gitignore`**

`git rm main.py`. Crea `.gitignore` con: `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `*.pyc`.

- [x] **Step 2: Crea il venv 3.13**

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version
```
Expected: `Python 3.13.x`

- [x] **Step 3: Scegli e verifica le versioni**

Per `langgraph`, `langchain-core` e `pytest` scegli l'ultima versione stabile
(`python -m pip index versions <pacchetto>`). Scrivi `requirements.txt` (`langgraph==…`,
`langchain-core==…`) e `requirements-dev.txt` (`-r requirements.txt`, `pytest==…`). Poi verifica:
```powershell
python -m pip install -r requirements-dev.txt
python -m pip download --only-binary=:all: --python-version 3.14 --implementation cp --platform manylinux_2_17_x86_64 -r requirements.txt -d "$env:TEMP\wheels314"
```
Expected: entrambi i comandi terminano senza errori. Se manca una wheel cp314, scegli la versione
più recente che le ha tutte. Nello stesso modo, nei Task 4 e 5, si aggiungono `langchain-openai`,
`python-dotenv` e `tzdata`.

- [x] **Step 4: Fissa l'immagine 3.14**

```powershell
docker pull python:3.14-slim
docker run --rm python:3.14-slim python --version
```
Annota `3.14.<patch>`: lo userai nella verifica ad hoc e nel `Dockerfile` (Task 7).

- [x] **Step 5: `pytest.ini`**

```ini
[pytest]
testpaths = tests
pythonpath = .
addopts = -ra
markers =
    lmstudio: prove reali che richiedono LM Studio attivo (RUN_LMSTUDIO_TESTS=1)
```

- [x] **Step 6: Scrivi i test che falliscono**

`tests/test_graph.py`:
```python
def test_reply_without_tool_calls_ends_after_one_model_call():
    model = ScriptedModel([AIMessage(content="Ciao!")])
    result = build_graph(model).invoke({"messages": [HumanMessage("Ciao")], "tool_steps": 0})
    assert len(model.calls) == 1
    assert [m.type for m in result["messages"]] == ["human", "ai"]
    assert result["messages"][-1].content == "Ciao!"

def test_model_receives_all_messages():
    model = ScriptedModel([AIMessage(content="ok")])
    build_graph(model).invoke({"messages": [SystemMessage("s"), HumanMessage("d")], "tool_steps": 0})
    assert [m.type for m in model.calls[0]] == ["system", "human"]

def test_graph_has_model_node():
    assert "modello" in build_graph(ScriptedModel([])).get_graph().nodes
```
`tests/test_model.py`:
```python
def test_fixed_reply_model_returns_constant():
    reply = FixedReplyModel().invoke([HumanMessage("x")])
    assert isinstance(reply, AIMessage) and reply.content == FIXED_REPLY
```

- [x] **Step 7: Verifica che falliscano**

Run: `python -m pytest -v`
Expected: FAIL per `ModuleNotFoundError: assistente.graph` / `assistente.model`.

- [x] **Step 8: Implementa `graph.py`, `model.py` e `tests/fakes.py`**

`FIXED_REPLY = "Risposta fissa: il collegamento al modello arriverà nel prossimo incremento."`
Il nodo `modello` restituisce `{"messages": [model.invoke(state["messages"])]}`.

- [x] **Step 9: Verifica su 3.13 e 3.14**

Run: `python -m pytest -v` e la verifica ad hoc su 3.14.
Expected: 4 passed in entrambi.

- [x] **Step 10: Commit**

```powershell
git add .gitignore requirements.txt requirements-dev.txt pytest.ini assistente tests
git commit -m "feat(grafo): crea il grafo minimo con risposta fissa"
```

##### Task 2: Ciclo da terminale con risposta fissa

**Files:**
- Create: `assistente/cli.py`, `assistente/__main__.py`, `tests/test_cli.py`, `README.md`
- Modify: `CLAUDE.md` (sezione struttura e comandi)

**Interfaces:**
- Consumes: `build_graph`, `FixedReplyModel` (Task 1), `ScriptedModel`
- Produces:
  - `assistente.cli.SYSTEM_PROMPT: str`, `EXIT_WORDS = {"esci", "exit"}`, `EMPTY_REPLY = "(nessuna risposta dal modello)"`
  - `new_history() -> list[BaseMessage]`: `[SystemMessage(SYSTEM_PROMPT)]`
  - `ask(graph, history: list[BaseMessage], question: str) -> tuple[list[BaseMessage], str]`:
    invoca il grafo con `{"messages": history + [HumanMessage(question)], "tool_steps": 0}` e
    restituisce i nuovi messaggi e il testo dell'ultima `AIMessage`
  - `run_chat(graph, history: list[BaseMessage] | None = None, input_fn: Callable[[str], str] = input, output: TextIO = sys.stdout, errors: TextIO = sys.stderr) -> list[BaseMessage]`:
    restituisce la cronologia finale
  - `configure_logging(level: str) -> None`
  - `main() -> int`; `__main__.py` esegue `raise SystemExit(main())`

- [x] **Step 1: Scrivi i test che falliscono**

In `tests/test_cli.py`, `inputs(*lines)` restituisce una `input_fn` che fornisce le righe in
ordine e poi solleva `EOFError`.
```python
@pytest.mark.parametrize("word", ["esci", "exit", "  Esci ", "EXIT"])
def test_exit_words_end_loop(word):
    model = ScriptedModel([])
    run_chat(build_graph(model), input_fn=inputs(word), output=io.StringIO())
    assert model.calls == []

@pytest.mark.parametrize("exc", [EOFError, KeyboardInterrupt])
def test_eof_and_ctrl_c_end_loop(exc): ...  # input_fn solleva exc → run_chat ritorna senza eccezioni

def test_blank_lines_are_ignored():  # inputs("", "   ", "esci") → model.calls == []

def test_reply_is_printed():
    out = io.StringIO()
    run_chat(build_graph(ScriptedModel([AIMessage("Ciao!")])), input_fn=inputs("Ciao", "esci"), output=out)
    assert "Assistente> Ciao!" in out.getvalue()

def test_history_is_kept_between_turns():
    model = ScriptedModel([AIMessage("uno"), AIMessage("due")])
    history = run_chat(build_graph(model), input_fn=inputs("a", "b", "esci"), output=io.StringIO())
    assert [m.type for m in model.calls[1]] == ["system", "human", "ai", "human"]
    assert len(history) == 5

def test_empty_reply_prints_placeholder():  # AIMessage("") → "Assistente> (nessuna risposta dal modello)"

def test_ctrl_c_while_waiting_exits_cleanly():  # ScriptedModel([KeyboardInterrupt()]) → run_chat ritorna
```

- [x] **Step 2: Verifica che falliscano**

Run: `python -m pytest tests/test_cli.py -v`
Expected: FAIL con `ModuleNotFoundError: assistente.cli`.

- [x] **Step 3: Implementa `cli.py` e `__main__.py`**

`SYSTEM_PROMPT = "Sei l'assistente del laboratorio. Rispondi in italiano, in modo breve e chiaro."`
Le parole d'uscita si confrontano dopo `strip().lower()`. Un'uscita, sia per parola sia per
EOF/Ctrl+C, stampa `Arrivederci.` su `output`. `configure_logging` usa
`logging.basicConfig(stream=sys.stderr, level=..., format=...)` con il formato dei Global
Constraints e porta `httpx`, `httpcore`, `openai` a WARNING. Per ora `main()` fa
`configure_logging("INFO")`, `run_chat(build_graph(FixedReplyModel()))` e `return 0`.

- [x] **Step 4: Verifica su 3.13 e 3.14**

Run: `python -m pytest -v` e la verifica ad hoc su 3.14.
Expected: tutti passed.

- [x] **Step 5: Prova manuale (senza modello)**

`python -m assistente`, scrivi `ciao` e poi `esci`.
Expected: `Assistente> Risposta fissa: …`, poi `Arrivederci.`, poi ritorno al prompt di PowerShell.

- [x] **Step 6: README e CLAUDE.md**

README: scopo, requisiti (Python 3.13 locale, Docker Desktop, LM Studio), preparazione del venv
(comandi degli Step 2 e 3 del Task 1), avvio `python -m assistente`, test `python -m pytest`.
CLAUDE.md: nuova sezione «Struttura e comandi» con i moduli di `assistente/`, il comando dei test
e la regola «suite verde su 3.13 e 3.14».

- [x] **Step 7: Commit**

```powershell
git add assistente/cli.py assistente/__main__.py tests/test_cli.py
git commit -m "feat(cli): aggiunge il ciclo da terminale con risposta fissa"
git add README.md CLAUDE.md
git commit -m "docs: documenta avvio e test del primo incremento"
```

---

#### Incremento 2 — Collegamento a LM Studio e cronologia

##### Task 3: Configurazione da variabili d'ambiente

**Files:**
- Create: `assistente/config.py`, `tests/test_config.py`, `.env.example`
- Modify: `requirements.txt` (`python-dotenv==…`, verificato come nel Task 1 Step 3)

**Interfaces:**
- Produces:
  - `assistente.config.ConfigError(Exception)`
  - `Settings` (dataclass frozen): `base_url: str`, `model: str`, `log_level: str = "INFO"`
    (il Task 5 aggiunge altri campi)
  - `load_settings(env: Mapping[str, str] | None = None) -> Settings`: con `env=None` chiama
    `load_dotenv(find_dotenv(usecwd=True), override=False)` e legge `os.environ`. I valori sono
    ripuliti con `strip()`; un valore vuoto conta come mancante. Tutti gli errori sono raccolti in un
    unico `ConfigError` che nomina ogni variabile coinvolta.

- [x] **Step 1: Scrivi i test che falliscono**

```python
BASE = {"LMSTUDIO_BASE_URL": "http://localhost:1234/v1", "LMSTUDIO_MODEL": "google/gemma-4-e2b"}

def test_missing_required_variables_are_named():
    with pytest.raises(ConfigError) as err:
        load_settings({})
    assert "LMSTUDIO_BASE_URL" in str(err.value) and "LMSTUDIO_MODEL" in str(err.value)

def test_blank_value_counts_as_missing():  # {**BASE, "LMSTUDIO_MODEL": "  "} → ConfigError con "LMSTUDIO_MODEL"

def test_values_are_read_and_stripped():
    s = load_settings({**BASE, "LMSTUDIO_MODEL": " google/gemma-4-e2b "})
    assert (s.base_url, s.model, s.log_level) == ("http://localhost:1234/v1", "google/gemma-4-e2b", "INFO")

def test_log_level_is_normalized_and_validated():
    assert load_settings({**BASE, "LOG_LEVEL": "debug"}).log_level == "DEBUG"
    with pytest.raises(ConfigError, match="LOG_LEVEL"):
        load_settings({**BASE, "LOG_LEVEL": "verbose"})

def test_environment_wins_over_dotenv(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("LMSTUDIO_BASE_URL=http://file/v1\nLMSTUDIO_MODEL=dal-file\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LMSTUDIO_MODEL", "dall-ambiente")
    monkeypatch.delenv("LMSTUDIO_BASE_URL", raising=False)
    s = load_settings()
    assert (s.base_url, s.model) == ("http://file/v1", "dall-ambiente")
```
`LOG_LEVEL` accetta `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`.

- [x] **Step 2: Verifica che falliscano** — `python -m pytest tests/test_config.py -v` → FAIL (modulo mancante)

- [x] **Step 3: Implementa `config.py`** e crea `.env.example` con `LMSTUDIO_BASE_URL=http://localhost:1234/v1`, `LMSTUDIO_MODEL=google/gemma-4-e2b`, `LOG_LEVEL=INFO`

- [x] **Step 4: Verifica su 3.13 e 3.14** — tutti passed

- [x] **Step 5: Commit**

```powershell
git add assistente/config.py tests/test_config.py .env.example requirements.txt
git commit -m "feat(config): legge la configurazione da variabili d'ambiente"
```

##### Task 4: Collegamento a LM Studio, controllo all'avvio, errori e cronologia reale

**Files:**
- Modify: `assistente/model.py` (rimuove `FixedReplyModel`/`FIXED_REPLY`, aggiunge il collegamento), `tests/test_model.py`
- Modify: `assistente/cli.py` (`main`, gestione degli errori del modello), `tests/test_cli.py`
- Modify: `requirements.txt` (`langchain-openai==…`, verificato come nel Task 1 Step 3)
- Create: `tests/integration/__init__.py`, `tests/integration/test_lmstudio.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `Settings`, `load_settings`, `ConfigError` (Task 3); `run_chat`, `ask`, `new_history` (Task 2)
- Produces:
  - `assistente.model.API_KEY = "lm-studio"`, `ModelCheckError(Exception)`
  - `list_models(base_url: str, timeout: float = 5.0) -> list[str]`: id da
    `openai.OpenAI(base_url=..., api_key=API_KEY, timeout=...).models.list()`
  - `check_model(settings: Settings, list_models_fn: Callable[[str], list[str]] = list_models) -> None`
  - `create_chat_model(settings: Settings, tools: Sequence[BaseTool] = ()) -> Runnable`: crea
    `ChatOpenAI(base_url=settings.base_url, api_key=API_KEY, model=settings.model)` e, se ci sono
    strumenti, applica `.bind_tools(tools)`

- [x] **Step 1: Scrivi i test che falliscono (senza modello)**

`tests/test_model.py` (elimina il test della risposta fissa). L'helper `settings(**overrides)`
crea `Settings(base_url="http://localhost:1234/v1", model="google/gemma-4-e2b")` con le sostituzioni indicate:
```python
def test_check_model_accepts_listed_model():
    check_model(settings(model="google/gemma-4-e2b"), lambda url: ["google/gemma-4-e2b", "altro"])

def test_check_model_lists_available_models():
    with pytest.raises(ModelCheckError) as err:
        check_model(settings(model="inventato"), lambda url: ["a/uno", "b/due"])
    msg = str(err.value)
    assert "inventato" in msg and "a/uno" in msg and "b/due" in msg and "http://localhost:1234/v1" in msg

def test_check_model_reports_unreachable_server():
    def down(url):
        raise openai.APIConnectionError(request=httpx.Request("GET", url))
    with pytest.raises(ModelCheckError, match="LM Studio"):
        check_model(settings(), down)

def test_create_chat_model_uses_settings():
    m = create_chat_model(settings())
    assert isinstance(m, ChatOpenAI) and m.model_name == "google/gemma-4-e2b"
    assert str(m.openai_api_base) == "http://localhost:1234/v1"
```
`tests/test_cli.py`:
```python
def test_model_error_discards_question_and_continues():
    err_conn = openai.APIConnectionError(request=httpx.Request("POST", "http://x"))
    model = ScriptedModel([err_conn, AIMessage("ok")])
    out, errs = io.StringIO(), io.StringIO()
    run_chat(build_graph(model), input_fn=inputs("prima", "seconda", "esci"), output=out, errors=errs)
    assert "Errore" in errs.getvalue()
    assert [m.type for m in model.calls[1]] == ["system", "human"]
    assert "Assistente> ok" in out.getvalue()

def test_main_fails_with_missing_config(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    for name in ("LMSTUDIO_BASE_URL", "LMSTUDIO_MODEL"):
        monkeypatch.delenv(name, raising=False)
    assert main() == 2
    assert "LMSTUDIO_BASE_URL" in capsys.readouterr().err
```

- [x] **Step 2: Verifica che falliscano** — `python -m pytest -v` → FAIL sui test nuovi

- [x] **Step 3: Implementa**

- `run_chat` intercetta `openai.APIError`, che comprende anche `APIConnectionError`, scrive su
  `errors` `Errore: il modello non ha risposto ({exc}). Domanda scartata, riprova.` e lascia la
  cronologia invariata.
- `main()`:
  - `load_settings()`; se solleva `ConfigError` → `Configurazione non valida: …` su stderr, `return 2`.
  - `configure_logging(settings.log_level)`.
  - `check_model(settings)`; se solleva `ModelCheckError` → messaggio su stderr, `return 1`.
  - `run_chat(build_graph(create_chat_model(settings)))`, poi `return 0`.
- Messaggi di `check_model`:
  - server irraggiungibile: `LM Studio non raggiungibile a {base_url}: avvia il server o controlla LMSTUDIO_BASE_URL.`
  - modello assente: `Modello '{model}' non disponibile su {base_url}. Modelli disponibili: {elenco}.`

- [x] **Step 4: Verifica su 3.13 e 3.14** — tutti passed

- [x] **Step 5: Prove reali con LM Studio (test)**

In `tests/integration/test_lmstudio.py` imposta `pytestmark = [pytest.mark.lmstudio, pytest.mark.skipif(os.environ.get("RUN_LMSTUDIO_TESTS") != "1", reason="prova reale: imposta RUN_LMSTUDIO_TESTS=1")]`.
La fixture `graph` esegue `load_settings()`, poi `check_model(settings)`, poi
`build_graph(create_chat_model(settings))`.
```python
def test_real_model_answers(graph):
    _, reply = ask(graph, new_history(), "Rispondi solo con la parola: pronto")
    assert reply.strip()

def test_real_model_remembers_previous_turn(graph):
    history, _ = ask(graph, new_history(), "Ricorda il numero 47. Rispondi solo: ok")
    _, reply = ask(graph, history, "Quale numero ti ho chiesto di ricordare?")
    assert "47" in reply
```
Run (LM Studio attivo, `.env` copiato da `.env.example`):
```powershell
$env:RUN_LMSTUDIO_TESTS = "1"; python -m pytest -m lmstudio -v; Remove-Item Env:RUN_LMSTUDIO_TESTS
```
Expected: 2 passed. Senza la variabile: 2 skipped.

- [x] **Step 6: Prove manuali con LM Studio**

1. `python -m assistente` con LM Studio attivo: una domanda riceve una risposta reale, e una
   domanda successiva che rimanda alla prima ne tiene conto.
2. Server LM Studio fermo: esce con codice 1 e il messaggio «LM Studio non raggiungibile…».
3. `LMSTUDIO_MODEL=inventato` nel `.env`: esce con codice 1 ed elenca i modelli disponibili.

- [x] **Step 7: README** — configurazione (`Copy-Item .env.example .env`), avvio del server di LM Studio, controllo all'avvio, prove reali (comando dello Step 5)

- [x] **Step 8: Commit**

```powershell
git add assistente/model.py assistente/cli.py tests/test_model.py tests/test_cli.py requirements.txt
git commit -m "feat(modello): collega LM Studio e conserva la cronologia di sessione"
git add tests/integration
git commit -m "test(modello): aggiunge le prove reali con LM Studio"
git add README.md
git commit -m "docs: documenta configurazione e prove con LM Studio"
```

---

#### Incremento 3 — Strumento orologio e instradamento

##### Task 5: Strumento orologio e configurazione relativa

**Files:**
- Create: `assistente/tools.py`, `tests/test_tools.py`
- Modify: `assistente/config.py`, `tests/test_config.py`, `.env.example`, `requirements.txt` (`tzdata==…`, verificato come nel Task 1 Step 3)

**Interfaces:**
- Produces:
  - `assistente.tools.utc_now() -> datetime` (aware, UTC)
  - `canonical_timezone(name: str) -> str | None`: nome IANA canonico. Applica `strip()`, poi
    cerca la corrispondenza esatta in `zoneinfo.available_timezones()`, poi quella senza
    distinzione tra maiuscole e minuscole; se non trova nulla restituisce `None`. L'insieme dei
    fusi è calcolato una sola volta (`functools.lru_cache`).
  - `current_time(timezone: str | None, default_timezone: str, now: datetime) -> str`
  - `make_clock_tool(default_timezone: str, clock: Callable[[], datetime] = utc_now) -> BaseTool`:
    strumento `@tool` chiamato `get_current_time` con parametro `timezone: str | None = None`.
    Descrizione: `"Restituisce la data e l'ora attuali. Parametro timezone: nome IANA del fuso orario, ad esempio 'Asia/Tokyo'. Se omesso usa il fuso predefinito."`
  - `Settings` acquista i campi `default_timezone: str = "Europe/Rome"` e `max_tool_steps: int = 3`

- [x] **Step 1: Scrivi i test che falliscono**

```python
NOW = datetime(2026, 10, 26, 16, 5, tzinfo=timezone.utc)
TOKYO = "2026-10-27T01:05:00+09:00 (Asia/Tokyo)"
ROME = "2026-10-26T17:05:00+01:00 (Europe/Rome)"

def test_time_in_requested_zone(): assert current_time("Asia/Tokyo", "Europe/Rome", NOW) == TOKYO

@pytest.mark.parametrize("tz", [None, "", "   "])
def test_missing_zone_uses_default(tz): assert current_time(tz, "Europe/Rome", NOW) == ROME

def test_zone_name_is_case_and_space_insensitive():
    assert current_time(" asia/tokyo ", "Europe/Rome", NOW) == TOKYO

@pytest.mark.parametrize("tz", ["Marte/Base", "../etc/passwd"])
def test_unknown_zone_returns_error_text(tz):
    assert current_time(tz, "Europe/Rome", NOW).startswith(f"Errore: fuso orario sconosciuto '{tz}'")

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
```
Messaggio d'errore completo: `Errore: fuso orario sconosciuto '{tz}'. Usa un nome IANA come 'Europe/Rome'.`
`tests/test_config.py`:
```python
def test_tool_defaults():
    s = load_settings(BASE)
    assert (s.default_timezone, s.max_tool_steps) == ("Europe/Rome", 3)

@pytest.mark.parametrize("value", ["0", "-1", "tre"])
def test_invalid_max_tool_steps(value):
    with pytest.raises(ConfigError, match="MAX_TOOL_STEPS"):
        load_settings({**BASE, "MAX_TOOL_STEPS": value})

def test_default_timezone_is_validated_and_canonical():
    assert load_settings({**BASE, "DEFAULT_TIMEZONE": "europe/rome"}).default_timezone == "Europe/Rome"
    with pytest.raises(ConfigError, match="DEFAULT_TIMEZONE"):
        load_settings({**BASE, "DEFAULT_TIMEZONE": "Marte/Base"})
```

- [x] **Step 2: Verifica che falliscano** — FAIL (modulo `assistente.tools` mancante, campi assenti)

- [x] **Step 3: Implementa `tools.py` ed estendi `config.py`**

`current_time` formatta l'ora con `now.astimezone(ZoneInfo(nome)).isoformat(timespec="seconds")`
seguita da ` (nome)`. `config.py` usa `canonical_timezone` per validare `DEFAULT_TIMEZONE`.
Aggiungi `DEFAULT_TIMEZONE=Europe/Rome` e `MAX_TOOL_STEPS=3` a `.env.example`.

- [x] **Step 4: Verifica su 3.13 e 3.14** — tutti passed. Su 3.14 il `test_tool_schema` controlla la differenza di comportamento delle annotazioni (PEP 649).

- [x] **Step 5: Commit**

```powershell
git add assistente/tools.py assistente/config.py tests/test_tools.py tests/test_config.py .env.example requirements.txt
git commit -m "feat(strumenti): aggiunge l'orologio con fuso orario esplicito"
```

##### Task 6: Nodi strumenti e limite, instradamento, log

**Files:**
- Modify: `assistente/graph.py`, `tests/test_graph.py`, `tests/test_model.py`
- Modify: `assistente/cli.py` (`SYSTEM_PROMPT`, collegamento in `main`)
- Modify: `tests/integration/test_lmstudio.py`, `README.md`

**Interfaces:**
- Consumes: `make_clock_tool` (Task 5), `Settings.default_timezone`, `Settings.max_tool_steps`, `create_chat_model(settings, tools)` (Task 4)
- Produces:
  - `build_graph(model: ChatModel, tools: Sequence[BaseTool] = (), max_tool_steps: int = 3) -> CompiledStateGraph`
    con nodi `"modello"`, `"strumenti"`, `"limite"` e instradamento come nella spec §6
  - `TOOL_SKIPPED = "non eseguito: limite di passaggi raggiunto"`
  - `LIMIT_REPLY = "Mi fermo: ho raggiunto il limite di {max_tool_steps} passaggi con gli strumenti. Prova a riformulare la domanda."`
  - logger `logging.getLogger("assistente.graph")`
  - ogni `ToolMessage` prodotta ha `name=<nome strumento>` e il `tool_call_id` della chiamata

- [x] **Step 1: Scrivi i test che falliscono**

`call(name, args, id)` costruisce un dizionario `tool_call`; `clock = make_clock_tool("Europe/Rome", clock=lambda: NOW)`.
```python
def test_tool_call_runs_tool_and_returns_result_to_model():
    model = ScriptedModel([AIMessage("", tool_calls=[call("get_current_time", {"timezone": "Asia/Tokyo"}, "c1")]), AIMessage("Sono le 01:05")])
    result = build_graph(model, [clock]).invoke({"messages": [HumanMessage("ora a Tokyo?")], "tool_steps": 0})
    sent = model.calls[1][-1]
    assert isinstance(sent, ToolMessage) and sent.tool_call_id == "c1" and sent.content == TOKYO
    assert result["messages"][-1].content == "Sono le 01:05" and result["tool_steps"] == 1

def test_parallel_tool_calls_count_as_one_step():  # c1 e c2 nella stessa AIMessage → 2 ToolMessage, tool_steps == 1

def test_limit_stops_the_loop():
    always = [AIMessage("", tool_calls=[call("get_current_time", {}, f"c{i}")]) for i in range(3)]
    model = ScriptedModel(always)
    result = build_graph(model, [clock], max_tool_steps=2).invoke({"messages": [HumanMessage("x")], "tool_steps": 0})
    tools = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(model.calls) == 3
    assert [m.content for m in tools].count(TOOL_SKIPPED) == 1 and len(tools) == 3
    assert result["messages"][-1].content == LIMIT_REPLY.format(max_tool_steps=2)
    asked = {c["id"] for m in result["messages"] if isinstance(m, AIMessage) for c in m.tool_calls}
    assert asked == {m.tool_call_id for m in tools}

def test_limit_is_logged_as_warning(caplog): ...  # stesso scenario, un record WARNING di "assistente.graph"

def test_unknown_tool_returns_error():  # name "meteo" → ToolMessage "Errore: strumento sconosciuto 'meteo'."

def test_tool_exception_returns_error():  # @tool boom che solleva RuntimeError("rotto") → content inizia con "Errore durante l'esecuzione di boom" e contiene "rotto"

def test_malformed_tool_args_return_error():  # {"timezone": ["Asia/Tokyo"]} → content inizia con "Errore durante l'esecuzione di get_current_time"

def test_tool_calls_are_logged(caplog):
    # scenario del primo test, caplog a INFO
    assert "strumento richiesto: get_current_time {'timezone': 'Asia/Tokyo'}" in caplog.text
    assert f"risultato strumento: {TOKYO}" in caplog.text

def test_history_after_tool_turn_is_valid_for_next_turn():
    # ask() due volte con lo stesso grafo: al secondo turno il modello riceve
    # ["system", "human", "ai", "tool", "ai", "human"]
```
`tests/test_model.py`:
```python
def test_create_chat_model_binds_clock_tool():
    bound = create_chat_model(settings(), [make_clock_tool("Europe/Rome")])
    assert bound.kwargs["tools"][0]["function"]["name"] == "get_current_time"
```

- [x] **Step 2: Verifica che falliscano** — FAIL (nuovi nodi e costanti assenti)

- [x] **Step 3: Implementa**

- Nodo `strumenti`:
  - per ogni chiamata registra `logger.info("strumento richiesto: %s %s", name, args)`;
  - esegue lo strumento con `tool.invoke(args)`;
  - registra `logger.info("risultato strumento: %s", result)`.
  - Un'eccezione dà il testo `Errore durante l'esecuzione di {name}: {exc}`; uno strumento
    sconosciuto dà `Errore: strumento sconosciuto '{name}'.`
  - Restituisce `tool_steps + 1`.
- Nodo `limite`: `logger.warning("limite di passaggi raggiunto (%d)", max_tool_steps)`.
- `SYSTEM_PROMPT` diventa:
  `"Sei l'assistente del laboratorio. Rispondi in italiano, in modo breve e chiaro. Per conoscere la data o l'ora attuali usa sempre lo strumento get_current_time e non inventarle."`
- In `main` crea `tools = [make_clock_tool(settings.default_timezone)]`, poi
  `build_graph(create_chat_model(settings, tools), tools, settings.max_tool_steps)`.

- [x] **Step 4: Verifica su 3.13 e 3.14** — tutti passed

- [x] **Step 5: Prova reale con LM Studio (test)**

```python
def test_real_model_uses_clock_tool(graph):
    history, reply = ask(graph, new_history(), "Che ore sono adesso a Tokyo?")
    assert any(isinstance(m, ToolMessage) and m.name == "get_current_time" for m in history)
    assert reply.strip()
```
La fixture `graph` ora usa gli strumenti, come `main`. Run: il comando del Task 4 Step 5 → 3 passed.
Se `google/gemma-4-e2b` non chiama lo strumento, **non** si cambia il modello né il prompt di
nascosto: si riporta l'esito e si decide insieme.

- [x] **Step 6: Prova manuale con LM Studio**

`python -m assistente`:
1. «Che ore sono a Tokyo?»: su stderr compaiono `strumento richiesto: get_current_time …` e
   `risultato strumento: …`, e la risposta è coerente con l'ora reale.
2. «E a Roma?»: il modello usa di nuovo lo strumento e il contesto della domanda precedente.
3. Con `LOG_LEVEL=WARNING` le righe dello strumento non compaiono più.

- [x] **Step 7: README** — strumento orologio, formato dei log, `LOG_LEVEL`, `MAX_TOOL_STEPS` e comportamento al limite

- [x] **Step 8: Commit**

```powershell
git add assistente/graph.py assistente/cli.py tests/test_graph.py tests/test_model.py
git commit -m "feat(grafo): instrada le chiamate allo strumento con limite di passaggi"
git add tests/integration/test_lmstudio.py
git commit -m "test(strumenti): verifica l'uso reale dell'orologio con LM Studio"
git add README.md
git commit -m "docs: documenta orologio, log e limite di passaggi"
```

---

#### Incremento 4 — Docker Compose

##### Task 7: Immagine, Compose e test su Python 3.14

**Files:**
- Create: `Dockerfile`, `compose.yaml`, `.dockerignore`
- Modify: `README.md`, `CLAUDE.md` (comandi Docker e test su 3.14)

**Interfaces:**
- Consumes: `python -m assistente`, `python -m pytest`, `assistente.model.list_models`

- [x] **Step 1: `Dockerfile` multi-stage**

Stage `base` (`python:3.14.<patch>-slim`, tag del Task 1 Step 4): `PYTHONUNBUFFERED=1`,
`PYTHONDONTWRITEBYTECODE=1`, `WORKDIR /app`, copia `requirements.txt`, poi
`pip install --no-cache-dir -r requirements.txt`.
Stage `test` (da `base`): installa `requirements-dev.txt`, copia `pytest.ini`, `assistente/` e
`tests/`, `CMD ["python", "-m", "pytest", "-p", "no:cacheprovider"]`.
Stage `app` (da `base`, **ultimo**, quindi predefinito): copia `assistente/`, crea un utente non
root e lo usa, `CMD ["python", "-m", "assistente"]`.

- [x] **Step 2: `compose.yaml` e `.dockerignore`**

Valori della spec §10: `name: assistente-laboratorio`; servizio `assistente` (`target: app`, `env_file: .env`,
`LMSTUDIO_BASE_URL: http://host.docker.internal:1234/v1`, `extra_hosts`, `stdin_open`, `tty`);
servizio `test` (`target: test`, `profiles: ["test"]`).
`.dockerignore`: `.env`, `.venv`, `__pycache__`, `.pytest_cache`, `docs`, `.git`.

- [x] **Step 3: Verifiche senza modello (Docker attivo)**

```powershell
docker compose config --quiet
docker compose build
docker compose --profile test run --rm --build test
docker compose run --rm assistente python --version
docker compose run --rm assistente python -c "import pytest"
docker compose run --rm assistente sh -c "ls -a /app"
```
Expected, nell'ordine:
- il primo comando non dà errori e il progetto si chiama `assistente-laboratorio`;
- la build riesce;
- i test passano su 3.14, con gli `lmstudio` in stato skipped;
- la versione stampata è `Python 3.14.<patch>`;
- `import pytest` fallisce con `ModuleNotFoundError`;
- `/app` contiene solo `assistente` e `requirements.txt`, senza `.env` né `tests`.

- [x] **Step 4: Prova con Docker e LM Studio**

```powershell
docker compose run --rm assistente python -c "import os; from assistente.model import list_models; print(list_models(os.environ['LMSTUDIO_BASE_URL']))"
```
Expected: l'elenco contiene `google/gemma-4-e2b`. Se il container non raggiunge LM Studio, attiva
«Serve on Local Network» in LM Studio, ripeti il comando e annota l'esito nel README.

- [x] **Step 5: README e CLAUDE.md**

README: sezione Docker con i comandi dello Step 3 effettivamente verificati e la diagnosi dello Step 4.
CLAUDE.md: comando dei test su 3.14, che sostituisce quello ad hoc.

- [x] **Step 6: Commit**

```powershell
git add Dockerfile compose.yaml .dockerignore
git commit -m "feat(docker): avvia l'applicazione e i test con Docker Compose"
git add README.md CLAUDE.md
git commit -m "docs: documenta avvio e test con Docker"
```

---

#### Incremento 5 — Verifica completa

##### Task 8: Verifica finale e resoconto

**Files:**
- Modify: `README.md` (diagnosi e checklist definitiva)

- [x] **Step 1: Suite senza modello su entrambe le versioni**

`python -m pytest -v` e `docker compose --profile test run --rm --build test` → tutti passed,
`lmstudio` skipped.

- [x] **Step 2: Allineamento delle dipendenze**

```powershell
python -m pip freeze > "$env:TEMP\freeze-313.txt"
docker compose run --rm assistente python -m pip freeze > "$env:TEMP\freeze-314.txt"
Compare-Object (Get-Content "$env:TEMP\freeze-313.txt") (Get-Content "$env:TEMP\freeze-314.txt")
```
Expected: le uniche differenze sono le dipendenze di sviluppo (`pytest`, `pluggy`, `iniconfig`…)
e quelle solo per Windows (`colorama`). Ogni altra differenza va spiegata, oppure la versione
corrispondente va fissata in `requirements.txt`.

- [x] **Step 3: Prove reali con LM Studio** — comando del Task 4 Step 5 → 3 passed

- [x] **Step 4: Checklist manuale in Docker (spec §11)**

`docker compose run --rm assistente`:
1. «Che ore sono a Tokyo?»: compare il log della chiamata e la risposta è coerente.
2. «Quale città ti ho chiesto prima?»: la risposta cita Tokyo.
3. `esci`, poi un nuovo avvio e «Quale città ti ho chiesto prima?»: il modello non lo sa.
4. LM Studio fermo: il messaggio di errore è chiaro e l'uscita avviene con codice 1.

- [x] **Step 5: README definitivo**

Sezione «Diagnosi»: LM Studio non raggiungibile in locale e da Docker, modello non disponibile,
variabile mancante, fuso orario non valido. Rileggi il README e tieni solo comandi eseguiti in
questo piano.

- [x] **Step 6: Commit e resoconto**

```powershell
git add README.md
git commit -m "docs: completa diagnosi e verifica finale nel README"
```
Resoconto all'utente: cosa è stato eseguito, con quale esito (anche per gemma con lo strumento) e
cosa resta da provare a mano. Nessun push.

## 2026-10-29 — L4: orologio per città e log dei messaggi

Approvato il 2026-10-29. Spec: `L4/docs/superpowers/specs/2026-10-29-orologio-citta-log-design.md`.
Fonte: `L4/docs/superpowers/plans/2026-10-29-orologio-citta-log.md`.

**Esito (2026-11-02):** completato e pushato (`8cddce3`, `5df730f`, `e4211fa`, `220f277`,
`28b82d8`). La revisione finale ha trovato un problema importante: il nome alternativo di una
città più grande copriva quello di un'altra città. È stato corretto in `220f277` e restano 8
problemi minori rimandati. Verifica finale su `220f277`: suite 83 superati / 3 skipped su 3.13 e
3.14, LM Studio 3/3, checklist Docker 4/4, città 20/20 (San Francisco riuscita al secondo
tentativo dopo un `Channel Error` di LM Studio). Dettagli in `L4/docs/registro-test.md`.

### Orologio per città e log dei messaggi — piano di implementazione

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

#### Global Constraints

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

#### Review Focus

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

##### Task 1: Ricerca delle città e strumento con il parametro `city`

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

##### Task 2: Log dei messaggi scambiati con il modello

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

##### Task 3: Documentazione, registri e verifica completa

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

## 2026-11-02 — L4: convertitore di unità

Approvato il 2026-11-02. Spec: `L4/docs/superpowers/specs/2026-11-02-convertitore-unita-design.md`.
Fonte: `L4/docs/superpowers/plans/2026-11-02-convertitore-unita.md`.

**Esito (2026-11-03):** Task 1-4 completati, riunito in `dev` e pushato su `origin/dev` (`3a45050`).
Commit: `de7422c`, `7f1d819`, `11c6039`, `4a7b950`; revisione finale: `ce9b45c` (risultati piccoli
≠ 0 mostrati 0.00), Task 4 intervallo gestito (`945d3cf`, `7f451bb`, `a59ed58`); punto da chiarire
registrato in `3a45050`. Verifica completa su `3a45050`: suite 150 passed / 4 skipped su 3.13 e
3.14, LM Studio 4/4, checklist Docker 5/5. Resta aperto il punto «Il modello calcola a mente invece
di chiamare `convert_units`» (sezione «Punti da chiarire»).

### Convertitore di unità — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** il modello può richiedere lo strumento locale `convert_units`, che converte un valore tra
due unità di un elenco chiuso e restituisce un errore per unità sconosciute o incompatibili.

**Architecture:** nuovo modulo `assistente/units.py` con la tabella delle unità e la conversione
affine (`scale`, `offset`) verso l'unità base; `tools.py` aggiunge la funzione pura
`convert_units` (controlli, formato, testi d'errore) e il factory `make_converter_tool`; `cli.py`
registra lo strumento e lo cita nel prompt di sistema. Grafo, modello e configurazione invariati.

**Tech Stack:** Python 3.13 (venv) e 3.14 (Docker), LangGraph, langchain-core, pytest. Nessuna
dipendenza nuova.

**Spec:** `L4/docs/superpowers/specs/2026-11-02-convertitore-unita-design.md` (estende
`2026-10-26-assistente-langgraph-design.md` e `2026-10-29-orologio-citta-log-design.md`).

Tutti i comandi si eseguono da `Es.1/L4` in PowerShell con il venv attivo (`.\.venv\Scripts\Activate.ps1`).

#### Global Constraints

- Branch `feat/convertitore-unita` (da `dev`); lavorare solo in `Es.1/L4` (più l'aggiunta del
  piano a `Es.1/plan.md`). Merge in `dev` solo dopo l'ok dell'utente; nessun push senza richiesta.
- Nessuna dipendenza nuova, nessuna variabile d'ambiente nuova; `graph.py`, `model.py`,
  `config.py`, `Dockerfile`, `compose.yaml` invariati.
- Tabella delle unità esattamente come nel §3 della specifica (simboli, `scale`, `offset`,
  sinonimi, ordine delle categorie: lunghezza, massa, volume, temperatura, velocità, tempo).
- Testi esatti dello strumento:
  - successo: `<valore> <simbolo da> = <risultato> <simbolo a> (<categoria>)`, es. `10 mi = 16.09 km (lunghezza)`
  - unità sconosciuta: `Errore: unità sconosciuta '<nome ricevuto>'. Unità ammesse: <ELENCO>`
  - incompatibili: `Errore: unità incompatibili: '<simbolo da>' è <articolo> <categoria>, '<simbolo a>' è <articolo> <categoria>.`
  - zero assoluto: `Errore: <valore> <simbolo> è sotto lo zero assoluto.`
  - valore non finito: `Errore: il valore deve essere un numero finito.`
- `<ELENCO>` esatto: `lunghezza (mm, cm, m, km, in, ft, yd, mi); massa (mg, g, kg, t, oz, lb); volume (ml, cl, l, m³, gal, fl oz); temperatura (°C, °F, K); velocità (m/s, km/h, mph, kn); tempo (s, min, h, d, wk).`
- Articoli: una lunghezza, una massa, un volume, una temperatura, una velocità, un tempo.
- Suite senza modello verde su 3.13 (`python -m pytest`) e 3.14
  (`docker compose --profile test run --rm --build test`) prima di ogni commit.
- Conventional Commits in italiano; `git status`, controllo del diff, staging selettivo; firma
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

#### Review Focus

- Il modello scrive °C con l'indicatore ordinale `º` (tastiera italiana) o con uno spazio
  (`° C`), o mette un punto finale (`lb.`, `km.`): l'unità va riconosciuta → normalizzazione in
  `find_unit` (Task 1).
- −459.67 °F e −273.15 °C sono esattamente lo zero assoluto: vanno accettati e danno `0.00 K`,
  non un errore né `-0.00` per il rumore dei float (Task 1 e Task 2).
- Il modello passa il valore come stringa (`"10"`): la validazione dello schema lo converte e la
  conversione riesce (Task 2).
- Un risultato che supera il massimo dei float (`1e308 km` → `mm`) non deve stampare `inf` →
  `Errore: il risultato è troppo grande per essere rappresentato.` (Task 2; testo non previsto
  dalla specifica, aggiunto qui).
- Sinonimo scritto con maiuscole miste e spazi interni multipli (`Chilometri  All'Ora`) → `km/h`
  (Task 1).

---

##### Task 1: tabella delle unità (`assistente/units.py`)

**Files:**
- Create: `assistente/units.py`
- Test: `tests/test_units.py`

**Interfaces:**
- Produces:
  - `Unit`: `@dataclass(frozen=True)` con `symbol: str`, `category: str`, `scale: float`,
    `offset: float = 0.0`, `aliases: tuple[str, ...] = ()`.
  - `UNITS: tuple[Unit, ...]` nell'ordine del §3; `category` vale esattamente `"lunghezza"`,
    `"massa"`, `"volume"`, `"temperatura"`, `"velocità"`, `"tempo"`.
  - `find_unit(name: str) -> Unit | None`
  - `to_base(unit: Unit, value: float) -> float` (`value × scale + offset`)
  - `from_base(unit: Unit, base: float) -> float` (`(base − offset) ÷ scale`)

- [ ] **Step 1: Scrivere i test che falliscono** in `tests/test_units.py`:

```python
@pytest.mark.parametrize("name, symbol", [
    ("km", "km"), ("Chilometri", "km"), ("  MIGLIA ", "mi"), ("°c", "°C"), ("celsius", "°C"),
    ("K", "K"), ("kelvin", "K"), ("fl oz", "fl oz"), ("oz", "oz"), ("m3", "m³"), ("nodi", "kn"),
    ("settimane", "wk"), ("km/h", "km/h"), ("chilometri all'ora", "km/h"),
    ("ºC", "°C"), ("° C", "°C"), ("lb.", "lb"), ("Chilometri  All'Ora", "km/h"),
])
def test_find_unit(name, symbol):
    assert find_unit(name).symbol == symbol

@pytest.mark.parametrize("name", ["parsec", "", "   "])
def test_unknown_unit_is_none(name):
    assert find_unit(name) is None

def test_names_are_unique():          # simboli e sinonimi, normalizzati, senza ripetizioni
def test_categories_in_order():       # ordine di prima comparsa == le 6 categorie del §3
def test_one_base_unit_per_category():# per categoria, esattamente un'unità con scale 1 e offset 0

@pytest.mark.parametrize("value, src, dst, expected", [
    (1, "mi", "km", 1.609344), (1, "lb", "kg", 0.45359237), (1, "gal", "l", 3.785411784),
    (100, "°C", "°F", 212), (0, "K", "°C", -273.15), (1, "kn", "km/h", 1.852), (1, "wk", "h", 168),
    (-459.67, "°F", "K", 0),
])
def test_reference_conversions(value, src, dst, expected):
    base = to_base(find_unit(src), value)
    assert from_base(find_unit(dst), base) == pytest.approx(expected, abs=1e-9)
```

- [ ] **Step 2: Eseguire i test e verificare che falliscono**

Run: `python -m pytest tests/test_units.py -v`
Expected: errore di collezione `ModuleNotFoundError: No module named 'assistente.units'`

- [ ] **Step 3: Implementare `assistente/units.py`**

Tabella `UNITS` copiata dal §3 della specifica (°F: `scale=5/9`, `offset=273.15 - 32 * 5 / 9`;
km/h: `1 / 3.6`; kn: `1852 / 3600`). Indice nome → unità costruito una volta, a livello di
modulo, su simboli e sinonimi normalizzati. Normalizzazione dei nomi (usata sia per l'indice sia
per la ricerca):

```python
def _normalize(name: str) -> str:
    text = " ".join(name.replace("º", "°").casefold().split())
    return text.replace("° ", "°").rstrip(".")
```

- [ ] **Step 4: Eseguire i test e verificare che passano**

Run: `python -m pytest tests/test_units.py -v`
Expected: tutti PASS

- [ ] **Step 5: Suite completa su 3.13 e 3.14**

Run: `python -m pytest` poi `docker compose --profile test run --rm --build test`
Expected: nessun fallimento su entrambe (3 skipped: le prove LM Studio)

- [ ] **Step 6: Commit**

```bash
git add assistente/units.py tests/test_units.py
git commit -m "feat(strumenti): tabella chiusa delle unità di misura"
```

##### Task 2: strumento `convert_units` e registrazione nella CLI

**Files:**
- Modify: `assistente/tools.py` (docstring del modulo; nuove `convert_units`, `make_converter_tool`, `CONVERTER_DESCRIPTION`)
- Modify: `assistente/cli.py:16-21` (prompt), `assistente/cli.py:86-89` (`create_graph`)
- Test: `tests/test_tools.py`, `tests/test_graph.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `Unit`, `UNITS`, `find_unit`, `to_base`, `from_base` (Task 1).
- Produces:
  - `convert_units(value: float, from_unit: str, to_unit: str) -> str`
  - `make_converter_tool() -> BaseTool` con nome `convert_units` e descrizione esatta del §2
    della specifica.
  - `make_tools(settings: Settings) -> list[BaseTool]` in `cli.py`: `[orologio, convertitore]`,
    usata da `create_graph`.

- [ ] **Step 1: Scrivere i test che falliscono**

`tests/test_tools.py`:

```python
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
    # name == "convert_units"; properties == {"value", "from_unit", "to_unit"};
    # required contiene tutti e tre; "number" in json.dumps(properties["value"])
```

`tests/test_graph.py`: `test_converter_call_returns_real_result` — con
`single_call_result("convert_units", {"value": 10, "from_unit": "miglia", "to_unit": "km"}, [clock, make_converter_tool()])`
il contenuto è `"10 mi = 16.09 km (lunghezza)"`.

`tests/test_cli.py`:
- `test_tools_include_clock_and_converter`: con
  `settings = Settings(base_url="http://localhost:1234/v1", model="m")`,
  `[t.name for t in make_tools(settings)] == ["get_current_time", "convert_units"]`;
- `test_system_prompt_mentions_converter`: `"convert_units" in SYSTEM_PROMPT`.

- [ ] **Step 2: Eseguire i test e verificare che falliscono**

Run: `python -m pytest tests/test_tools.py tests/test_graph.py tests/test_cli.py -v`
Expected: errore di collezione `ImportError: cannot import name 'convert_units'`

- [ ] **Step 3: Implementare in `assistente/tools.py`**

`convert_units` esegue i controlli nell'ordine della specifica (valore non finito → unità
sconosciuta da/a → categorie diverse → `round(to_base(...), 9) < 0` per la temperatura) e poi il
controllo del risultato non finito. Formattazione:

```python
def _format_input(value: float) -> str:            # 10.0 → "10", 1e-7 → "0.0000001", -0.0 → "0"
    text = format(Decimal(repr(value)).normalize(), "f")
    return "0" if text in ("-0", "0") else text

def _format_result(value: float) -> str:
    value = round(value, 12)                        # elimina il rumore dei float (−459.67 °F → 0)
    if value == 0:
        return "0.00"
    if round(value, 2) == 0:                         # 2 cifre significative, senza notazione scientifica
        return f"{value:.{1 - math.floor(math.log10(abs(value)))}f}"
    return f"{value:.2f}"
```

`make_converter_tool` usa `tool("convert_units", description=CONVERTER_DESCRIPTION)` su una
funzione interna `convert_units(value: float, from_unit: str, to_unit: str) -> str` (stesso
schema dell'orologio). Docstring del modulo: «Strumenti che il modello può richiedere: orologio e
convertitore di unità.»

- [ ] **Step 4: Aggiornare `assistente/cli.py`**

`make_tools(settings)` restituisce `[make_clock_tool(settings.default_timezone), make_converter_tool()]`;
`create_graph` la usa. In coda a `SYSTEM_PROMPT`: «Per convertire unità di misura usa sempre lo
strumento convert_units e non fare il calcolo a mente.»

- [ ] **Step 5: Eseguire i test e verificare che passano**

Run: `python -m pytest tests/test_tools.py tests/test_graph.py tests/test_cli.py -v`
Expected: tutti PASS

- [ ] **Step 6: Suite completa su 3.13 e 3.14**

Run: `python -m pytest` poi `docker compose --profile test run --rm --build test`
Expected: nessun fallimento su entrambe

- [ ] **Step 7: Commit**

```bash
git add assistente/tools.py assistente/cli.py tests/test_tools.py tests/test_graph.py tests/test_cli.py
git commit -m "feat(strumenti): converte unità di misura su richiesta del modello"
```

##### Task 3: prove reali e documentazione

**Files:**
- Modify: `tests/integration/test_lmstudio.py`
- Modify: `README.md`, `CLAUDE.md` (struttura), `docs/registro-test.md`

**Interfaces:**
- Consumes: `create_graph`, `ask`, `new_history` (esistenti), strumento `convert_units` (Task 2).

- [ ] **Step 1: Prova reale in `tests/integration/test_lmstudio.py`**

`test_real_model_uses_converter`: `ask(graph, new_history(), "Quanti chilometri sono 10 miglia?")`;
tra i `ToolMessage` con `name == "convert_units"` almeno uno contiene `"16.09 km"`, e `"16.09"`
compare nella risposta (accettare anche `"16,09"`).

- [ ] **Step 2: Eseguire le prove reali** (LM Studio acceso con il modello di `.env`)

Run: `$env:RUN_LMSTUDIO_TESTS = "1"; python -m pytest -m lmstudio -v`
Expected: 4 passed. Un fallimento si riporta all'utente così com'è, senza simulare.

- [ ] **Step 3: Serie a mano**, una sessione nuova per domanda, con `LOG_LEVEL=INFO`
(`"<domanda>" | python -m assistente`), annotando la riga `← modello [chiamata] convert_units …`
e la risposta:
«Quanti chilometri sono 10 miglia?», «Quanti gradi Fahrenheit sono 30 gradi Celsius?»,
«Quanti kg sono 150 libbre?», «Quanti km/h sono 20 nodi?», «Quante ore ci sono in 3 settimane?»,
«Quanti kg sono 5 km?» (atteso: errore dello strumento riportato, nessuna conversione inventata).

- [ ] **Step 4: Docker**

Run: `docker compose --profile test run --rm --build test`, poi
`docker compose run --rm --build assistente` con «Quanti chilometri sono 10 miglia?» ed `esci`.
Expected: suite senza fallimenti; nei log `convert_units` e risultato `16.09 km`.

- [ ] **Step 5: Documentazione**

- README: nuova sezione «Strumento convertitore di unità» dopo quella dell'orologio (parametri,
  tabella delle categorie con i simboli, formato del risultato con esempi, i cinque errori),
  voce nella checklist di verifica completa, righe di diagnosi «unità sconosciuta» e «unità
  incompatibili». Solo comandi eseguiti negli step 2-4.
- `CLAUDE.md`, «Struttura e comandi»: `tools.py` (orologio, convertitore) e
  `units.py` (tabella delle unità e conversione).
- `docs/registro-test.md`: nuova sessione con data, commit, esiti degli step 2-4 (argomenti
  passati dal modello per ogni domanda della serie).

- [ ] **Step 6: Commit**

```bash
git add tests/integration/test_lmstudio.py
git commit -m "test(strumenti): prova reale del convertitore con LM Studio"
git add README.md CLAUDE.md docs/registro-test.md
git commit -m "docs: documenta il convertitore di unità e le verifiche"
```

- [ ] **Step 7: Resoconto all'utente** con che cosa è stato eseguito, esiti e che cosa resta da
provare; richiesta dell'ok per il merge di `feat/convertitore-unita` in `dev`.

##### Task 4: intervallo gestito (aggiunta del 2026-11-03)

Approvato il 2026-11-03 dopo la revisione finale (minori: valori estremi con centinaia di cifre,
`1e306 km → km` «troppo grande», `-273.15 °C → K` senza test). Spec: §7.

**Files:**
- Modify: `assistente/tools.py` (costanti `_MIN_ABS = 1e-15`, `_MAX_ABS = 1e15`; controlli 2, 6, 7 del §7)
- Test: `tests/test_tools.py`
- Docs: `README.md` (tabella degli errori), `docs/registro-test.md`

- [ ] **Step 1: Test che falliscono** in `tests/test_tools.py`:
  - `test_value_out_of_range`: `(1e16, "m", "km")`, `(-1e16, "m", "km")`, `(1e-16, "m", "km")`,
    `(1e306, "km", "km")` → `Errore: il valore deve essere 0 oppure, in valore assoluto, compreso tra 0.000000000000001 e 1000000000000000.`
  - casi nuovi in `test_convert_units`: `(1e15, "m", "m", "1000000000000000 m = 1000000000000000.00 m (lunghezza)")`,
    `(1e-15, "m", "m", "0.000000000000001 m = 0.0000000000000010 m (lunghezza)")`,
    `(-273.15, "°C", "K", "-273.15 °C = 0.00 K (temperatura)")`;
  - `test_result_too_large`: `convert_units(1e14, "km", "mm")` (sostituisce `1e308`, ora respinto in entrata);
  - `test_result_too_small`: `convert_units(1e-10, "mg", "t")` → `Errore: il risultato è troppo piccolo per essere rappresentato.`
- [ ] **Step 2: Eseguirli** — Run: `python -m pytest tests/test_tools.py -v`. Expected: falliscono
  `test_value_out_of_range` e `test_result_too_small`; `-273.15 °C`, gli estremi e `1e14 km → mm` possono già passare.
- [ ] **Step 3: Implementare** i controlli nell'ordine del §7; il controllo sul risultato non finito
  è sostituito da quello sul massimo.
- [ ] **Step 4: Suite completa su 3.13 e 3.14** — `python -m pytest` e
  `docker compose --profile test run --rm --build test`. Expected: nessun fallimento.
- [ ] **Step 5: Commit** `fix(strumenti): limita il convertitore a un intervallo di valori rappresentabili`.
- [ ] **Step 6: Documentazione** — README: righe d'errore per valore fuori intervallo e risultato
  troppo piccolo, «risultato oltre i limiti» riferito a 1e15; registro dei test: sessione con gli
  esiti. Commit `docs: documenta l'intervallo gestito del convertitore`.

#### Punti da chiarire (2026-11-03)

##### Il modello calcola a mente invece di chiamare `convert_units`

- **Osservato** con `google/gemma-4-e2b` e il prompt attuale. «Quante ore ci sono in 3 settimane?»
  e «Quanti kg sono 5 km?» non hanno mai prodotto una chiamata allo strumento (0 su 4 ciascuna,
  più 3 su 3 senza chiamata nella prova interrotta). Le risposte sono corrette e nessuna inventa
  una conversione tra km e kg. Con «Converti 3 settimane in ore» e «Converti 5 km in kg» la chiamata
  avviene (2 su 2 ciascuna). Le altre domande della serie chiamano lo strumento (4 su 4).
- **Effetto:** il criterio di successo del §1 della specifica («Quanti kg sono 5 km?» produce il
  testo d'errore dello strumento) non è raggiunto con la domanda originale.
- **Ipotesi da verificare:**
  1. la domanda non sembra una conversione, perché non contiene «convertire» né unità scritte
     come simboli, e il prompt dice di usare lo strumento solo «per convertire»;
  2. il modello sa già che km e kg sono incompatibili e il prompt non gli chiede di chiamare lo
     strumento anche in quel caso;
  3. è un limite del modello piccolo e non del testo del prompt.
- **Prova proposta, non ancora eseguita:** varianti A (prompt attuale), B (usare lo strumento per
  qualsiasi quantità con un'unità, anche se il calcolo è facile), C (B più: chiamarlo anche con
  unità che sembrano incompatibili) e D (A con `qwen/qwen3.8-27b`). Per ciascuna, 4 tentativi sulle
  due domande e 2 sulle domande di controllo («10 miglia in km», «Che ore sono a Miami?», «Ciao,
  come stai?»).
- **Da decidere con l'utente:** quando eseguire la prova, la correzione (prompt, descrizione dello
  strumento o criterio della specifica) e se il punto blocca il merge di `feat/convertitore-unita`
  in `dev`.
