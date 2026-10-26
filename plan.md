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

- [ ] **Step 1: Pulizia e `.gitignore`**

`git rm main.py`. Crea `.gitignore` con: `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `*.pyc`.

- [ ] **Step 2: Crea il venv 3.13**

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version
```
Expected: `Python 3.13.x`

- [ ] **Step 3: Scegli e verifica le versioni**

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

- [ ] **Step 4: Fissa l'immagine 3.14**

```powershell
docker pull python:3.14-slim
docker run --rm python:3.14-slim python --version
```
Annota `3.14.<patch>`: lo userai nella verifica ad hoc e nel `Dockerfile` (Task 7).

- [ ] **Step 5: `pytest.ini`**

```ini
[pytest]
testpaths = tests
pythonpath = .
addopts = -ra
markers =
    lmstudio: prove reali che richiedono LM Studio attivo (RUN_LMSTUDIO_TESTS=1)
```

- [ ] **Step 6: Scrivi i test che falliscono**

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

- [ ] **Step 7: Verifica che falliscano**

Run: `python -m pytest -v`
Expected: FAIL per `ModuleNotFoundError: assistente.graph` / `assistente.model`.

- [ ] **Step 8: Implementa `graph.py`, `model.py` e `tests/fakes.py`**

`FIXED_REPLY = "Risposta fissa: il collegamento al modello arriverà nel prossimo incremento."`
Il nodo `modello` restituisce `{"messages": [model.invoke(state["messages"])]}`.

- [ ] **Step 9: Verifica su 3.13 e 3.14**

Run: `python -m pytest -v` e la verifica ad hoc su 3.14.
Expected: 4 passed in entrambi.

- [ ] **Step 10: Commit**

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

- [ ] **Step 1: Scrivi i test che falliscono**

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

- [ ] **Step 2: Verifica che falliscano**

Run: `python -m pytest tests/test_cli.py -v`
Expected: FAIL con `ModuleNotFoundError: assistente.cli`.

- [ ] **Step 3: Implementa `cli.py` e `__main__.py`**

`SYSTEM_PROMPT = "Sei l'assistente del laboratorio. Rispondi in italiano, in modo breve e chiaro."`
Le parole d'uscita si confrontano dopo `strip().lower()`. Un'uscita, sia per parola sia per
EOF/Ctrl+C, stampa `Arrivederci.` su `output`. `configure_logging` usa
`logging.basicConfig(stream=sys.stderr, level=..., format=...)` con il formato dei Global
Constraints e porta `httpx`, `httpcore`, `openai` a WARNING. Per ora `main()` fa
`configure_logging("INFO")`, `run_chat(build_graph(FixedReplyModel()))` e `return 0`.

- [ ] **Step 4: Verifica su 3.13 e 3.14**

Run: `python -m pytest -v` e la verifica ad hoc su 3.14.
Expected: tutti passed.

- [ ] **Step 5: Prova manuale (senza modello)**

`python -m assistente`, scrivi `ciao` e poi `esci`.
Expected: `Assistente> Risposta fissa: …`, poi `Arrivederci.`, poi ritorno al prompt di PowerShell.

- [ ] **Step 6: README e CLAUDE.md**

README: scopo, requisiti (Python 3.13 locale, Docker Desktop, LM Studio), preparazione del venv
(comandi degli Step 2 e 3 del Task 1), avvio `python -m assistente`, test `python -m pytest`.
CLAUDE.md: nuova sezione «Struttura e comandi» con i moduli di `assistente/`, il comando dei test
e la regola «suite verde su 3.13 e 3.14».

- [ ] **Step 7: Commit**

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

- [ ] **Step 1: Scrivi i test che falliscono**

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

- [ ] **Step 2: Verifica che falliscano** — `python -m pytest tests/test_config.py -v` → FAIL (modulo mancante)

- [ ] **Step 3: Implementa `config.py`** e crea `.env.example` con `LMSTUDIO_BASE_URL=http://localhost:1234/v1`, `LMSTUDIO_MODEL=google/gemma-4-e2b`, `LOG_LEVEL=INFO`

- [ ] **Step 4: Verifica su 3.13 e 3.14** — tutti passed

- [ ] **Step 5: Commit**

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

- [ ] **Step 1: Scrivi i test che falliscono (senza modello)**

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

- [ ] **Step 2: Verifica che falliscano** — `python -m pytest -v` → FAIL sui test nuovi

- [ ] **Step 3: Implementa**

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

- [ ] **Step 4: Verifica su 3.13 e 3.14** — tutti passed

- [ ] **Step 5: Prove reali con LM Studio (test)**

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

- [ ] **Step 6: Prove manuali con LM Studio**

1. `python -m assistente` con LM Studio attivo: una domanda riceve una risposta reale, e una
   domanda successiva che rimanda alla prima ne tiene conto.
2. Server LM Studio fermo: esce con codice 1 e il messaggio «LM Studio non raggiungibile…».
3. `LMSTUDIO_MODEL=inventato` nel `.env`: esce con codice 1 ed elenca i modelli disponibili.

- [ ] **Step 7: README** — configurazione (`Copy-Item .env.example .env`), avvio del server di LM Studio, controllo all'avvio, prove reali (comando dello Step 5)

- [ ] **Step 8: Commit**

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

- [ ] **Step 1: Scrivi i test che falliscono**

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

- [ ] **Step 2: Verifica che falliscano** — FAIL (modulo `assistente.tools` mancante, campi assenti)

- [ ] **Step 3: Implementa `tools.py` ed estendi `config.py`**

`current_time` formatta l'ora con `now.astimezone(ZoneInfo(nome)).isoformat(timespec="seconds")`
seguita da ` (nome)`. `config.py` usa `canonical_timezone` per validare `DEFAULT_TIMEZONE`.
Aggiungi `DEFAULT_TIMEZONE=Europe/Rome` e `MAX_TOOL_STEPS=3` a `.env.example`.

- [ ] **Step 4: Verifica su 3.13 e 3.14** — tutti passed. Su 3.14 il `test_tool_schema` controlla la differenza di comportamento delle annotazioni (PEP 649).

- [ ] **Step 5: Commit**

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

- [ ] **Step 1: Scrivi i test che falliscono**

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

- [ ] **Step 2: Verifica che falliscano** — FAIL (nuovi nodi e costanti assenti)

- [ ] **Step 3: Implementa**

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

- [ ] **Step 4: Verifica su 3.13 e 3.14** — tutti passed

- [ ] **Step 5: Prova reale con LM Studio (test)**

```python
def test_real_model_uses_clock_tool(graph):
    history, reply = ask(graph, new_history(), "Che ore sono adesso a Tokyo?")
    assert any(isinstance(m, ToolMessage) and m.name == "get_current_time" for m in history)
    assert reply.strip()
```
La fixture `graph` ora usa gli strumenti, come `main`. Run: il comando del Task 4 Step 5 → 3 passed.
Se `google/gemma-4-e2b` non chiama lo strumento, **non** si cambia il modello né il prompt di
nascosto: si riporta l'esito e si decide insieme.

- [ ] **Step 6: Prova manuale con LM Studio**

`python -m assistente`:
1. «Che ore sono a Tokyo?»: su stderr compaiono `strumento richiesto: get_current_time …` e
   `risultato strumento: …`, e la risposta è coerente con l'ora reale.
2. «E a Roma?»: il modello usa di nuovo lo strumento e il contesto della domanda precedente.
3. Con `LOG_LEVEL=WARNING` le righe dello strumento non compaiono più.

- [ ] **Step 7: README** — strumento orologio, formato dei log, `LOG_LEVEL`, `MAX_TOOL_STEPS` e comportamento al limite

- [ ] **Step 8: Commit**

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

- [ ] **Step 1: `Dockerfile` multi-stage**

Stage `base` (`python:3.14.<patch>-slim`, tag del Task 1 Step 4): `PYTHONUNBUFFERED=1`,
`PYTHONDONTWRITEBYTECODE=1`, `WORKDIR /app`, copia `requirements.txt`, poi
`pip install --no-cache-dir -r requirements.txt`.
Stage `test` (da `base`): installa `requirements-dev.txt`, copia `pytest.ini`, `assistente/` e
`tests/`, `CMD ["python", "-m", "pytest", "-p", "no:cacheprovider"]`.
Stage `app` (da `base`, **ultimo**, quindi predefinito): copia `assistente/`, crea un utente non
root e lo usa, `CMD ["python", "-m", "assistente"]`.

- [ ] **Step 2: `compose.yaml` e `.dockerignore`**

Valori della spec §10: `name: assistente-laboratorio`; servizio `assistente` (`target: app`, `env_file: .env`,
`LMSTUDIO_BASE_URL: http://host.docker.internal:1234/v1`, `extra_hosts`, `stdin_open`, `tty`);
servizio `test` (`target: test`, `profiles: ["test"]`).
`.dockerignore`: `.env`, `.venv`, `__pycache__`, `.pytest_cache`, `docs`, `.git`.

- [ ] **Step 3: Verifiche senza modello (Docker attivo)**

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

- [ ] **Step 4: Prova con Docker e LM Studio**

```powershell
docker compose run --rm assistente python -c "import os; from assistente.model import list_models; print(list_models(os.environ['LMSTUDIO_BASE_URL']))"
```
Expected: l'elenco contiene `google/gemma-4-e2b`. Se il container non raggiunge LM Studio, attiva
«Serve on Local Network» in LM Studio, ripeti il comando e annota l'esito nel README.

- [ ] **Step 5: README e CLAUDE.md**

README: sezione Docker con i comandi dello Step 3 effettivamente verificati e la diagnosi dello Step 4.
CLAUDE.md: comando dei test su 3.14, che sostituisce quello ad hoc.

- [ ] **Step 6: Commit**

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

- [ ] **Step 1: Suite senza modello su entrambe le versioni**

`python -m pytest -v` e `docker compose --profile test run --rm --build test` → tutti passed,
`lmstudio` skipped.

- [ ] **Step 2: Allineamento delle dipendenze**

```powershell
python -m pip freeze > "$env:TEMP\freeze-313.txt"
docker compose run --rm assistente python -m pip freeze > "$env:TEMP\freeze-314.txt"
Compare-Object (Get-Content "$env:TEMP\freeze-313.txt") (Get-Content "$env:TEMP\freeze-314.txt")
```
Expected: le uniche differenze sono le dipendenze di sviluppo (`pytest`, `pluggy`, `iniconfig`…)
e quelle solo per Windows (`colorama`). Ogni altra differenza va spiegata, oppure la versione
corrispondente va fissata in `requirements.txt`.

- [ ] **Step 3: Prove reali con LM Studio** — comando del Task 4 Step 5 → 3 passed

- [ ] **Step 4: Checklist manuale in Docker (spec §11)**

`docker compose run --rm assistente`:
1. «Che ore sono a Tokyo?»: compare il log della chiamata e la risposta è coerente.
2. «Quale città ti ho chiesto prima?»: la risposta cita Tokyo.
3. `esci`, poi un nuovo avvio e «Quale città ti ho chiesto prima?»: il modello non lo sa.
4. LM Studio fermo: il messaggio di errore è chiaro e l'uscita avviene con codice 1.

- [ ] **Step 5: README definitivo**

Sezione «Diagnosi»: LM Studio non raggiungibile in locale e da Docker, modello non disponibile,
variabile mancante, fuso orario non valido. Rileggi il README e tieni solo comandi eseguiti in
questo piano.

- [ ] **Step 6: Commit e resoconto**

```powershell
git add README.md
git commit -m "docs: completa diagnosi e verifica finale nel README"
```
Resoconto all'utente: cosa è stato eseguito, con quale esito (anche per gemma con lo strumento) e
cosa resta da provare a mano. Nessun push.
