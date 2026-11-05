# Calcolatrice sicura

Data: 2026-11-03
Stato: approvata (2026-11-03), con l'aggiunta del §7
Branch: `feat/calcolatrice-sicura` (da `dev`)
Specifiche di riferimento: `2026-10-26-assistente-langgraph-design.md`,
`2026-10-29-orologio-citta-log-design.md` e `2026-11-02-convertitore-unita-design.md` (restano
valide per tutto ciò che qui non è modificato).

## 1. Obiettivo

Terzo strumento locale dell'assistente, dopo orologio e convertitore di unità: il modello lo
richiede tramite tool calling e il programma lo esegue davvero. Calcola un'espressione aritmetica
**senza `eval`**: l'espressione viene analizzata con `ast.parse` (che costruisce l'albero sintattico
senza eseguire nulla) e valutata da codice nostro che ammette solo numeri, operatori consentiti e
parentesi. Tutto il resto produce un errore.

### Criteri di successo

- Con LM Studio e `google/gemma-4-e2b`, «Quanto fa 1234 * 5678?» produce una chiamata a `calculate`
  il cui risultato è `7006652` e una risposta che contiene 7006652 (anche con separatori delle
  migliaia).
- «Quanto fa 7 diviso 0?» produce il testo d'errore dello strumento, non un risultato inventato.
- La suite senza modello passa su Python 3.13 (venv) e 3.14 (container).
- Orologio e convertitore continuano a funzionare come prima.

Non è un criterio, ma un'osservazione da riportare: se il modello usa lo strumento anche per i
calcoli «facili» («Quanto fa 2 + 2?»). Con il convertitore gemma-4-e2b rispondeva a mente alle
domande semplici (punto da chiarire del piano del convertitore); qui il prompt lo chiede
esplicitamente (§4), ma l'esito va misurato, non dato per scontato.

### Fuori ambito

Funzioni (`sqrt`, `sin`, `log`, …), costanti (`pi`, `e`), variabili e assegnazioni, confronti,
percentuali, notazione scientifica in ingresso (`1e5`), numeri complessi, virgola decimale,
separatori delle migliaia, moltiplicazione implicita (`2(3+4)`), aritmetica esatta (`Decimal`,
`Fraction`), nuove dipendenze.

## 2. Lo strumento visto dal modello

`calculate(expression: str) -> str`

Descrizione per il modello: «Calcola un'espressione aritmetica e restituisce il risultato.
Operatori: + - * /, // (divisione intera), % (resto), ^ o ** (potenza), parentesi. Usa il punto
per i decimali: se l'utente scrive 3,5 passa 3.5. Esempi: '(3.5 + 2) * 4', '2^10', '17 % 5'.»

L'utente non scrive mai l'espressione: la scrive il modello traducendo la domanda. Le indicazioni
sulla sintassi (descrizione ed errori) sono quindi rivolte al modello.

### Sintassi ammessa

- Numeri: cifre con punto decimale facoltativo; ammessi anche `.5` e `5.`.
- Operatori binari: `+ - * /`, `//` (divisione intera), `%` (resto), `^` e `**` (potenza).
- Operatori unari: `+` e `-`.
- Parentesi tonde; spazi ignorati.
- Simboli alternativi, sostituiti prima dell'analisi: `×` e `·` → `*`; `÷` e `:` → `/`;
  `−` (meno tipografico, U+2212) → `-`; `^` → `**`.

### Regole di calcolo (quelle di Python)

| Regola | Esempio |
| --- | --- |
| Precedenza, dalla più forte: parentesi → potenza → segno unario → `* / // %` → `+ -` | `2 + 3 * 4` = 14 |
| Potenza associativa a destra | `2^3^2` = 512 |
| La potenza lega più forte del segno che la precede | `-2^2` = -4; `2^-1` = 0.5 |
| `//` arrotonda verso il basso; `%` ha il segno del divisore | `-7 // 2` = -4; `-7 % 3` = 2 |

Ogni numero e ogni calcolo è in float (`float` di Python), anche quando i numeri scritti sono
interi.

### Risultato

Formato: `<espressione ricevuta> = <risultato>`, con l'espressione così come l'ha passata il
modello, tolti gli spazi esterni.

```
(3.5 + 2) * 4 = 22
0.1 + 0.2 = 0.3
1 / 3 = 0.333333333333333
7 × 6 = 42
```

- Al massimo 15 cifre significative (la precisione garantita da un float), arrotondate.
- Notazione decimale, senza notazione scientifica e senza zeri finali inutili: `10 / 2` → `5`.
- Un risultato uguale a zero si scrive `0`, mai `-0`.

## 3. Errori e limiti

Testo che comincia con `Errore:`, come per gli altri strumenti; nessuna eccezione verso il grafo.
Si riporta il primo errore trovato. I controlli avvengono in quest'ordine.

Prima del calcolo, sull'intera espressione:

1. vuota o di soli spazi → `Errore: l'espressione è vuota.`
2. più di 200 caratteri (dopo aver tolto gli spazi esterni) →
   `Errore: l'espressione supera i 200 caratteri.`
3. contiene una virgola →
   `Errore: usa il punto come separatore decimale (es. 3.5), non la virgola.`
4. dopo la sostituzione dei simboli alternativi, contiene un carattere diverso da cifre, `.`,
   `+ - * / % ( )` e spazi → il primo di questi caratteri, con il messaggio
   `Errore: carattere non ammesso 'x'. Ammessi: cifre, punto decimale, + - * / // % ^ **, parentesi.`
5. `ast.parse` fallisce, oppure l'albero contiene un nodo fuori dalla lista bianca (§5) — per
   esempio `2 3`, `3 +`, `2****3`, `()`, `2(3+4)` →
   `Errore: espressione non valida. Esempio corretto: '(3.5 + 2) * 4'.`

Durante il calcolo, nell'ordine in cui si percorre l'albero (operando sinistro, operando destro,
operazione):

6. un numero scritto nell'espressione vale più di 0 e meno di 0.000000000000001, oppure più di
   1000000000000000 →
   `Errore: i numeri devono essere 0 oppure, in valore assoluto, compresi tra 0.000000000000001 e 1000000000000000.`
7. divisore zero con `/`, `//` o `%`, oppure base zero con esponente negativo →
   `Errore: divisione per zero.`
8. potenza con base negativa ed esponente non intero (per esempio `(-8)^0.5`, per cui Python
   restituirebbe un numero complesso) →
   `Errore: potenza non reale (base negativa con esponente non intero).`
9. un risultato, anche intermedio, oltre 1000000000000000 in valore assoluto, oppure una potenza
   che supera i limiti dei float (`OverflowError`, per esempio `9^9^9`) →
   `Errore: il risultato è troppo grande per essere rappresentato.`
10. un risultato, anche intermedio, diverso da zero e sotto 0.000000000000001 in valore assoluto,
    oppure una potenza con base diversa da zero che dà esattamente 0 per arrotondamento dei float
    (per esempio `0.5^10000`) →
    `Errore: il risultato è troppo piccolo per essere rappresentato.`

Note:

- L'intervallo 1e-15 .. 1e15 è lo stesso del convertitore. Il controllo sui risultati intermedi è
  una restrizione voluta: `(10^8)^2 / 10^10` dà «troppo grande» al passo `(10^8)^2`, anche se il
  risultato finale sarebbe 1000000.
- Il limite di 200 caratteri tiene piccoli l'albero e la profondità delle parentesi, lontano dal
  limite di ricorsione di Python.
- Calcolare la potenza in float fa fallire subito le potenze esplosive con `OverflowError`: non
  possono bloccare il programma come farebbe `9**9**9` con gli interi.
- Un argomento che non è una stringa viene respinto dalla validazione dello schema e il nodo
  `strumenti` restituisce già `Errore durante l'esecuzione di calculate: …` (comportamento
  esistente, non modificato).

## 4. Struttura del codice

Ricalca la coppia `units.py` / `tools.py`: analisi e calcolo in un modulo senza testi per il
modello, strumento e messaggi in `tools.py`.

- `assistente/arithmetic.py` (nuovo):
  - `Problem`: enum dei casi d'errore del §3 (vuota, troppo lunga, virgola, carattere, sintassi,
    numero fuori intervallo, divisione per zero, potenza non reale, troppo grande, troppo
    piccolo);
  - `CalcError(Exception)`: porta un `Problem` e, per il carattere non ammesso, il carattere;
  - `evaluate(expression: str) -> float`: controlli 1-4, sostituzione dei simboli alternativi,
    `ast.parse(..., mode="eval")`, controllo dell'intero albero con la lista bianca (controllo 5),
    poi calcolo ricorsivo con i controlli 6-10. Solleva `CalcError`; non restituisce mai un valore
    fuori intervallo.
  - Lista bianca dei nodi: `Expression`; `Constant` con valore `int` o `float` (non `bool`, non
    `complex`); `BinOp` con `Add`, `Sub`, `Mult`, `Div`, `FloorDiv`, `Mod`, `Pow`; `UnaryOp` con
    `UAdd`, `USub`. Non si usano mai `eval`, `exec` o `compile` su codice eseguibile.
- `assistente/tools.py`:
  - `calculate(expression: str) -> str`: funzione pura che chiama `evaluate`, formatta il
    risultato (§2) o traduce il `Problem` nel testo d'errore del §3;
  - `CALCULATOR_DESCRIPTION` e `make_calculator_tool() -> BaseTool` con nome `calculate`;
  - la docstring del modulo nomina anche la calcolatrice.
- `assistente/cli.py`:
  - `make_tools()` aggiunge `make_calculator_tool()` dopo orologio e convertitore;
  - il prompt di sistema aggiunge: «Per qualsiasi calcolo aritmetico, anche semplice, usa sempre
    lo strumento calculate e non fare il calcolo a mente.»

Invariati: `graph.py`, `model.py`, `config.py`, `units.py`, `cities.py`, `Dockerfile`,
`compose.yaml`, le dipendenze e le variabili d'ambiente.

## 5. Test e verifiche

### Test automatici (senza modello, scritti prima del codice)

- `tests/test_arithmetic.py` (nuovo):
  - operatori, precedenze e associatività della tabella del §2 (`2 + 3 * 4`, `2^3^2`, `-2^2`,
    `2^-1`, `-7 // 2`, `-7 % 3`, parentesi annidate), `.5` e `5.`, spazi;
  - simboli alternativi `×`, `·`, `÷`, `:`, `−`, `^` equivalenti a quelli ASCII;
  - ogni `Problem` del §3 con almeno un caso, compreso l'ordine (per esempio un'espressione con
    virgola e lettere dà la virgola; `1/0 + 2(3)` dà espressione non valida, non divisione per
    zero);
  - costrutti respinti dalla lista bianca: `()`, `2(3+4)`, `(1)(2)`;
  - lettere e nomi respinti al controllo dei caratteri: `abs(1)`, `1e5`, `0x10`, `1_000`,
    `__import__('os')`;
  - limiti: numero `1000000000000000` accettato e `1000000000000001` respinto, `0.000000000000001`
    accettato, risultato intermedio fuori intervallo, `9^9^9`, `0.5^10000`, `(-8)^0.5`, `0^-1`.
- `tests/test_tools.py` (aggiunte):
  - formato: `0.1 + 0.2 = 0.3`, `1 / 3 = 0.333333333333333`, `10 / 2 = 5`, `-0` scritto `0`,
    estremi `1000000000000000` e `0.000000000000001` senza notazione scientifica, espressione
    riportata senza spazi esterni;
  - ogni `Problem` tradotto nel testo esatto del §3;
  - nome, descrizione e parametro dello strumento.
- Grafo e CLI:
  - con `ScriptedModel` il modello finto chiede `calculate` e il `ToolMessage` contiene il
    risultato vero;
  - `make_tools` restituisce `get_current_time`, `convert_units`, `calculate`;
  - il prompt di sistema nomina `calculate`.

### Prove reali (separate, attivate esplicitamente)

- LM Studio: nuovo test in `tests/integration/test_lmstudio.py` («Quanto fa 1234 * 5678?»): il
  `ToolMessage` di `calculate` contiene `= 7006652` e la risposta, tolti punti, spazi e apostrofi,
  contiene 7006652.
- Serie a mano, ogni domanda in una sessione nuova, annotando se lo strumento è stato chiamato e
  con quali argomenti: «Quanto fa 1234 * 5678?», «Quanto fa 3,5 per 2?» (virgola → punto),
  «Quanto fa 2 alla 10?», «Quanto fa 17 modulo 5?», «Quanto fa 7 diviso 0?», «Quanto fa 2 + 2?»
  (calcolo facile), «Quanti chilometri sono 10 miglia?» (deve restare `convert_units`).
- Docker: suite su 3.14 con `docker compose --profile test run --rm --build test` e un calcolo
  provato con `docker compose run --rm assistente`.

Se il modello piccolo calcola a mente o sbaglia l'espressione, è un esito da riportare, non da
simulare.

## 6. Documentazione e commit

- README: lo strumento, sintassi ammessa, esempi, diagnosi (virgola, carattere non ammesso,
  espressione non valida, limiti), solo comandi verificati.
- `CLAUDE.md`: `arithmetic.py` nella struttura del pacchetto e calcolatrice in `tools.py` (da
  discutere prima della modifica).
- `docs/registro-test.md`: esiti delle verifiche.
- Commit su `feat/calcolatrice-sicura`: `docs:` per questa specifica, `feat(strumenti):` per
  modulo e strumento con i test, `docs:` per README e registri. A feature verificata si chiede
  l'ok prima del merge in `dev`; push solo su richiesta.

## 7. Aggiunta del 2026-11-03: correzioni dopo la revisione finale

Approvata il 2026-11-03 dopo le prove reali e la revisione finale. Integra i §2 e §3; dove li
contraddice, vale questa sezione.

### 7.1 «per» nella descrizione dello strumento

Con `google/gemma-4-e2b`, «Quanto fa 3,5 per 2?» produceva `3.5 / 2` in 5 tentativi su 5: «per» è
ambiguo («km per ora» è una divisione). La descrizione diventa:

«Calcola un'espressione aritmetica e restituisce il risultato. Operatori: + - * /, // (divisione
intera), % (resto), ^ o ** (potenza), parentesi. Parole: 'per' e 'x' indicano la moltiplicazione
(3,5 per 2 → 3.5 * 2), 'diviso' la divisione. Usa il punto per i decimali: se l'utente scrive 3,5
passa 3.5. Esempi: '(3.5 + 2) * 4', '2^10', '17 % 5'.»

Criterio: con la nuova descrizione «Quanto fa 3,5 per 2?» produce `3.5 * 2` (o un'espressione
equivalente) in almeno 4 tentativi su 5, senza regressioni sui controlli: «Quanto fa 3,5 diviso
2?» → divisione, «Quanto fa 3,5 moltiplicato 2?» → moltiplicazione, «Quanto fa 2 + 2?» →
`calculate`, «Quanti chilometri sono 10 miglia?» → `convert_units`, «Che ore sono a Miami?» →
`get_current_time`. Se il criterio non è raggiunto, è un esito da riportare; prompt e modello non
si cambiano senza un nuovo accordo.

### 7.2 Rumore dei float dopo somme e sottrazioni

`0.1 + 0.2` vale `0.30000000000000004` in float: il rumore sopravviveva alle sottrazioni e
`0.1 + 0.2 - 0.3` dava «troppo piccolo», `100 * 1.1 - 110` dava `0.000000000000014210854715202`.

- Dopo ogni `+` e `-` binario, se almeno un operando non è intero, il risultato si arrotonda a 15
  cifre significative dell'operando più grande in valore assoluto:
  `round(risultato, 14 - e)`, dove `e` è l'esponente decimale esatto di quell'operando
  (`Decimal(m).adjusted()`, non `math.log10`, che vicino a 1e15 arrotonda per eccesso).
- Con due operandi interi non si arrotonda: entro 1e15 la somma di due interi in float è esatta.
- L'arrotondamento avviene prima dei controlli 9 e 10 del §3.
- Esiti: `0.1 + 0.2 - 0.3 = 0`, `1.1 - 1 - 0.1 = 0`, `3 * 0.1 - 0.3 = 0`, `100 * 1.1 - 110 = 0`,
  `1000000000000000 - 1 = 999999999999999`, `999999999999999.5 - 0.5 = 999999999999999`.

### 7.3 Zeri iniziali

Un numero con zeri iniziali nella parte intera è accettato e vale come senza: `05 + 3` = 8,
`007` = 7, `00.5 + 1` = 1.5. Prima `05` dava «espressione non valida» (il parser di Python lo
rifiuta) mentre `00.5` era accettato. L'espressione riportata nel risultato resta quella ricevuta.

### 7.4 Spazi e caratteri invisibili

- Ogni carattere di spaziatura (`str.isspace()`: tabulazione, a capo, spazio non separabile, …)
  vale come uno spazio. `1 +\t2` = 3; `1 000 + 1` con uno spazio non separabile dà «espressione
  non valida», come con lo spazio normale.
- Nel messaggio del carattere non ammesso, un carattere non stampabile (`str.isprintable()` falso,
  per esempio lo spazio a larghezza zero) si scrive come codice: `Errore: carattere non ammesso
  'U+200B'. Ammessi: …`. Gli altri caratteri restano scritti così come sono.

### 7.5 Simboli alternativi raddoppiati

Ogni simbolo alternativo si sostituisce circondato da spazi (`÷` → ` / `, `^` → ` ** `, …), così
due simboli consecutivi non si fondono in un operatore diverso: `6::4`, `6÷÷4`, `6××4` e `6*·4`
danno «espressione non valida» (prima `6::4` dava la divisione intera e `6*·4` la potenza). `//` e
`**` scritti in ASCII restano la divisione intera e la potenza.

### 7.6 Ordine dei controlli aggiornato

1-3 come nel §3 (vuota, lunghezza sull'espressione ricevuta senza spazi esterni, virgola); poi
spaziature → spazio e sostituzione dei simboli alternativi; 4 carattere non ammesso; rimozione
degli zeri iniziali; 5 sintassi e lista bianca; 6-10 durante il calcolo, con l'arrotondamento del
§7.2 dopo ogni somma e sottrazione.

### 7.7 Documentazione

`CLAUDE.md` (approvato dall'utente il 2026-11-03): nella struttura del pacchetto, `tools.py`
(orologio, convertitore, calcolatrice) e `arithmetic.py` (analisi e calcolo sicuro delle
espressioni aritmetiche). README e registro dei test aggiornati con questi comportamenti e con gli
esiti delle nuove prove.

## 8. Aggiunta del 2026-11-05: chiamare lo strumento anche quando il caso è «impossibile»

Approvata dall'utente il 2026-11-05. Chiude il punto da chiarire del piano («7 diviso 0» riceve una risposta a mente) e
quello analogo del convertitore («Quanti kg sono 5 km?»): la stessa correzione vale per entrambi
gli strumenti e per il prompt di sistema. Integra il §4 e il §7.1; dove li contraddice, vale
questa sezione. La specifica del convertitore rimanda qui (suo §8).

### 8.1 Perché

Con `google/gemma-4-e2b` il modello risponde a mente quando «sa» già che l'operazione non si può
fare. Risposte corrette, ma non vengono dallo strumento e il criterio del §1 non è raggiunto.
Due spike, solo gemma, una sessione nuova per tentativo (`docs/registro-test.md`, sessioni (5) e
(6)); chiamate allo strumento atteso:

| Variante | «7 diviso 0» | «5 km → kg» | Controlli |
|---|---|---|---|
| A — prompt e descrizioni attuali (3/11 e 5/11) | 4/6 e 4/6 | 1/6 e 1/6 | 10/10 |
| B — regola nel prompt (8.2) | 2/6 | 2/6 | 10/10 |
| D — frasi nelle descrizioni (8.3), prompt attuale | 3/6 (+1 chiamata come testo, 2 errori 400) | 3/6 | 10/10 |
| **C — regola nel prompt e frasi nelle descrizioni** | **6/6** | **6/6** | 10/10 |

Né la regola né le descrizioni bastano da sole; insieme sì. Si adotta C, con i testi esatti
provati nello spike.

### 8.2 Prompt di sistema

Al prompt attuale, dopo la frase sulla calcolatrice, si aggiunge (preceduta da uno spazio):

«Usa gli strumenti anche quando la risposta ti sembra ovvia, il calcolo è facile o l'operazione
sembra impossibile (per esempio una divisione per zero o una conversione tra unità di categorie
diverse): chiama comunque lo strumento e riporta il suo esito. Ogni domanda che chiede quanto vale
una quantità in un'altra unità è una conversione.»

### 8.3 Descrizioni degli strumenti

In coda alle descrizioni attuali, preceduta da uno spazio:

- `calculate`: «Se l'espressione non si può calcolare (per esempio una divisione per zero)
  restituisce un errore che spiega il motivo: chiamalo comunque, non rispondere a mente.»
- `convert_units`: «Se le unità sono di categorie diverse restituisce un errore che lo spiega:
  chiamalo comunque, non rispondere a mente.»

Codice degli strumenti, testi d'errore, grafo, modello e configurazione restano invariati.

### 8.4 «3 settimane in ore»

Dopo l'arrivo della calcolatrice «Quante ore ci sono in 3 settimane?» chiama sempre `calculate`
(`3 * 7 * 24` → `504`, 30 su 30 negli spike) e mai `convert_units`. Il risultato viene da uno
strumento ed è corretto: per questa domanda è accettato `calculate` con risultato 504 oppure
`convert_units` con `wk` → `h` e risultato 504. Una risposta senza chiamata resta un esito
negativo.

### 8.5 Criteri

Serie a mano con prompt e descrizioni nuovi, una sessione nuova per tentativo, solo
`google/gemma-4-e2b`:

- «Quanto fa 7 diviso 0?» → `calculate` con `Errore: divisione per zero.` in almeno 8 tentativi
  su 10;
- «Quanti kg sono 5 km?» → `convert_units` con l'errore delle unità incompatibili in almeno 8 su 10;
- «Quante ore ci sono in 3 settimane?» → uno strumento con risultato 504 (8.4) in almeno 8 su 10;
- controlli, 2 tentativi ciascuno, tutti come prima: «Quanto fa 1234 * 5678?» e «Quanto fa 2 + 2?»
  → `calculate`; «Quanto fa 3,5 per 2?» → `3.5 * 2`; «Converti 10 miglia in km» e «Quanti
  chilometri sono 10 miglia?» → `convert_units`; «Che ore sono a Miami?» → `get_current_time`;
  «Ciao, come stai?» → nessuno strumento.

Una chiamata scritta come testo conta come tentativo non riuscito. Un errore di LM Studio (es.
400 o tempo scaduto) si conta a parte e si riporta, senza ripetere il tentativo. Se un criterio
non è raggiunto, è un esito da riportare: prompt, descrizioni e modello non si cambiano senza un
nuovo accordo.

### 8.6 Documentazione

README: righe della diagnosi su «7 diviso 0» e «3 settimane» aggiornate con l'esito della serie;
la chiamata scritta come testo resta in diagnosi. `docs/registro-test.md`: spike del 2026-11-05
(sessione (6)) ed esiti della serie. Chiusi i punti da chiarire, si chiede all'utente se
cancellare i ledger `Es.1/.superpowers/sdd/2026-11-02-convertitore-unita/` e
`2026-11-03-calcolatrice-sicura/`.
