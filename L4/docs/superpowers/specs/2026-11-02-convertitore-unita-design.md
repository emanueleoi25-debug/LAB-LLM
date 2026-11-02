# Convertitore di unità

Data: 2026-11-02
Stato: in revisione
Branch: `feat/convertitore-unita` (da `dev`)
Specifiche di riferimento: `2026-10-26-assistente-langgraph-design.md` e
`2026-10-29-orologio-citta-log-design.md` (restano valide per tutto ciò che qui non è modificato).

## 1. Obiettivo

Secondo strumento locale dell'assistente, costruito come l'orologio: il modello lo richiede tramite
tool calling e il programma lo esegue davvero. Converte un valore tra due unità di misura di un
elenco chiuso; con unità sconosciute o di categorie diverse restituisce un errore.

### Criteri di successo

- Con LM Studio e `google/gemma-4-e2b`, «Quanti chilometri sono 10 miglia?» produce una chiamata a
  `convert_units` con `mi` → `km` (simboli o sinonimi) e una risposta che contiene 16.09.
- Una richiesta con unità incompatibili («Quanti kg sono 5 km?») produce il testo d'errore dello
  strumento, non una conversione inventata.
- La suite senza modello passa su Python 3.13 (venv) e 3.14 (container).
- L'orologio continua a funzionare come prima.

### Fuori ambito

Unità fuori dalla tabella (§3), prefissi SI generici, unità composte libere, miglio nautico,
galloni e once imperiali britanniche, conversioni di valuta, espressioni aritmetiche (arriveranno
con la calcolatrice), nuove dipendenze.

## 2. Lo strumento visto dal modello

`convert_units(value: float, from_unit: str, to_unit: str) -> str`

- Descrizione per il modello: «Converte un valore tra due unità di misura della stessa categoria:
  lunghezza, massa, volume, temperatura, velocità, tempo. Parametri: value, il numero da
  convertire; from_unit e to_unit, il simbolo o il nome dell'unità (es. 'km', 'miglia', '°C',
  'libbre').»

### Riconoscimento delle unità

- Confronto su `name.strip().casefold()`: maiuscole, minuscole e spazi esterni non contano.
- Si accetta il simbolo canonico o uno dei sinonimi fissi della tabella (§3): nomi italiani e
  inglesi, singolare e plurale. L'elenco resta chiuso: ogni sinonimo porta a una sola unità.
- Abbreviazioni ambigue assegnate a una sola unità: `m` metro, `g` grammo, `t` tonnellata metrica,
  `min` minuto, `mi` miglio terrestre, `oz` oncia di massa (l'oncia fluida è `fl oz`), `gal`
  gallone statunitense.

### Risultato

Formato: `<valore di partenza> <simbolo da> = <risultato> <simbolo a> (<categoria>)`, con i simboli
canonici anche se il modello ha usato un sinonimo.

```
10 mi = 16.09 km (lunghezza)
100 °C = 212.00 °F (temperatura)
5 mg = 0.0000050 kg (massa)
```

- Valore di partenza in notazione decimale, senza zeri finali inutili (`10.0` → `10`, `2.50` →
  `2.5`).
- Risultato con due cifre decimali e punto decimale (il formato meno ambiguo per il modello, che
  poi risponde in italiano).
- Se un risultato diverso da zero si arrotonderebbe a `0.00`, si mostrano invece 2 cifre
  significative in notazione decimale (`0.0000050`). Nessuna notazione scientifica.
- Un risultato uguale a zero si scrive `0.00`, mai `-0.00`.
- Unità di partenza e di arrivo uguali: il risultato è lo stesso valore.

### Errori

Testo che comincia con `Errore:`, come per l'orologio; nessuna eccezione verso il grafo. I
controlli avvengono in quest'ordine:

1. valore non finito (infinito o NaN) → `Errore: il valore deve essere un numero finito.`
2. unità sconosciuta (prima `from_unit`, poi `to_unit`) →
   `Errore: unità sconosciuta 'xyz'. Unità ammesse: lunghezza (mm, cm, m, km, in, ft, yd, mi); massa (…); …`
   con tutte le categorie e i simboli canonici, nell'ordine della tabella;
3. categorie diverse → `Errore: unità incompatibili: 'km' è una lunghezza, 'kg' è una massa.`
   (con i simboli canonici e la categoria con l'articolo: una lunghezza, una massa, un volume,
   una temperatura, una velocità, un tempo);
4. temperatura sotto lo zero assoluto → `Errore: -300 °C è sotto lo zero assoluto.`

Valori negativi ammessi per tutte le categorie; l'unico limite è lo zero assoluto. Un valore che non
è un numero viene respinto dalla validazione dello schema e il nodo `strumenti` restituisce già
`Errore durante l'esecuzione di convert_units: …` (comportamento esistente, non modificato).

## 3. Tabella delle unità

Ogni unità ha una categoria, un simbolo canonico, dei sinonimi e due numeri, `scale` e `offset`,
verso l'unità base della categoria:

- `base = valore × scale + offset`
- `valore = (base − offset) ÷ scale`

`offset` vale 0 per tutte le unità tranne °C e °F: la temperatura non richiede codice speciale e lo
zero assoluto corrisponde a «base < 0».

### Lunghezza (base: m)

| Simbolo | scale | Sinonimi |
| --- | --- | --- |
| mm | 0.001 | millimetro, millimetri, millimeter, millimeters, millimetre, millimetres |
| cm | 0.01 | centimetro, centimetri, centimeter, centimeters, centimetre, centimetres |
| m | 1 | metro, metri, meter, meters, metre, metres |
| km | 1000 | chilometro, chilometri, kilometro, kilometri, kilometer, kilometers, kilometre, kilometres |
| in | 0.0254 | pollice, pollici, inch, inches |
| ft | 0.3048 | piede, piedi, foot, feet |
| yd | 0.9144 | iarda, iarde, yard, yards |
| mi | 1609.344 | miglio, miglia, mile, miles |

### Massa (base: kg)

| Simbolo | scale | Sinonimi |
| --- | --- | --- |
| mg | 0.000001 | milligrammo, milligrammi, milligram, milligrams |
| g | 0.001 | grammo, grammi, gram, grams |
| kg | 1 | chilogrammo, chilogrammi, chilo, chili, kilogrammo, kilogrammi, kilo, kilogram, kilograms |
| t | 1000 | tonnellata, tonnellate, tonne, tonnes |
| oz | 0.028349523125 | oncia, once, ounce, ounces |
| lb | 0.45359237 | libbra, libbre, pound, pounds, lbs |

### Volume (base: l)

| Simbolo | scale | Sinonimi |
| --- | --- | --- |
| ml | 0.001 | millilitro, millilitri, milliliter, milliliters, millilitre, millilitres |
| cl | 0.01 | centilitro, centilitri, centiliter, centiliters, centilitre, centilitres |
| l | 1 | litro, litri, liter, liters, litre, litres |
| m³ | 1000 | m3, mc, metro cubo, metri cubi, cubic meter, cubic meters, cubic metre, cubic metres |
| gal | 3.785411784 | gallone, galloni, gallon, gallons |
| fl oz | 0.0295735295625 | floz, oncia fluida, once fluide, fluid ounce, fluid ounces |

### Temperatura (base: K)

| Simbolo | scale | offset | Sinonimi |
| --- | --- | --- | --- |
| °C | 1 | 273.15 | c, celsius, grado celsius, gradi celsius, centigradi |
| °F | 5/9 | 273.15 − 32 × 5/9 | f, fahrenheit, grado fahrenheit, gradi fahrenheit |
| K | 1 | 0 | kelvin |

### Velocità (base: m/s)

| Simbolo | scale | Sinonimi |
| --- | --- | --- |
| m/s | 1 | mps, metro al secondo, metri al secondo, meters per second, metres per second |
| km/h | 1/3.6 | kmh, kph, km/ora, chilometri orari, chilometri all'ora, kilometers per hour, kilometres per hour |
| mph | 0.44704 | miglia orarie, miglia all'ora, miles per hour |
| kn | 1852/3600 | nodo, nodi, knot, knots, kt |

### Tempo (base: s)

| Simbolo | scale | Sinonimi |
| --- | --- | --- |
| s | 1 | sec, secondo, secondi, second, seconds |
| min | 60 | minuto, minuti, minute, minutes |
| h | 3600 | hr, ora, ore, hour, hours |
| d | 86400 | giorno, giorni, day, days |
| wk | 604800 | settimana, settimane, week, weeks |

## 4. Struttura del codice

Ricalca la coppia `cities.py` / `tools.py`: dati e calcolo in un modulo, strumento in `tools.py`.

- `assistente/units.py` (nuovo), tabella e matematica senza testi per il modello:
  - `Unit`: dataclass immutabile con `symbol`, `category`, `scale`, `offset`, `aliases`;
  - `UNITS`: la tabella chiusa del §3, nell'ordine indicato;
  - `find_unit(name: str) -> Unit | None`: ricerca nell'indice simbolo/sinonimo → unità,
    costruito una volta sola; nome vuoto o sconosciuto → `None`;
  - conversione da e verso la base (`to_base`, `from_base`).
- `assistente/tools.py`:
  - `convert_units(value, from_unit, to_unit) -> str`: funzione pura con controlli, conversione,
    formattazione e testi d'errore del §2 (analoga a `current_time`);
  - `make_converter_tool() -> BaseTool`: la avvolge con nome `convert_units` e descrizione;
  - la docstring del modulo non dice più «per ora solo l'orologio».
- `assistente/cli.py`:
  - `create_graph` registra `make_converter_tool()` accanto all'orologio;
  - il prompt di sistema aggiunge: «Per convertire unità di misura usa sempre lo strumento
    convert_units e non fare il calcolo a mente.»

Invariati: `graph.py`, `model.py`, `config.py`, `Dockerfile`, `compose.yaml`, le dipendenze e le
variabili d'ambiente.

## 5. Test e verifiche

### Test automatici (senza modello, scritti prima del codice)

- `tests/test_units.py` (nuovo):
  - `find_unit` trova simboli e sinonimi senza distinguere maiuscole e minuscole e con spazi in
    eccesso; `None` per nomi sconosciuti o vuoti;
  - nessun simbolo o sinonimo appartiene a due unità; ogni categoria ha esattamente un'unità con
    `scale` 1 e `offset` 0;
  - conversioni di riferimento: 1 mi = 1.609344 km, 1 lb = 0.45359237 kg,
    1 gal = 3.785411784 l, 100 °C = 212 °F, 0 K = −273.15 °C, 1 kn = 1.852 km/h,
    1 wk = 168 h (confronto con `pytest.approx`).
- `tests/test_tools.py` (aggiunte):
  - formato: due decimali, valore di partenza senza zeri inutili, valori piccoli con 2 cifre
    significative, zero senza segno, sinonimi riportati al simbolo canonico;
  - i quattro errori del §2, con l'elenco completo delle unità ammesse per l'unità sconosciuta;
  - nome e parametri dello strumento.
- Grafo e CLI:
  - con `ScriptedModel` il modello finto chiede `convert_units` e il `ToolMessage` contiene il
    risultato vero;
  - `create_graph` registra sia `get_current_time` sia `convert_units`.

### Prove reali (separate, attivate esplicitamente)

- LM Studio: nuovo test in `tests/integration/test_lmstudio.py` («Quanti chilometri sono 10
  miglia?»): il `ToolMessage` di `convert_units` contiene `16.09 km` e la risposta contiene 16.09.
- Serie a mano, ogni domanda in una sessione nuova, annotando gli argomenti passati dal modello:
  miglia → km, °C → °F, libbre → kg, nodi → km/h, settimane → ore, «Quanti kg sono 5 km?».
- Docker: suite su 3.14 con `docker compose --profile test run --rm --build test` e una
  conversione provata con `docker compose run --rm assistente`.

Se il modello piccolo sbaglia gli argomenti, è un esito da riportare, non da simulare.

## 6. Documentazione e commit

- README: lo strumento, la tabella delle unità, esempi, diagnosi (unità sconosciuta, unità
  incompatibili), solo comandi verificati.
- `CLAUDE.md`: `units.py` nella struttura del pacchetto.
- `docs/registro-test.md`: esiti delle verifiche.
- Commit su `feat/convertitore-unita`: `docs:` per questa specifica, `feat(strumenti):` per tabella
  e strumento con i test, `docs:` per README e registri. A feature verificata si chiede l'ok prima
  del merge in `dev`; push solo su richiesta.
