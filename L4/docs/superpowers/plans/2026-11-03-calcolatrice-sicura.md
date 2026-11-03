# Calcolatrice sicura — piano di implementazione

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

## Global Constraints

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

## Review Focus

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

### Task 1: analisi e calcolo (`assistente/arithmetic.py`)

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

### Task 2: strumento `calculate` (`assistente/tools.py`)

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

### Task 3: registrazione, prova reale e documentazione

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
