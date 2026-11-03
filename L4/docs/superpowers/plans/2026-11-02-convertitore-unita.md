# Convertitore di unità — piano di implementazione

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

## Global Constraints

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

## Review Focus

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

### Task 1: tabella delle unità (`assistente/units.py`)

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

### Task 2: strumento `convert_units` e registrazione nella CLI

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

### Task 3: prove reali e documentazione

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

### Task 4: intervallo gestito (aggiunta del 2026-11-03)

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

## Punti da chiarire (2026-11-03)

### Il modello calcola a mente invece di chiamare `convert_units`

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
