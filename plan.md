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
- **Prova del 2026-11-03 (spike, solo `gemma-4-e2b`, la variante D con qwen esclusa
  dall'utente)**, eseguita con la calcolatrice già in `dev`; dettagli e testi delle varianti in
  `docs/registro-test.md`, sessione (5). Su 6 tentativi:
  - «Quanti kg sono 5 km?» → `convert_units`: prompt attuale 1, prompt con la regola «chiama anche
    se ovvio o impossibile» 2, stessa regola più la frase nella descrizione («se le unità sono di
    categorie diverse restituisce un errore: chiamalo comunque») **6**.
  - «Quante ore ci sono in 3 settimane?» → mai `convert_units`, ma sempre `calculate` con
    `3 * 7 * 24` → `504` (18/18): la risposta ora viene da uno strumento.
  - Controlli invariati (10/10 in ogni variante). Conclusione provvisoria: le ipotesi 1 e 2 non
    bastano a spiegare il caso (la regola nel prompt non aiuta), conta la descrizione dello
    strumento.
- **Resta da decidere:** provare la sola descrizione con il prompt attuale, se accettare
  `calculate` come strumento valido per «3 settimane in ore» nel criterio della spec, e la
  correzione come aggiunta approvata a spec e piano, insieme a quella della calcolatrice.
- **Prova del 2026-11-05 (spike, solo `gemma-4-e2b`)**, sessione (6) del registro: sole frasi
  nelle descrizioni con il prompt attuale. «Quanti kg sono 5 km?» → `convert_units`: prompt
  attuale 1/6, sole descrizioni 3/6. «3 settimane in ore» → `calculate` 504 in 12 su 12.
- **Decisione (2026-11-05):** variante C (regola nel prompt e frasi nelle descrizioni);
  «3 settimane in ore» con `calculate` e risultato 504 è accettato (spec §8). Esecuzione nei
  Task 8-9 del piano della calcolatrice, su `feat/calcolatrice-sicura`.

## 2026-11-03 — L4: calcolatrice sicura

Approvato il 2026-11-03 (esecuzione: Native). Spec: `L4/docs/superpowers/specs/2026-11-03-calcolatrice-sicura-design.md`.
Fonte: `L4/docs/superpowers/plans/2026-11-03-calcolatrice-sicura.md`.

**Esito (2026-11-03):** Task 1-3 completati (`a923f29`, `eb8f58d`, `5fe59a0`, `1891866`); revisione
finale (subagent): 0 critici, 1 importante (rumore dei float dopo somme e sottrazioni), 5 minori.
Aggiunta approvata (spec §7, Task 4-7): descrizione con «per» (`14458b6`), arrotondamento
(`f982b5a`), minori (`8c20ace`), `CLAUDE.md` (`8590ca5`). Verifica completa su `8590ca5`: suite
261 passed / 5 skipped su 3.13 e 3.14, LM Studio 5/5, Docker 2/2, «3,5 per 2» → `3.5 * 2` 6/6.
Resta aperto il punto «7 diviso 0» risposto a mente (sezione «Punti da chiarire»).

**Aggiunta del 2026-11-05** (spec §8, Task 8-9, approvata il 2026-11-05, esecuzione Native):
variante C per calcolatrice e convertitore, docs `dcd3ed4`. Esito (2026-11-05): prompt e
descrizioni `c1b7a22`, docs `ae57653`. Serie §8.5: «7 diviso 0» → `calculate` 10/10, «5 km → kg» →
`convert_units` 10/10, «3 settimane» → `calculate` 504 10/10, controlli 14/14. Suite 263/5 su 3.13 e
3.14.9, LM Studio 5/5, checklist Docker 8/8; revisione finale (subagent): 0 critici, 0 importanti,
2 minori. Punti da chiarire chiusi. Riunito in `dev` e pushato il 2026-11-05.

### Calcolatrice sicura — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** il modello può richiedere lo strumento locale `calculate`, che valuta un'espressione
aritmetica senza `eval` e restituisce il risultato o un testo `Errore: …`.

**Architecture:** nuovo modulo `assistente/arithmetic.py`: controlli sul testo, sostituzione dei
simboli alternativi, `ast.parse(..., mode="eval")`, controllo dell'albero con una lista bianca,
calcolo ricorsivo in float con i limiti; solleva `CalcError` con un `Problem` e non contiene testi
per il modello. `tools.py` aggiunge la funzione pura `calculate` (formato e testi d'errore) e
`make_calculator_tool`; `cli.py` registra lo strumento e lo cita nel prompt. Grafo, modello e
configurazione invariati.

**Tech Stack:** Python 3.13 (venv) e 3.14 (Docker), `ast` della libreria standard, LangGraph,
langchain-core, pytest. Nessuna dipendenza nuova.

**Spec:** `L4/docs/superpowers/specs/2026-11-03-calcolatrice-sicura-design.md` (estende le
specifiche precedenti, in particolare `2026-11-02-convertitore-unita-design.md`).

Tutti i comandi si eseguono da `Es.1/L4` in PowerShell con il venv attivo (`.\.venv\Scripts\Activate.ps1`).

#### Global Constraints

- Branch `feat/calcolatrice-sicura` (da `dev`); lavorare solo in `Es.1/L4` (più l'aggiunta del
  piano a `Es.1/plan.md`). Merge in `dev` solo dopo l'ok dell'utente; nessun push senza richiesta.
- Nessuna dipendenza nuova, nessuna variabile d'ambiente nuova; `graph.py`, `model.py`,
  `config.py`, `units.py`, `cities.py`, `Dockerfile`, `compose.yaml` invariati.
- Mai `eval`, `exec` o `compile` nel codice della calcolatrice.
- Limiti: `MAX_LENGTH = 200` caratteri; intervallo `MIN_ABS = 1e-15`, `MAX_ABS = 1e15` (estremi
  inclusi, più lo 0).
- Testi esatti dello strumento:
  - successo: `<espressione ricevuta senza spazi esterni> = <risultato>`, es. `(3.5 + 2) * 4 = 22`
  - vuota: `Errore: l'espressione è vuota.`
  - troppo lunga: `Errore: l'espressione supera i 200 caratteri.`
  - virgola: `Errore: usa il punto come separatore decimale (es. 3.5), non la virgola.`
  - carattere: `Errore: carattere non ammesso '<c>'. Ammessi: cifre, punto decimale, + - * / // % ^ **, parentesi.`
  - sintassi: `Errore: espressione non valida. Esempio corretto: '(3.5 + 2) * 4'.`
  - numero fuori intervallo: `Errore: i numeri devono essere 0 oppure, in valore assoluto, compresi tra 0.000000000000001 e 1000000000000000.`
  - divisione per zero: `Errore: divisione per zero.`
  - potenza non reale: `Errore: potenza non reale (base negativa con esponente non intero).`
  - troppo grande: `Errore: il risultato è troppo grande per essere rappresentato.`
  - troppo piccolo: `Errore: il risultato è troppo piccolo per essere rappresentato.`
- Descrizione esatta per il modello: `Calcola un'espressione aritmetica e restituisce il risultato. Operatori: + - * /, // (divisione intera), % (resto), ^ o ** (potenza), parentesi. Usa il punto per i decimali: se l'utente scrive 3,5 passa 3.5. Esempi: '(3.5 + 2) * 4', '2^10', '17 % 5'.`
- Frase esatta aggiunta in coda al prompt di sistema: `Per qualsiasi calcolo aritmetico, anche semplice, usa sempre lo strumento calculate e non fare il calcolo a mente.`
- Suite senza modello verde su 3.13 (`python -m pytest`) e 3.14
  (`docker compose --profile test run --rm --build test`) prima di ogni commit.
- Conventional Commits in italiano; `git status`, controllo del diff, staging selettivo; firma
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

#### Review Focus

- Il modello scrive `x` come segno di moltiplicazione (`3 x 4`): non è tra i simboli concordati,
  quindi deve dare l'errore del carattere `'x'`, che indica gli operatori ammessi, e non un
  errore di sintassi generico (Task 1).
- Il modello copia l'uguale finale della domanda (`1234 * 5678 =`): errore del carattere `'='`
  (Task 1).
- Cifre non ASCII, come l'apice `²` (`2²`) o le cifre arabo-indiane: `str.isdigit()` le accetta,
  quindi il controllo dei caratteri deve usare l'insieme esplicito `0123456789`. Esito: errore del
  carattere `'²'` (Task 1).
- Segni ripetuti (`2--3`, `--5`): Python li analizza come segni unari, il risultato è 5 e non un
  errore (Task 1).
- Spazio come separatore delle migliaia (`1 000 + 1`): non deve diventare `1000`, ma l'errore di
  espressione non valida; ultima cifra arrotondata correttamente (`2 / 3 = 0.666666666666667`)
  (Task 1 e Task 2).

---

##### Task 1: analisi e calcolo (`assistente/arithmetic.py`)

**Files:**
- Create: `assistente/arithmetic.py`
- Test: `tests/test_arithmetic.py`

**Interfaces:**
- Produces:
  - `Problem(Enum)` con i membri `EMPTY`, `TOO_LONG`, `COMMA`, `CHARACTER`, `SYNTAX`,
    `NUMBER_RANGE`, `DIVISION_BY_ZERO`, `NOT_REAL`, `TOO_BIG`, `TOO_SMALL`.
  - `CalcError(Exception)`: `CalcError(problem: Problem, char: str | None = None)`, con gli
    attributi `problem` e `char` (`char` valorizzato solo per `CHARACTER`).
  - `MAX_LENGTH = 200`, `MIN_ABS = 1e-15`, `MAX_ABS = 1e15`.
  - `evaluate(expression: str) -> float`: risultato finito nell'intervallo, oppure `CalcError`.

- [ ] **Step 1: Scrivere i test che falliscono** in `tests/test_arithmetic.py` (con
  `pytest.approx` per i risultati non interi):

```python
@pytest.mark.parametrize("expr, expected", [
    ("2 + 3 * 4", 14), ("(2 + 3) * 4", 20), ("((1 + 2) * (3 + 4))", 21),
    ("2^3^2", 512), ("2**3**2", 512), ("-2^2", -4), ("2^-1", 0.5),
    ("-7 // 2", -4), ("-7 % 3", 2), ("17 % 5", 2), ("7 / 2", 3.5),
    (".5 + 5.", 5.5), ("  1+1  ", 2), ("+3", 3), ("2--3", 5), ("--5", 5),
])
def test_operators_and_precedence(expr, expected): ...   # evaluate(expr) == expected

@pytest.mark.parametrize("alt, ascii_", [
    ("7 × 6", "7 * 6"), ("7 · 6", "7 * 6"), ("8 ÷ 2", "8 / 2"), ("8 : 2", "8 / 2"),
    ("5 − 3", "5 - 3"), ("2 ^ 10", "2 ** 10"),
])
def test_alternative_symbols(alt, ascii_): ...   # evaluate(alt) == evaluate(ascii_)

@pytest.mark.parametrize("expr, problem, char", [
    ("", Problem.EMPTY, None), ("   ", Problem.EMPTY, None),
    ("1+" * 100 + "1", Problem.TOO_LONG, None),          # 201 caratteri
    ("3,5 * 2", Problem.COMMA, None), ("abs(1,5)", Problem.COMMA, None),   # la virgola prima delle lettere
    ("abs(1)", Problem.CHARACTER, "a"), ("1e5", Problem.CHARACTER, "e"),
    ("0x10", Problem.CHARACTER, "x"), ("1_000", Problem.CHARACTER, "_"),
    ("__import__('os')", Problem.CHARACTER, "_"), ("3 x 4", Problem.CHARACTER, "x"),
    ("1234 * 5678 =", Problem.CHARACTER, "="), ("2²", Problem.CHARACTER, "²"),
    ("2 3", Problem.SYNTAX, None), ("3 +", Problem.SYNTAX, None), ("2****3", Problem.SYNTAX, None),
    ("()", Problem.SYNTAX, None), ("2(3+4)", Problem.SYNTAX, None), ("(1)(2)", Problem.SYNTAX, None),
    ("1 000 + 1", Problem.SYNTAX, None), ("1/0 + 2(3)", Problem.SYNTAX, None),  # sintassi prima del calcolo
    ("1000000000000001", Problem.NUMBER_RANGE, None), ("0.0000000000000001", Problem.NUMBER_RANGE, None),
    ("1 / 0", Problem.DIVISION_BY_ZERO, None), ("1 // 0", Problem.DIVISION_BY_ZERO, None),
    ("1 % 0", Problem.DIVISION_BY_ZERO, None), ("0^-1", Problem.DIVISION_BY_ZERO, None),
    ("(-8)^0.5", Problem.NOT_REAL, None),
    ("9^9^9", Problem.TOO_BIG, None), ("(10^8)^2 / 10^10", Problem.TOO_BIG, None),
    ("1000000000000000 + 1", Problem.TOO_BIG, None),
    ("0.5^10000", Problem.TOO_SMALL, None), ("0.000000000000001 / 10", Problem.TOO_SMALL, None),
])
def test_problems(expr, problem, char): ...   # pytest.raises(CalcError): .problem == problem, .char == char

def test_limits_are_inclusive():
    assert evaluate("1000000000000000") == 1e15
    assert evaluate("0.000000000000001") == 1e-15
    assert evaluate("0") == 0
    assert evaluate("1+" * 99 + "11") == 110   # esattamente 200 caratteri: accettata

def test_negative_base_with_integer_exponent():
    assert evaluate("(-2)^3") == -8
```

- [ ] **Step 2: Eseguire i test e verificare che falliscano**

Run: `python -m pytest tests/test_arithmetic.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'assistente.arithmetic'`).

- [ ] **Step 3: Implementare `assistente/arithmetic.py`**

  `evaluate` esegue, nell'ordine del §3 della spec:
  1. `text = expression.strip()`; vuota → `EMPTY`; `len(text) > MAX_LENGTH` → `TOO_LONG`;
     `","` in `text` → `COMMA`;
  2. sostituzione: `×`, `·` → `*`; `÷`, `:` → `/`; `−` → `-`; `^` → `**`;
  3. il primo carattere fuori da `set("0123456789.+-*/%() ")` → `CHARACTER` con quel carattere
     (insieme esplicito, non `str.isdigit()`);
  4. `ast.parse(text, mode="eval")`; `SyntaxError` → `SYNTAX`; poi un controllo dell'intero
     albero (tutti i nodi, prima di calcolare) con la lista bianca del §4 della spec
     (`Constant` int/float esclusi `bool`, `BinOp` con `Add Sub Mult Div FloorDiv Mod Pow`,
     `UnaryOp` con `UAdd USub`) → altrimenti `SYNTAX`;
  5. calcolo ricorsivo in float: `Constant` → `float(value)` e controllo `NUMBER_RANGE`;
     `UnaryOp` → segno, senza controlli; `BinOp` → sinistro, destro, poi:
     divisore 0 con `/ // %` → `DIVISION_BY_ZERO`; per `Pow`, prima base 0 con esponente
     negativo → `DIVISION_BY_ZERO`, base negativa con esponente non intero → `NOT_REAL`,
     `OverflowError` → `TOO_BIG`, base ≠ 0 con risultato 0 → `TOO_SMALL`; infine, per ogni
     operazione binaria, `abs(r) > MAX_ABS` → `TOO_BIG` e `r != 0 and abs(r) < MIN_ABS` →
     `TOO_SMALL`.

- [ ] **Step 4: Eseguire i test e verificare che passino**

Run: `python -m pytest tests/test_arithmetic.py -v`, poi `python -m pytest`
Expected: tutto PASS.

- [ ] **Step 5: Commit** — solo i due file:
  `feat(strumenti): analisi e calcolo sicuro delle espressioni aritmetiche`.

##### Task 2: strumento `calculate` (`assistente/tools.py`)

**Files:**
- Modify: `assistente/tools.py` (docstring del modulo; nuove costanti e funzioni in coda)
- Test: `tests/test_tools.py`, `tests/test_graph.py`

**Interfaces:**
- Consumes: `evaluate`, `CalcError`, `Problem` da Task 1.
- Produces:
  - `CALCULATOR_DESCRIPTION: str` (testo esatto in Global Constraints).
  - `calculate(expression: str) -> str`
  - `make_calculator_tool() -> BaseTool` con nome `calculate` e un solo parametro obbligatorio
    `expression` di tipo stringa.

- [ ] **Step 1: Scrivere i test che falliscono**

  In `tests/test_tools.py`:

```python
@pytest.mark.parametrize("expr, expected", [
    ("(3.5 + 2) * 4", "(3.5 + 2) * 4 = 22"), ("0.1 + 0.2", "0.1 + 0.2 = 0.3"),
    ("1 / 3", "1 / 3 = 0.333333333333333"), ("2 / 3", "2 / 3 = 0.666666666666667"),
    ("10 / 2", "10 / 2 = 5"), ("7 × 6", "7 × 6 = 42"), ("  2^10  ", "2^10 = 1024"),
    ("-0", "-0 = 0"), ("0 * -1", "0 * -1 = 0"),
    ("1000000000000000", "1000000000000000 = 1000000000000000"),
    ("0.000000000000001", "0.000000000000001 = 0.000000000000001"),
    ("1234 * 5678", "1234 * 5678 = 7006652"),
])
def test_calculate_format(expr, expected): ...   # calculate(expr) == expected

@pytest.mark.parametrize("expr, expected", [
    ("", <testo vuota>), ("1+" * 100 + "1", <testo troppo lunga>), ("3,5", <testo virgola>),
    ("3 x 4", <testo carattere con 'x'>), ("2 3", <testo sintassi>),
    ("1000000000000001", <testo numero fuori intervallo>), ("1 / 0", <testo divisione per zero>),
    ("(-8)^0.5", <testo potenza non reale>), ("9^9^9", <testo troppo grande>),
    ("0.5^10000", <testo troppo piccolo>),
])
def test_calculate_errors(expr, expected): ...   # <…> = i testi esatti delle Global Constraints

def test_calculator_tool_schema():
    fn = convert_to_openai_tool(make_calculator_tool())["function"]
    assert fn["name"] == "calculate"
    assert fn["description"] == CALCULATOR_DESCRIPTION
    assert set(fn["parameters"]["properties"]) == {"expression"}
    assert fn["parameters"]["required"] == ["expression"]
    assert "string" in json.dumps(fn["parameters"]["properties"]["expression"])
```

  In `tests/test_graph.py`, con l'helper esistente `single_call_result`:

```python
def test_calculator_call_returns_real_result():
    result = single_call_result("calculate", {"expression": "1234 * 5678"}, [clock, make_calculator_tool()])
    assert result == "1234 * 5678 = 7006652"
```

- [ ] **Step 2: Eseguire i test e verificare che falliscano**

Run: `python -m pytest tests/test_tools.py tests/test_graph.py -v`
Expected: FAIL (`ImportError` su `calculate` / `make_calculator_tool`).

- [ ] **Step 3: Implementare in `assistente/tools.py`**
  - un dizionario `Problem` → testo con i dieci testi esatti (quello di `CHARACTER` con `{char}`);
  - `_format_number(value: float) -> str`: `"0"` se `value == 0`, altrimenti
    `format(Decimal(format(value, ".15g")).normalize(), "f")` (15 cifre significative, niente
    notazione scientifica, niente zeri finali);
  - `calculate`: `f"{expression.strip()} = {_format_number(evaluate(expression))}"`, oppure il
    testo del `CalcError`;
  - `make_calculator_tool`, sullo stesso schema di `make_converter_tool`;
  - docstring del modulo: «Strumenti che il modello può richiedere: orologio, convertitore di
    unità e calcolatrice.»

- [ ] **Step 4: Eseguire i test e verificare che passino**

Run: `python -m pytest`
Expected: tutto PASS.

- [ ] **Step 5: Commit** — `assistente/tools.py`, `tests/test_tools.py`, `tests/test_graph.py`:
  `feat(strumenti): strumento calculate per le espressioni aritmetiche`.

##### Task 3: registrazione, prova reale e documentazione

**Files:**
- Modify: `assistente/cli.py` (`SYSTEM_PROMPT`, `make_tools`)
- Modify: `tests/test_cli.py`, `tests/integration/test_lmstudio.py`
- Modify: `README.md`, `docs/registro-test.md`, `CLAUDE.md` (dopo l'ok dell'utente)

**Interfaces:**
- Consumes: `make_calculator_tool()` da Task 2.
- Produces: `make_tools(settings)` restituisce, in quest'ordine, `get_current_time`,
  `convert_units`, `calculate`.

- [ ] **Step 1: Scrivere i test che falliscono** in `tests/test_cli.py`: il test esistente
  `test_tools_include_clock_and_converter` diventa `test_tools_include_all_local_tools` e si
  aspetta `["get_current_time", "convert_units", "calculate"]`; nuovo
  `test_system_prompt_mentions_calculator`: `"calculate" in SYSTEM_PROMPT`.

  In `tests/integration/test_lmstudio.py` (aggiungere `import re`):

```python
def test_real_model_uses_calculator(graph):
    history, reply = ask(graph, new_history(), "Quanto fa 1234 * 5678?")
    results = [m.content for m in history if isinstance(m, ToolMessage) and m.name == "calculate"]
    assert any("= 7006652" in r for r in results), results
    assert "7006652" in re.sub(r"[.\s'’]", "", reply), reply
```

- [ ] **Step 2: Eseguire i test e verificare che falliscano**

Run: `python -m pytest tests/test_cli.py -v`
Expected: FAIL sui due test nuovi/modificati.

- [ ] **Step 3: Implementare in `assistente/cli.py`**: `make_tools` aggiunge
  `make_calculator_tool()` in coda (docstring: «orologio, convertitore di unità e calcolatrice»);
  `SYSTEM_PROMPT` aggiunge in coda, dopo uno spazio, la frase esatta delle Global Constraints.

- [ ] **Step 4: Eseguire la suite su entrambe le versioni**

Run: `python -m pytest` e `docker compose --profile test run --rm --build test`
Expected: tutto PASS (i test `lmstudio` risultano skipped).

- [ ] **Step 5: Commit** — `assistente/cli.py`, `tests/test_cli.py`,
  `tests/integration/test_lmstudio.py`: `feat(cli): registra la calcolatrice e la cita nel prompt`.

- [ ] **Step 6: Prove reali** (LM Studio acceso con `google/gemma-4-e2b`)
  - `$env:RUN_LMSTUDIO_TESTS = "1"; python -m pytest -m lmstudio -v` → 5 test, tutti PASS
    attesi (gli esiti, anche negativi, si riportano senza correggerli di nascosto).
  - Serie a mano della spec §5, ogni domanda in una sessione nuova (`python -m assistente`, log a
    livello `INFO`), annotando chiamata sì/no, argomenti e risposta: «Quanto fa 1234 * 5678?»,
    «Quanto fa 3,5 per 2?», «Quanto fa 2 alla 10?», «Quanto fa 17 modulo 5?», «Quanto fa 7 diviso
    0?», «Quanto fa 2 + 2?», «Quanti chilometri sono 10 miglia?».
  - Docker: `"Quanto fa 1234 * 5678?", "esci" | docker compose run --rm -T --build assistente`.

- [ ] **Step 7: Documentazione**
  - README: sezione della calcolatrice (sintassi ammessa, esempi del §2, diagnosi con i testi
    d'errore), solo comandi eseguiti allo Step 6.
  - `docs/registro-test.md`: sessione con gli esiti dello Step 4 e dello Step 6, compresa
    l'osservazione sui calcoli facili.
  - `CLAUDE.md`: proporre all'utente la modifica della riga «Pacchetto `assistente/`»
    (`tools.py` (orologio, convertitore, calcolatrice), `arithmetic.py` (analisi e calcolo sicuro
    delle espressioni)) e applicarla solo dopo il suo ok.
  - Commit `docs: documenta la calcolatrice sicura`. Poi chiedere l'ok per il merge in `dev`.

#### Aggiunta del 2026-11-03: correzioni dopo la revisione finale

Approvata dall'utente il 2026-11-03 (spec §7).

##### Task 4: «per» nella descrizione (aggiunta del 2026-11-03, spec §7.1)

**Files:**
- Modify: `assistente/tools.py` (`CALCULATOR_DESCRIPTION`)
- Test: `tests/test_tools.py` (`test_calculator_description_is_exact`)

- [ ] **Step 1:** aggiornare `test_calculator_description_is_exact` al testo esatto del §7.1.
- [ ] **Step 2:** `python -m pytest tests/test_tools.py -v` → FAIL solo su quel test.
- [ ] **Step 3:** aggiornare `CALCULATOR_DESCRIPTION` al testo del §7.1.
- [ ] **Step 4:** `python -m pytest` → tutto PASS.
- [ ] **Step 5:** commit `feat(strumenti): la descrizione della calcolatrice spiega «per» e «diviso»`.
- [ ] **Step 6: Prova reale** (script usa e getta, una sessione nuova per domanda): 5 tentativi su
  «Quanto fa 3,5 per 2?» e 1 per ciascun controllo del §7.1, annotando chiamata, argomenti e
  risposta. Esito atteso: almeno 4 su 5 con una moltiplicazione, controlli invariati. Un esito
  negativo si riporta, non si corregge senza accordo.

##### Task 5: arrotondamento dopo somme e sottrazioni (spec §7.2)

**Files:**
- Modify: `assistente/arithmetic.py` (`_compute`)
- Test: `tests/test_arithmetic.py`, `tests/test_tools.py`

- [ ] **Step 1: test che falliscono**

```python
@pytest.mark.parametrize("expr, expected", [
    ("0.1 + 0.2 - 0.3", 0), ("1.1 - 1 - 0.1", 0), ("3 * 0.1 - 0.3", 0), ("100 * 1.1 - 110", 0),
    ("0.1 + 0.2", 0.3),                         # uguaglianza esatta, non approx
    ("1000000000000000 - 1", 999999999999999), ("999999999999999.5 - 0.5", 999999999999999),
])
def test_addition_noise_is_rounded(expr, expected): ...   # evaluate(expr) == expected
```

  In `tests/test_tools.py`, in `test_calculate_format`: `("0.1 + 0.2 - 0.3", "0.1 + 0.2 - 0.3 = 0")`,
  `("100 * 1.1 - 110", "100 * 1.1 - 110 = 0")`.

- [ ] **Step 2:** `python -m pytest tests/test_arithmetic.py tests/test_tools.py -v` → FAIL sui casi nuovi
  tranne `0.1 + 0.2` e i due interi (già corretti: restano come protezione).
- [ ] **Step 3:** in `_compute`, dopo `Add`/`Sub` e prima di `_check_range`: se almeno un operando
  non è intero, `round(result, 14 - Decimal(max(abs(left), abs(right))).adjusted())`.
- [ ] **Step 4:** `python -m pytest` → tutto PASS.
- [ ] **Step 5:** commit `fix(strumenti): la calcolatrice arrotonda il rumore dei float dopo somme e sottrazioni`.

##### Task 6: problemi minori della revisione (spec §7.3-7.5, §7.7)

**Files:**
- Modify: `assistente/arithmetic.py`, `assistente/tools.py` (messaggio del carattere), `CLAUDE.md`
- Test: `tests/test_arithmetic.py`, `tests/test_tools.py`, `tests/test_graph.py` (solo righe vuote)

- [ ] **Step 1: test che falliscono**

```python
@pytest.mark.parametrize("expr, expected", [
    ("05 + 3", 8), ("007", 7), ("00.5 + 1", 1.5), ("1.005 * 1000", 1005), ("0.05 * 100", 5),
    ("1 +\t2", 3), ("1\n+ 2", 3), ("6 // 4", 1), ("2^-1", 0.5),
])
def test_minor_fixes_values(expr, expected): ...   # evaluate(expr) == expected

@pytest.mark.parametrize("expr", ["6::4", "6÷÷4", "6××4", "6*·4", "1 000 + 1"])
def test_doubled_symbols_and_nbsp_are_syntax_errors(expr): ...   # CalcError, Problem.SYNTAX

def test_invisible_character_keeps_raw_char():   # evaluate("1​+2") → CHARACTER, char == "​"
```

  In `tests/test_tools.py`: `calculate("1​+2") == "Errore: carattere non ammesso 'U+200B'. Ammessi: cifre, punto decimale, + - * / // % ^ **, parentesi."`;
  `calculate("05 + 3") == "05 + 3 = 8"`.

- [ ] **Step 2:** `python -m pytest tests/test_arithmetic.py tests/test_tools.py -v` → FAIL sui casi nuovi.
- [ ] **Step 3:** in `evaluate`, dopo la virgola: ogni carattere con `isspace()` → spazio; ogni
  simbolo alternativo → ` <simbolo> ` (con spazi); controllo dei caratteri; poi
  `re.sub(r"(?<![\d.])0+(?=\d)", "", text)` per gli zeri iniziali; poi `_parse`. In `tools.py` il
  carattere non stampabile si scrive `U+%04X`.
- [ ] **Step 4:** togliere le due righe vuote in più prima di `test_calculator_call_returns_real_result`;
  `CLAUDE.md` come nel §7.7. `python -m pytest` → tutto PASS.
- [ ] **Step 5:** commit `fix(strumenti): zeri iniziali, spaziature e simboli raddoppiati nella calcolatrice`
  (codice e test) e `docs: struttura del pacchetto con la calcolatrice` (`CLAUDE.md`).

##### Task 7: verifica completa e documentazione

- [ ] Suite su 3.13 e 3.14 (`python -m pytest`, `docker compose --profile test run --rm --build test`).
- [ ] Prove reali `$env:RUN_LMSTUDIO_TESTS = "1"; python -m pytest -m lmstudio -v` → 5 PASS attesi.
- [ ] Serie a mano completa della spec §5 (una sessione per domanda) con la nuova descrizione.
- [ ] Docker: `"Quanto fa 1234 * 5678?", "esci" | docker compose run --rm -T --build assistente`.
- [ ] README (sintassi: zeri iniziali, spaziature, simboli raddoppiati; arrotondamento dopo somme e
  sottrazioni; esito della prova su «per» e riga di diagnosi aggiornata), `docs/registro-test.md`,
  esito in `Es.1/plan.md`. Commit `docs: ...`. Poi chiedere l'ok per il merge in `dev`.

#### Punti da chiarire (2026-11-03)

##### «7 diviso 0» riceve una risposta a mente invece di una chiamata a `calculate`

- **Osservato** con `google/gemma-4-e2b`: lo strumento viene chiamato 1 volta su 6 con la
  descrizione attuale e 1 su 5 con quella vecchia (1 su 1 nella prima serie). Le risposte senza
  chiamata sono corrette («la divisione per zero è indefinita») e nessuna inventa un risultato.
  In un tentativo il modello ha scritto la chiamata come testo
  (`calculate{expression:<|"|>7 / 0<|"|>}<tool_call|>`), che LM Studio non ha riconosciuto: il
  testo è arrivato all'utente come risposta.
- **Effetto:** il criterio del §1 della specifica («Quanto fa 7 diviso 0?» produce il testo
  d'errore dello strumento) non è raggiunto in modo affidabile. Tutte le altre domande di calcolo
  chiamano lo strumento, anche «2 + 2».
- **Ipotesi:** il modello «sa» che la divisione per zero è indefinita e non sente il bisogno dello
  strumento, come per «km → kg» nel convertitore (stesso schema, vedi il piano del convertitore).
- **Da decidere con l'utente:** se e come intervenire (prompt, descrizione, criterio della
  specifica), insieme al punto analogo del convertitore.
- **Prova del 2026-11-03 (spike, solo `gemma-4-e2b`)**, dettagli e testi delle varianti in
  `docs/registro-test.md`, sessione (5). Chiamate a `calculate` su 6 tentativi: prompt attuale 4,
  prompt con la regola «chiama anche se ovvio o impossibile» 2, stessa regola più la frase nella
  descrizione («se l'espressione non si può calcolare, es. divisione per zero, restituisce un
  errore: chiamalo comunque») **6**. Controlli invariati (10/10 in ogni variante), nessuna
  chiamata scritta come testo. Conclusione provvisoria: conta la descrizione dello strumento, non
  il prompt.
- **Resta da decidere:** provare la sola descrizione con il prompt attuale (modifica più piccola),
  poi la correzione come aggiunta approvata a spec e piano, insieme a quella del convertitore.
- **Prova del 2026-11-05 (spike, solo `gemma-4-e2b`)**, sessione (6) del registro: sole frasi
  nelle descrizioni con il prompt attuale (D), più il prompt attuale ripetuto come controllo (A).
  «7 diviso 0» → `calculate`: A 4/6, D 3/6 (più 1 chiamata scritta come testo e 2 errori 400 di
  LM Studio, «Failed to generate a tool call … timed out after 600000ms»). Le descrizioni da sole
  non bastano.
- **Decisione (2026-11-05):** si adotta la variante C (regola nel prompt e frasi nelle
  descrizioni) con l'aggiunta qui sotto (spec §8), su `feat/calcolatrice-sicura`, insieme al
  convertitore.

---

#### Aggiunta del 2026-11-05: chiamare lo strumento anche nei casi «impossibili»

Approvata dall'utente il 2026-11-05, esecuzione Native (spec §8). Vale anche per il convertitore (spec del convertitore §8): un solo
intervento su prompt e descrizioni, su `feat/calcolatrice-sicura`.

**Goal:** con `google/gemma-4-e2b`, «Quanto fa 7 diviso 0?» e «Quanti kg sono 5 km?» chiamano lo
strumento e riportano il suo errore, invece di rispondere a mente.

**Architecture:** solo testi. `SYSTEM_PROMPT` in `cli.py` riceve una frase finale (§8.2);
`CALCULATOR_DESCRIPTION` e `CONVERTER_DESCRIPTION` in `tools.py` ricevono una frase in coda (§8.3).
Codice degli strumenti, grafo, modello, configurazione, Docker invariati.

**Global Constraints dell'aggiunta** (oltre a quelle in cima, dove valgono):
- Testi esatti del §8.2 e §8.3, ciascuno aggiunto dopo uno spazio; le frasi già presenti non
  cambiano. La descrizione della calcolatrice in cima a questo piano è superata dal §7.1 e dal §8.3.
- Nessun file nuovo nel pacchetto, nessuna dipendenza, nessun test reale nuovo in
  `tests/integration` (un tentativo singolo non misura un comportamento che oscilla): la misura è
  la serie del §8.5.
- Solo `google/gemma-4-e2b` nelle prove reali.

**Review Focus dell'aggiunta:**
- La regola «usa gli strumenti anche quando la risposta ti sembra ovvia» non deve far chiamare
  strumenti per una domanda senza strumento: «Ciao, come stai?» → nessuna chiamata (Task 9).
- «Che ore sono a Miami?» deve restare `get_current_time` con `city`, non un calcolo (Task 9).
- «Quanto fa 3,5 per 2?» deve restare `3.5 * 2`: la descrizione allungata non deve far perdere la
  regola su «per» (Task 9).
- Una chiamata scritta come testo (`calculate{expression:<|"|>…`) va contata come insuccesso e
  riportata, non scartata (Task 9).
- Gli errori di LM Studio (400, tempo scaduto) si contano a parte: non vanno nascosti ripetendo
  il tentativo (Task 9).

##### Task 8: prompt e descrizioni (spec §8.2-8.3)

**Files:**
- Modify: `assistente/cli.py` (`SYSTEM_PROMPT`)
- Modify: `assistente/tools.py` (`CALCULATOR_DESCRIPTION`, `CONVERTER_DESCRIPTION`)
- Test: `tests/test_cli.py`, `tests/test_tools.py`

- [ ] **Step 1: aggiornare e aggiungere i test**
  - `tests/test_tools.py::test_calculator_description_is_exact`: testo attuale (§7.1) seguito da
    `" Se l'espressione non si può calcolare (per esempio una divisione per zero) restituisce un
    errore che spiega il motivo: chiamalo comunque, non rispondere a mente."`
  - nuovo `tests/test_tools.py::test_converter_description_is_exact`: `CONVERTER_DESCRIPTION ==`
    testo attuale del §2 del convertitore seguito da `" Se le unità sono di categorie diverse
    restituisce un errore che lo spiega: chiamalo comunque, non rispondere a mente."`
  - `tests/test_cli.py::test_system_prompt_mentions_calculator`: da `endswith` a `in` sulla stessa
    frase.
  - nuovo `tests/test_cli.py::test_system_prompt_asks_to_call_tools_anyway`:
    `SYSTEM_PROMPT.endswith(" Usa gli strumenti anche quando … è una conversione.")` con il testo
    esatto del §8.2.
- [ ] **Step 2:** `python -m pytest tests/test_cli.py tests/test_tools.py -v` → FAIL su tre dei
  quattro test del passo 1, per la coda mancante (`test_system_prompt_mentions_calculator` con
  `in` passa già).
- [ ] **Step 3:** aggiungere le frasi in `tools.py` e in `cli.py` (frammenti di stringa
  concatenati, come gli altri).
- [ ] **Step 4:** `python -m pytest` → tutto PASS (attesi 263 passed, 5 skipped: due test nuovi
  rispetto ai 261 attuali).
- [ ] **Step 5:** commit `feat(strumenti): calcolatrice e convertitore chiamati anche nei casi impossibili`
  (`git add assistente/cli.py assistente/tools.py tests/test_cli.py tests/test_tools.py`).

##### Task 9: serie reale, verifica completa e documentazione (spec §8.4-8.6)

- [ ] **Step 1: serie del §8.5** con uno script usa e getta nella scratchpad (non nel repo):
  `create_graph(load_settings())` e `ask(graph, new_history(), domanda)`, una sessione nuova per
  tentativo; 10 tentativi su «7 diviso 0», «5 km → kg», «3 settimane in ore», 2 per ciascun
  controllo; JSONL con chiamate, argomenti, risultati, risposta, chiamata scritta come testo,
  errore. Esito atteso: almeno 8/10 sulle tre domande, controlli invariati. Un esito negativo si
  riporta e si discute, non si corregge.
- [ ] **Step 2:** suite 3.13 (`python -m pytest`) e 3.14
  (`docker compose --profile test run --rm --build test`) → 263 passed, 5 skipped.
- [ ] **Step 3:** `$env:RUN_LMSTUDIO_TESTS = "1"; python -m pytest -m lmstudio -v` → 5 PASS.
- [ ] **Step 4:** checklist in Docker (`… | docker compose run --rm -T --build assistente`) con
  le domande della checklist precedente più «Quanto fa 7 diviso 0?» e «Quanti kg sono 5 km?».
- [ ] **Step 5: documentazione**: `docs/registro-test.md` (sessione (7): serie del §8.5 e
  verifica; la sessione (6) con lo spike del 5/11 è già scritta); README, righe di diagnosi su «7 diviso 0», «3 settimane» e sezioni dei
  due strumenti con l'esito; punti da chiarire dei due piani segnati come chiusi con l'esito;
  esito in `Es.1/plan.md` (fuori dai commit). Commit `docs: esito della correzione sui casi impossibili`.
- [ ] **Step 6:** chiedere all'utente l'ok per il merge in `dev` e se cancellare i due ledger
  (§8.6). Push solo su richiesta, dopo la verifica completa rieseguita.

## 2026-11-05 — L4: giorni e scadenze

Approvato il 2026-11-05 (commit del piano richiesto dall'utente); eseguito con Subagent-Driven Development
(scelta dell'utente), un implementatore e una revisione per task, revisione finale opus.
Spec: `L4/docs/superpowers/specs/2026-11-05-giorni-scadenze-design.md`.
Fonte: `L4/docs/superpowers/plans/2026-11-05-giorni-scadenze.md`.

**Esito (2026-11-05):** Task 1-6 eseguiti su `feat/giorni-scadenze` (`9823c65`…`d44cf4b`, prova
reale `2501ad2`, docs nel commit seguente). Suite 379 passed / 6 skipped su 3.13.14 e 3.14.9;
LM Studio 6/6 con il servizio avviato. Serie della spec §7 con `google/gemma-4-e2b` (60 tentativi,
nessuna chiamata scritta come testo, nessun errore di LM Studio): «Natale» → `days_between` 10/10,
«tra 30 giorni» → `add_days` 10/10, «10 giorni lavorativi» → `add_business_days` 10/10, «2 giugno
2027» → `date_info` 10/10, «30 febbraio» → `Errore:` dello strumento 9/10 (1 risposta a mente,
nessuna data inventata); controlli 2/2 ciascuno. Servizio spento: errore «non raggiungibile» e chat che
continua, ma il modello ha risposto comunque con un numero. Checklist Docker: 8 su 10 come atteso;
«7 diviso 0» e «5 km in kg» senza chiamata in una sessione lunga (da fresche: 9/10 e 10/10).
`CLAUDE.md` non modificato: proposta in attesa dell'ok dell'utente. Non ancora riunito in `dev`,
nessun push.

**Revisione finale (2026-11-05, subagent opus):** «mergeabile con correzioni». 0 critici, 3 importanti
(`_call` non cattura gli errori HTTP diversi dal trasporto; `localhost` → `::1` su Windows, circa 2 s
per chiamata; rischio `GG-MM` passato come `MM-GG`), 4 minori. L'utente ha scelto di correggere i
primi due: spec §9 e Task 7-8 qui sotto, approvati il 2026-11-06 (esecuzione inline). `CLAUDE.md`:
l'utente approva la proposta «con modifiche», da precisare: decisione rimandata a prima del merge.

### Giorni e scadenze — piano di implementazione

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

#### Global Constraints

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

#### Review Focus

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

##### Task 1: calendario e festività (`servizio_giorni/calendario.py`)

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

##### Task 2: dipendenze e app FastAPI (`servizio_giorni/app.py`)

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

##### Task 3: configurazione e strumenti client (`assistente/dates.py`)

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

##### Task 4: registrazione nell'agente

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

##### Task 5: Docker

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

##### Task 6: prove reali e documentazione

**Files:**
- Modify: `tests/integration/test_lmstudio.py`, `README.md`, `docs/registro-test.md`,
  `Es.1/plan.md`; `CLAUDE.md` solo dopo l'ok dell'utente

- [x] **Step 1: test reale** `test_real_model_uses_date_info` in `tests/integration/test_lmstudio.py`:
  se `GET <GIORNI_BASE_URL>/salute` fallisce → `pytest.fail("servizio giorni non avviato: …")`;
  «Il 2 giugno 2027 è festivo?» → un `ToolMessage` di `date_info` contiene `Festa della Repubblica`.
  Con il servizio avviato: `$env:RUN_LMSTUDIO_TESTS = "1"; python -m pytest -m lmstudio -v` → 6 PASS.
  Commit `test(strumenti): prova reale dello strumento date_info`.
- [x] **Step 2: serie a mano** della spec §7 con uno script usa e getta nella scratchpad
  (`create_graph` + `ask`, una sessione nuova per tentativo, JSONL con chiamate, argomenti,
  risultati, risposta, chiamata scritta come testo, errore), servizio avviato. Criterio: almeno
  8 su 10 per ciascuna delle quattro domande e per «30 febbraio»; controlli invariati. Esito
  negativo: si riporta, non si corregge senza accordo.
- [x] **Step 3: servizio spento**: una domanda sulle date con il servizio fermo → `risultato
  strumento: Errore: servizio giorni non raggiungibile a http://localhost:8000.` nei log e la
  chat continua con la domanda successiva.
- [x] **Step 4: checklist in Docker** (`… | docker compose run --rm -T --build assistente`): la
  checklist precedente più «Quanti giorni mancano a Natale?» e «Il 2 giugno 2027 è festivo?»;
  poi `docker compose stop giorni`.
- [x] **Step 5: documentazione**: README (servizio e strumenti, avvio in due terminali e in
  Docker, file delle festività, esempi dai log reali, diagnosi della spec §8, solo comandi
  eseguiti in questo piano); `docs/registro-test.md` (sessione con tutte le verifiche); proposta
  all'utente per `CLAUDE.md` (struttura con `servizio_giorni/` e `dates.py`, comando del
  servizio, `GIORNI_BASE_URL`) applicata solo dopo il suo ok; esito in `Es.1/plan.md`. Commit
  `docs: giorni e scadenze nel README e nei registri`.
- [ ] **Step 6:** chiedere all'utente l'ok per il merge in `dev`. Push solo su richiesta, dopo la
  verifica completa rieseguita (suite 3.13 e 3.14, LM Studio, checklist Docker).

#### Correzioni dopo la revisione finale (aggiunta del 2026-11-05)

Stato: proposta del 2026-11-05, **approvata** dall'utente il 2026-11-06 (esecuzione inline).

Spec §9. Stessi Global Constraints del piano. Suite attuale: 379 passed, 6 skipped.

##### Task 7: nessuna eccezione HTTP dagli strumenti (spec §9.1)

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

##### Task 8: indirizzo locale 127.0.0.1 e verifica (spec §9.2-9.3)

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

**Esito delle correzioni (2026-11-06, esecuzione inline):** Task 7 (`b2ef580`): `_call` trasforma
ogni `httpx.HTTPError` non di trasporto in `Errore: risposta non valida dal servizio giorni.`, test
`test_http_error_becomes_invalid_response` visto fallire (4 casi) e poi passare. Task 8 (`518f67a`):
`GIORNI_BASE_URL=http://127.0.0.1:8000` in `.env.example`, README e `.env` locale. Tempi di
`date_info` con il servizio acceso: `localhost` 2,0 s a ogni nuova connessione (chiamate a 6 s
l'una dall'altra: 2,05 / 2,02 / 2,03 s), `127.0.0.1` 0,00 s. Suite 383 passed / 6 skipped su 3.13 e
3.14.9; LM Studio 6/6 con il servizio acceso; servizio spento: errore «non raggiungibile a
http://127.0.0.1:8000» e chat che continua (il modello risponde ancora a mente). Restano annotati:
rischio `GG-MM`, risposta a mente col servizio spento, possibile ritardo di `LMSTUDIO_BASE_URL`;
checklist Docker da rifare nella verifica completa prima del push. Dettagli in
`L4/docs/registro-test.md`, sessione (9).

#### Aggiunte prima del merge in `dev` (2026-11-08)

Stato: proposta del 2026-11-08, **approvata** dall'utente il 2026-11-08 (esecuzione Native, inline).

Spec §10 (approvata il 2026-11-08). Stessi Global Constraints del piano. Suite attuale: 383 passed,
6 skipped; i Task 9-10 cambiano testi attesi di test esistenti, senza test nuovi, quindi le conte
restano 383/6. Serie sui modelli: solo `google/gemma-4-e2b`, script usa e getta nella scratchpad
(`create_graph` + `ask`, una sessione nuova per tentativo), esiti nel registro. Un esito sotto il
criterio si riporta all'utente e non si corregge senza accordo. Il servizio locale e quello Docker
non vanno mai avviati insieme; a fine prova la porta 8000 resta libera.

##### Task 9: il testo dei guasti del servizio chiede di non rispondere a mente (spec §10.1)

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

##### Task 10: `days_between` non aggiunge l'anno alle date senza anno (spec §10.3)

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

##### Task 11: fuso dei log in Docker e 127.0.0.1 per LM Studio (spec §10.2)

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

**Esito delle aggiunte (2026-11-08, esecuzione Native inline):**
- Task 9 (`664608e`): coda `Non è possibile calcolare il risultato: dillo all'utente e non
  calcolarlo a mente.` sui testi dei guasti del servizio e regola in coda al prompt (spec §10.1.1).
  Servizio spento: prima 0 su 8 senza numero, solo testo d'errore 0 su 5, testo + regola 7 su 10
  (criterio 8 su 10 mancato di uno, risultato accettato dall'utente). Esecuzione reale: risposta
  senza numero e chat che continua.
- Task 10: descrizione di `days_between` con «senza aggiungere tu l'anno» → 1 su 9 giusto (spike
  con la descrizione vecchia 8 su 10): annullata, nessun commit di codice (`69393e4`, spec §10.3.1).
  Spike sulle date ambigue: 0 scambi giorno/mese su 36.
- Task 11: `127.0.0.1` per LM Studio (`b677693`; prima connessione 2,04 s con `localhost`, 0,01 s
  con `127.0.0.1`) e `TZ: Europe/Rome` per i log del container (`20797c6`; timestamp verificato).
- Suite 384 passed / 6 skipped su 3.13.14 e 3.14.9; LM Studio 6/6 con il servizio acceso.
  Checklist in Docker: 8 su 10 come atteso («7 diviso 0» e «5 km in kg» senza chiamata in sessione
  lunga, come il 2026-11-05). Revisione finale (opus): «mergeable con correzioni», 1 importante
  corretto (stato della spec §10.1.1), 4 minori di documentazione lasciati aperti per scelta
  dell'utente. Restano: checklist con il terminale interattivo vero; circa 3
  su 10 risposte con un numero a servizio spento; anno aggiunto dal modello circa 2 su 10. Dettagli
  in `L4/docs/registro-test.md`, sessione (10), e in `L4/docs/registro-modifiche.md`. Riunito in
  `dev` (fast-forward) e pushato su richiesta dell'utente il 2026-11-08.

## 2026-11-08 — L4: catalogo locale

Approvato il 2026-11-08 (esecuzione: Native, revisione finale opus).
Spec: `L4/docs/superpowers/specs/2026-11-08-catalogo-locale-design.md`.
Fonte: `L4/docs/superpowers/plans/2026-11-08-catalogo-locale.md`.

**Esito (2026-11-08):** Task 1-6 eseguiti su `feat/catalogo-locale` (`830d35c`…`3dbcaf3`, prova
reale `60155c1`, docs nel commit seguente). Suite 481 passed / 6 skipped su 3.13.14 e 3.14.9;
LM Studio 7/7 con i servizi giorni e catalogo avviati. Serie della spec §7 con
`google/gemma-4-e2b` (40 tentativi, nessun errore, nessuna chiamata scritta come testo):
multimetro 10/10, Arduino Uno 10/10, scheda LAB-002 10/10, stampante 3D 10/10; servizio spento
0 posizioni inventate su 10. Checklist Docker: 2 domande del catalogo come atteso. Ruling: lista
delle parole vuote di 28 parole come nella spec (il piano diceva 30). Osservazione: il risultato a
più righe di `search_catalog` va a capo nella riga di log `risultato strumento` (`graph.py`
invariato). `CLAUDE.md` da aggiornare dopo l'ok dell'utente. Dettagli in
`L4/docs/registro-test.md`, sessione (11).

### Catalogo locale — piano di implementazione

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

#### Global Constraints

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

#### Review Focus

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

##### Task 1: inventario e validazione (`servizio_catalogo/inventario.py`, `inventario.json`)

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

##### Task 2: ricerca e dettaglio (`servizio_catalogo/inventario.py`)

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

##### Task 3: app FastAPI (`servizio_catalogo/app.py`)

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

##### Task 4: configurazione e strumenti client (`assistente/catalog.py`)

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

##### Task 5: registrazione nell'agente e Docker

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

##### Task 6: prove reali e documentazione

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
