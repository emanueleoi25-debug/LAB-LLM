# Assistente del laboratorio

Chat da terminale in Python che organizza il flusso in un grafo LangGraph esplicito e usa un
modello servito da LM Studio sull'host. La cronologia vale per la sessione e si perde all'uscita.
Prima dell'agente un router decide se la domanda rientra nell'ambito dell'assistente: le domande
fuori ambito ricevono un rifiuto senza raggiungere l'agente.
Progetto del corso «Deep Learning e LLM: costruire chatbot e agenti» (lezione L4).

## Requisiti

- Python 3.13 per l'ambiente locale (in Docker si usa Python 3.14.9)
- Docker Desktop (per l'avvio con Docker Compose)
- LM Studio sull'host, con il server attivo e il modello scaricato

Tutti i comandi si eseguono dalla cartella `Es.1/L4`.

## Preparazione (PowerShell)

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

`requirements.txt` contiene le dipendenze dell'applicazione, `requirements-dev.txt` aggiunge
quelle per i test.

## Configurazione

```powershell
Copy-Item .env.example .env
```

Le variabili d'ambiente hanno la precedenza su `.env`, che resta fuori da Git.

| Variabile | Obbligatoria | Default | Significato |
|---|---|---|---|
| `LMSTUDIO_BASE_URL` | sì | — | indirizzo dell'API di LM Studio, es. `http://127.0.0.1:1234/v1`: LM Studio ascolta solo su `127.0.0.1` e con `localhost` Windows prova prima `::1`, così ogni nuova connessione costa circa 2 s in più (in Docker lo imposta `compose.yaml`) |
| `LMSTUDIO_MODEL` | sì | — | identificativo del modello come restituito da `GET /v1/models` |
| `GIORNI_BASE_URL` | sì | — | indirizzo del servizio giorni, es. `http://127.0.0.1:8000`: con `localhost` Windows prova prima `::1`, dove uvicorn non ascolta, e ogni chiamata costa circa 2 s in più (in Docker lo imposta `compose.yaml`) |
| `CATALOGO_BASE_URL` | sì | — | indirizzo del servizio catalogo, es. `http://127.0.0.1:8001` (in Docker lo imposta `compose.yaml`) |
| `NOTE_DB_PATH` | sì | — | file SQLite delle note, es. `dati/note.db`, relativo alla cartella da cui avvii l'app (in Docker lo imposta `compose.yaml`) |
| `AMBITO_PATH` | no | `ambito.md` | file con la descrizione dell'ambito usata dal router, relativo alla cartella da cui avvii l'app (vedi [Router](#router-domande-fuori-ambito)) |
| `DEFAULT_TIMEZONE` | no | `Europe/Rome` | fuso dell'orologio quando il modello non indica una città (nome IANA) |
| `MAX_TOOL_STEPS` | no | `3` | giri modello→strumenti consentiti per ogni domanda (intero ≥ 1) |
| `LOG_LEVEL` | no | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |

In LM Studio: carica il modello (es. `google/gemma-4-e2b`) e avvia il server locale (porta 1234).
Per vedere gli identificativi disponibili:

```powershell
Invoke-RestMethod http://127.0.0.1:1234/v1/models | Select-Object -ExpandProperty data | Select-Object id
```

## Avvio

Servono tre terminali, tutti nella cartella `Es.1/L4` con il venv attivo. Nel primo si avvia il
servizio giorni (vedi [Strumenti per giorni e scadenze](#strumenti-per-giorni-e-scadenze)), nel
secondo il servizio catalogo (vedi [Strumenti del catalogo](#strumenti-del-catalogo)); entrambi
restano in esecuzione. Nel terzo la chat.

```powershell
python -m uvicorn servizio_giorni.app:app --port 8000
```

```powershell
python -m uvicorn servizio_catalogo.app:app --port 8001
```

```powershell
python -m assistente
```

L'applicazione si avvia anche con i servizi spenti: non li controlla all'avvio. Solo gli
strumenti del servizio spento rispondono allora con un errore (vedi Diagnosi). Il server delle
note invece non va avviato a mano: lo avvia l'applicazione (vedi
[Strumenti delle note](#strumenti-delle-note)).

All'avvio l'applicazione controlla che LM Studio risponda e che il modello configurato sia
disponibile; altrimenti termina con codice 1 e un messaggio che riporta l'indirizzo e i modelli
disponibili. Poi legge gli strumenti dal server delle note: se il server non parte termina con
codice 1 e `Server MCP delle note non avviabile: …`. Una variabile mancante o non valida, o un
file dell'ambito mancante, illeggibile o vuoto, fa terminare con codice 2.

Scrivi una domanda dopo `Tu>`. Per uscire: `esci`, `exit`, Ctrl+C oppure Ctrl+Z seguito da Invio
(Ctrl+D su Linux/macOS). Se il modello non risponde durante la sessione, la domanda viene scartata
e si può riprovare.

## Router: domande fuori ambito

Ogni domanda passa prima dal nodo `router`, che chiede allo stesso modello di LM Studio, con un
prompt di sistema proprio, se la domanda rientra nell'ambito dell'assistente. Il grafo è:

```
START → router ─┬─ conversazione (anche risposta non utilizzabile) → agente ─┬─ nessuna chiamata → END
                │                                                            ├─ chiamata, entro il limite → strumenti → agente
                │                                                            └─ chiamata, oltre il limite → limite → END
                └─ fuori_ambito → rifiuto → END
```

L'ambito è descritto in [`ambito.md`](ambito.md), nella cartella del progetto (o nel file indicato
da `AMBITO_PATH`): ora e fusi, unità di misura, calcoli, date e scadenze, inventario, note, domande
sul laboratorio e sull'assistente, saluti e domande sulla conversazione in corso. Tutto il resto è
fuori ambito, comprese per ora le domande sul meteo. Per cambiare l'ambito basta modificare il file
e riavviare l'applicazione, senza toccare il codice.

Il router riceve la domanda e gli ultimi 4 messaggi di testo tra utente e assistente (non le
chiamate agli strumenti), così una domanda come «e a Tokyo?» viene giudicata insieme a quella
precedente. Risponde con un JSON vincolato da uno schema (`response_format` di LM Studio, con
`temperature=0`): `categoria` (`conversazione` o `fuori_ambito`) e `motivo`. Non sceglie gli
strumenti: lo fa l'agente, come prima. I messaggi del router non entrano nella cronologia.

- In ambito: la domanda va all'agente.
- Fuori ambito: il nodo `rifiuto` risponde sempre «Posso aiutarti solo con il laboratorio: ora e
  fusi orari, unità di misura, calcoli, date e scadenze, inventario e note. Questa domanda è fuori
  dal mio ambito.» L'agente non viene eseguito; domanda e rifiuto restano nella cronologia.
- Risposta del router non utilizzabile (JSON non valido, categoria sconosciuta, motivo vuoto…): la
  domanda va all'agente, con un avviso nel log.

Ogni domanda costa quindi una chiamata in più al modello. Con `google/gemma-4-e4b` il router ha
richiesto da 41 a 63 s per domanda il 2026-11-09: il modello produce circa 276 token per un JSON di
circa 40, probabilmente un ragionamento nascosto; lo schema non rallenta (stessi tempi senza). Senza
schema gemma racchiude il JSON in un blocco di codice, che il router non accetterebbe.

Righe di log del router (formato):

```
INFO assistente.graph: router: categoria=conversazione motivo=<motivo del router>
INFO assistente.graph: router → agente
INFO assistente.graph: router: categoria=fuori_ambito motivo=<motivo del router>
INFO assistente.graph: router → rifiuto
INFO assistente.graph: rifiuto: domanda fuori ambito, agente non eseguito
WARNING assistente.graph: router: risposta non utilizzabile (JSON non valido), la domanda passa all'agente: <risposta grezza>
```

Nel percorso fuori ambito non compaiono righe `→ modello` o `← modello`: è il segno che l'agente
non è stato eseguito. Con `LOG_LEVEL=DEBUG` compaiono anche i messaggi mandati al router
(`→ router [sistema] …`, `→ router [utente] …`).

## Strumento orologio, log e limite di passaggi

Il modello può chiedere lo strumento `get_current_time(city)`. `city` è il nome della città come
l'ha scritto l'utente (es. `Miami`, `Nuova York`, `Pechino`); il programma ne trova il fuso in un
archivio locale (`geonamescache`, città con almeno 5.000 abitanti, nessun accesso alla rete).
Maiuscole, accenti nel nome ufficiale (`Cancun` trova Cancún) e spazi iniziali o finali sono
indifferenti; una parte dopo la virgola viene ignorata se serve (`Miami, Florida`). Tra città con
lo stesso nome vince la più popolosa. Il nome ufficiale di una città prevale sul nome alternativo
di un'altra (`Zaragoza` resta in Spagna), salvo che quest'altra sia almeno 10 volte più popolosa
(`Roma` è Rome, non Roma in Lesotho). È accettato anche un nome IANA (`Asia/Tokyo`).

Il risultato dichiara sempre che cosa è stato usato:

| Caso | Esempio di risultato |
|---|---|
| città trovata | `2026-11-02T04:09:01-05:00 (Miami, US, fuso America/New_York)` |
| nome IANA | `2026-10-27T01:05:00+09:00 (fuso Asia/Tokyo)` |
| nessuna città | `2026-11-02T10:09:45+01:00 (fuso predefinito Europe/Rome)` |
| città sconosciuta | `Errore: città sconosciuta 'Xyzville'. Indica il nome di una città, ad esempio 'Roma'.` |

Il messaggio d'errore torna al modello, senza interrompere la sessione.

Il grafo esegue lo strumento, restituisce il risultato al modello e ottiene la risposta finale.
I log vanno su stderr, separati dalle risposte. Le righe `→ modello` mostrano i messaggi nuovi
inviati al modello (il prompt di sistema solo alla prima domanda), le righe `← modello` che cosa
ha deciso: chiamata a uno strumento, chiamata non valida o risposta. Gli a capo sono scritti `\n`.
Esempio dal container (prompt di sistema accorciato):

```
2026-11-02 09:08:56,824 INFO assistente.graph: → modello [sistema] Sei l'assistente del laboratorio. …
2026-11-02 09:08:56,824 INFO assistente.graph: → modello [utente] Che ore sono a Miami?
2026-11-02 09:09:01,726 INFO assistente.graph: ← modello [chiamata] get_current_time {'city': 'Miami'}
2026-11-02 09:09:01,728 INFO assistente.graph: strumento richiesto: get_current_time {'city': 'Miami'}
2026-11-02 09:09:02,911 INFO assistente.graph: risultato strumento: 2026-11-02T04:09:01-05:00 (Miami, US, fuso America/New_York)
2026-11-02 09:09:02,913 INFO assistente.graph: → modello [strumento get_current_time] 2026-11-02T04:09:01-05:00 (Miami, US, fuso America/New_York)
2026-11-02 09:09:12,103 INFO assistente.graph: ← modello [risposta] Attualmente sono le 04:09 del 2 novembre 2026 a Miami.
Assistente> Attualmente sono le 04:09 del 2 novembre 2026 a Miami.
```

Con `LOG_LEVEL=WARNING` queste righe non compaiono. Se in una stessa domanda il modello continua a
chiedere strumenti oltre `MAX_TOOL_STEPS` giri, il grafo si ferma, registra un WARNING e risponde
«Mi fermo: ho raggiunto il limite di N passaggi con gli strumenti…».

## Strumento convertitore di unità

Il modello può chiedere lo strumento `convert_units(value, from_unit, to_unit)`: `value` è il
numero da convertire, `from_unit` e `to_unit` il simbolo o il nome dell'unità (es. `km`,
`miglia`, `°C`, `libbre`). La conversione è locale, su una tabella chiusa; nessuna dipendenza in
più.

| Categoria | Simboli |
|---|---|
| lunghezza | mm, cm, m, km, in, ft, yd, mi |
| massa | mg, g, kg, t, oz, lb |
| volume | ml, cl, l, m³, gal, fl oz |
| temperatura | °C, °F, K |
| velocità | m/s, km/h, mph, kn |
| tempo | s, min, h, d, wk |

Oltre ai simboli sono accettati nomi italiani e inglesi, al singolare e al plurale (`chilometri`,
`miles`, `libbre`, `nodi`, `gradi celsius`…). Maiuscole, spazi in eccesso, un punto finale (`lb.`)
e `ºC` o `° C` al posto di `°C` sono indifferenti. Le abbreviazioni ambigue valgono una sola
unità: `m` metro, `g` grammo, `t` tonnellata, `min` minuto, `mi` miglio terrestre, `oz` oncia di
massa (l'oncia fluida è `fl oz`), `gal` gallone statunitense.

Il risultato usa i simboli canonici e due decimali. Un valore diverso da zero che diventerebbe
`0.00` è scritto con due cifre significative, senza notazione scientifica:

```
10 mi = 16.09 km (lunghezza)
100 °C = 212.00 °F (temperatura)
5 mg = 0.0000050 kg (massa)
```

Gli errori tornano al modello come testo, senza interrompere la sessione:

| Caso | Risultato |
|---|---|
| valore infinito o NaN | `Errore: il valore deve essere un numero finito.` |
| valore fuori intervallo | `Errore: il valore deve essere 0 oppure, in valore assoluto, compreso tra 0.000000000000001 e 1000000000000000.` |
| unità sconosciuta | `Errore: unità sconosciuta 'parsec'. Unità ammesse: lunghezza (mm, cm, …); …` |
| categorie diverse | `Errore: unità incompatibili: 'km' è una lunghezza, 'kg' è una massa.` |
| sotto lo zero assoluto | `Errore: -300 °C è sotto lo zero assoluto.` |
| risultato oltre 1000000000000000 | `Errore: il risultato è troppo grande per essere rappresentato.` |
| risultato diverso da zero sotto 0.000000000000001 | `Errore: il risultato è troppo piccolo per essere rappresentato.` |

Valori e risultati diversi da zero sono gestiti, in valore assoluto, tra 0.000000000000001 e
1000000000000000 (1e-15 e 1e15): dentro l'intervallo si scrivono in poche cifre, senza notazione
scientifica.

Esempio dal container:

```
2026-11-03 09:21:51,964 INFO assistente.graph: ← modello [chiamata] convert_units {'from_unit': 'miglia', 'to_unit': 'chilometro', 'value': 10}
2026-11-03 09:21:51,966 INFO assistente.graph: → modello [strumento convert_units] 10 mi = 16.09 km (lunghezza)
2026-11-03 09:21:58,400 INFO assistente.graph: ← modello [risposta] 10 miglia sono circa 16.09 chilometri.
Assistente> 10 miglia sono circa 16.09 chilometri.
```

Con `google/gemma-4-e2b` e i testi di prima il modello rispondeva a mente a «Quanti kg sono
5 km?» (strumento chiamato 1 volta su 6). Ora il prompt chiede di usare gli strumenti anche
quando l'operazione sembra impossibile e la descrizione dice di chiamare lo strumento anche con
unità di categorie diverse: nella serie del 2026-11-05 la domanda ha chiamato `convert_units` in
10 tentativi su 10, con l'errore `unità incompatibili`. «Quante ore ci sono in 3 settimane?» usa
la calcolatrice (`3 * 7 * 24 = 504`, 10 su 10), che è un esito accettato. Dettagli in
[`docs/registro-test.md`](docs/registro-test.md).

## Strumento calcolatrice

Il modello può chiedere lo strumento `calculate(expression)`, che calcola un'espressione
aritmetica scritta dal modello traducendo la domanda. Il calcolo è locale e **non usa `eval`**:
`ast.parse` costruisce soltanto l'albero sintattico, e il programma calcola accettando solo numeri,
operatori consentiti e parentesi. Nessuna dipendenza in più.

| Sintassi | Significato |
|---|---|
| `+ - * /` | operazioni di base |
| `//` | divisione intera (arrotonda verso il basso: `-7 // 2` = -4) |
| `%` | resto, con il segno del divisore (`-7 % 3` = 2) |
| `^` o `**` | potenza, associativa a destra (`2^3^2` = 512); lega più del segno (`-2^2` = -4) |
| `( )` | parentesi |
| `×` `·` / `÷` `:` / `−` | equivalenti di `*`, `/` e `-` |

I decimali si scrivono con il punto (`.5` e `5.` sono ammessi); gli zeri iniziali non contano
(`05 + 3` = 8). Tabulazioni, a capo e spazi non separabili valgono come spazi. Funzioni,
costanti, lettere, notazione scientifica (`1e5`), virgola decimale e separatori delle migliaia
non sono ammessi. Due simboli alternativi di seguito (`6::4`, `6÷÷4`) sono un errore di sintassi,
non un operatore diverso.

Il risultato ha al massimo 15 cifre significative, senza notazione scientifica né zeri finali.
Dopo ogni somma o sottrazione con decimali il risultato si arrotonda alla 15ª cifra significativa
dell'operando più grande, così il rumore dei float non resta nel risultato:

```
(3.5 + 2) * 4 = 22
0.1 + 0.2 = 0.3
0.1 + 0.2 - 0.3 = 0
100 * 1.1 - 110 = 0
1 / 3 = 0.333333333333333
7 × 6 = 42
```

Gli errori tornano al modello come testo, senza interrompere la sessione:

| Caso | Risultato |
|---|---|
| espressione vuota | `Errore: l'espressione è vuota.` |
| più di 200 caratteri | `Errore: l'espressione supera i 200 caratteri.` |
| virgola | `Errore: usa il punto come separatore decimale (es. 3.5), non la virgola.` |
| lettere o altri simboli (`3 x 4`, `1e5`, `=`) | `Errore: carattere non ammesso 'x'. Ammessi: cifre, punto decimale, + - * / // % ^ **, parentesi.` |
| carattere invisibile (es. spazio a larghezza zero) | `Errore: carattere non ammesso 'U+200B'. Ammessi: …` |
| sintassi errata (`2 3`, `3 +`, `2(3+4)`, `6::4`) | `Errore: espressione non valida. Esempio corretto: '(3.5 + 2) * 4'.` |
| numero fuori intervallo | `Errore: i numeri devono essere 0 oppure, in valore assoluto, compresi tra 0.000000000000001 e 1000000000000000.` |
| divisione per zero (anche `0^-1`) | `Errore: divisione per zero.` |
| base negativa con esponente non intero | `Errore: potenza non reale (base negativa con esponente non intero).` |
| risultato, anche intermedio, oltre 1000000000000000 | `Errore: il risultato è troppo grande per essere rappresentato.` |
| risultato, anche intermedio, diverso da zero sotto 0.000000000000001 | `Errore: il risultato è troppo piccolo per essere rappresentato.` |

L'intervallo gestito è lo stesso del convertitore e vale anche per i passaggi intermedi:
`(10^8)^2 / 10^10` dà «troppo grande» al passo `(10^8)^2`.

Esempio dal container:

```
2026-11-03 10:41:28,025 INFO assistente.graph: ← modello [chiamata] calculate {'expression': '1234 * 5678'}
2026-11-03 10:41:28,033 INFO assistente.graph: → modello [strumento calculate] 1234 * 5678 = 7006652
2026-11-03 10:41:35,387 INFO assistente.graph: ← modello [risposta] $1234 \times 5678 = 7.006.652$
Assistente> $1234 \times 5678 = 7.006.652$
```

Nelle prove del 2026-11-03 `google/gemma-4-e2b` ha chiamato lo strumento anche per «Quanto fa
2 + 2?». La descrizione dello strumento spiega che «per» e «x» indicano la moltiplicazione: senza
questa frase il modello passava `3.5 / 2` per «Quanto fa 3,5 per 2?» (5 tentativi su 5), con la
frase passa `3.5 * 2` (6 su 6, e 2 su 2 nella serie del 2026-11-05). Per «Quanto fa 7 diviso 0?»
il modello rispondeva spesso a mente («la divisione per zero è indefinita»). Con la regola nel
prompt e la frase in coda alla descrizione («se l'espressione non si può calcolare … chiamalo
comunque») ha chiamato `calculate` in 10 tentativi su 10, con `Errore: divisione per zero.`; né
la sola regola né la sola frase bastavano. Dettagli in
[`docs/registro-test.md`](docs/registro-test.md).

## Strumenti per giorni e scadenze

La logica sta in un servizio FastAPI separato, `servizio_giorni`, che non importa nulla da
`assistente`. L'agente lo raggiunge via HTTP (indirizzo in `GIORNI_BASE_URL`, timeout 5 secondi) con
quattro strumenti che trasformano la risposta JSON in un testo per il modello. Si avvia con:

```powershell
python -m uvicorn servizio_giorni.app:app --port 8000
```

Per controllare che risponda (da un altro terminale):

```powershell
Invoke-RestMethod http://127.0.0.1:8000/salute
curl.exe http://127.0.0.1:8000/salute
```

La risposta è `{"stato":"ok","anni_festivita":[2020,2040]}`.

| Strumento | Parametri | Che cosa fa |
|---|---|---|
| `days_between` | `end`, `start` (facoltativo) | giorni di calendario e giorni lavorativi tra due date |
| `add_days` | `days`, `start` (facoltativo) | data ottenuta aggiungendo (o togliendo, se negativo) giorni di calendario |
| `add_business_days` | `days`, `start` (facoltativo) | scadenza in giorni lavorativi, con le festività saltate |
| `date_info` | `date` (facoltativo) | giorno della settimana, festività, fine settimana, lavorativo |

Le date sono `AAAA-MM-GG` oppure `MM-GG` (vale la prossima occorrenza: `12-25` per Natale);
i parametri di data omessi valgono oggi. «Oggi» è la data nel fuso `DEFAULT_TIMEZONE`, calcolata
dallo strumento e passata sempre al servizio, che non legge mai il proprio orologio. «Lavorativo»
vuol dire dal lunedì al venerdì e non festività nazionale italiana; una festività di sabato o
domenica non si recupera. Il calcolo copre gli anni 1900-2100; festività e giorni lavorativi solo
gli anni 2020-2040.

Le festività stanno in `servizio_giorni/festivita.json`: le undici fisse (San Francesco d'Assisi,
4 ottobre, dal 2026 per la legge 8 ottobre 2025 n. 151) e, per ogni anno 2020-2040, le date di
Pasqua e Lunedì dell'Angelo scritte nel file (il servizio non le calcola). All'avvio il file è
validato; se non è valido il servizio non parte e dice perché.

Il risultato dichiara sempre che cosa è stato calcolato; gli errori iniziano con `Errore: ` e
tornano al modello come testo, senza interrompere la sessione:

| Caso | Esempio di risultato |
|---|---|
| `days_between` | `Dal 2026-11-05 (giovedì) al 2026-12-25 (venerdì): 50 giorni di calendario, 34 giorni lavorativi (esclusa la partenza, inclusa la data di arrivo).` |
| `add_days` | `2026-11-05 (giovedì) + 30 giorni = 2026-12-05 (sabato)` |
| `add_business_days` | `2026-11-05 (giovedì) + 10 giorni lavorativi = 2026-11-19 (giovedì); nessuna festività saltata.` |
| `date_info`, festività | `2027-06-02 (mercoledì): festività, Festa della Repubblica; non lavorativo.` |
| data non valida | `Errore: data non valida '02-30'. Usa AAAA-MM-GG o MM-GG.` |
| servizio spento | `Errore: servizio giorni non raggiungibile a http://127.0.0.1:8000. Non è possibile calcolare il risultato: dillo all'utente e non calcolarlo a mente.` |
| risposta inattesa | `Errore: risposta non valida dal servizio giorni (HTTP <codice>). Non è possibile calcolare il risultato: dillo all'utente e non calcolarlo a mente.` |

Esempio dal container (prompt di sistema omesso):

```
2026-11-05 16:32:07,983 INFO assistente.graph: ← modello [chiamata] days_between {'end': '2026-12-25', 'start': '2026-11-05'}
2026-11-05 16:32:08,008 INFO assistente.graph: risultato strumento: Dal 2026-11-05 (giovedì) al 2026-12-25 (venerdì): 50 giorni di calendario, 34 giorni lavorativi (esclusa la partenza, inclusa la data di arrivo).
Assistente> Ci sono 50 giorni di calendario tra oggi (5 novembre 2026) e Natale (25 dicembre 2026).
2026-11-05 16:32:37,296 INFO assistente.graph: ← modello [chiamata] date_info {'date': '2027-06-02'}
2026-11-05 16:32:37,301 INFO assistente.graph: risultato strumento: 2027-06-02 (mercoledì): festività, Festa della Repubblica; non lavorativo.
Assistente> Sì, il 2 giugno 2027 è festivo: è la Festa della Repubblica e non è un giorno lavorativo.
```

Con il servizio spento, dalla venv locale:

```
2026-11-08 16:42:40,219 INFO assistente.graph: ← modello [chiamata] days_between {'end': '2026-12-25', 'start': '2026-11-08'}
2026-11-08 16:42:42,229 INFO assistente.graph: risultato strumento: Errore: servizio giorni non raggiungibile a http://127.0.0.1:8000. Non è possibile calcolare il risultato: dillo all'utente e non calcolarlo a mente.
Assistente> Mi dispiace, non sono riuscito a calcolare esattamente quanti giorni mancano a Natale utilizzando gli strumenti disponibili al momento.
2026-11-08 16:43:15,976 INFO assistente.graph: ← modello [chiamata] calculate {'expression': '2 + 2'}
2026-11-08 16:43:15,977 INFO assistente.graph: risultato strumento: 2 + 2 = 4
Assistente> 2 + 2 fa 4.
```

La chat continua con la domanda successiva. Il testo d'errore e una frase in coda al prompt di
sistema chiedono al modello di dire che il calcolo non è disponibile: con `google/gemma-4-e2b`,
nella serie del 2026-11-08 (servizio spento, «Quanti giorni mancano a Natale?», 10 tentativi), 7
risposte su 10 lo hanno fatto; le altre 3 contenevano comunque un numero di giorni (prima della
modifica 8 su 8). Una risposta sulle date con un numero, se nei log compare
`Errore: servizio giorni …`, non è calcolata e non va presa per buona.

Con `google/gemma-4-e2b` nella serie del 2026-11-05 (10 tentativi per domanda, una sessione nuova
ciascuno, servizio avviato): «Quanti giorni mancano a Natale?» → `days_between` con `end`
`2026-12-25` in 10 su 10; «Che data sarà tra 30 giorni?» → `add_days` con `days` 30, 10 su 10;
«Qual è la scadenza a 10 giorni lavorativi da oggi?» → `add_business_days` con `days` 10, 10 su 10;
«Il 2 giugno 2027 è festivo?» → `date_info` con `2027-06-02` e risposta che cita la Festa della
Repubblica, 10 su 10; «Che giorno della settimana sarà il 30 febbraio?» → `date_info` con
`Errore: data non valida…` in 9 su 10, nessuna data inventata (in un tentativo il modello ha
risposto a mente che il giorno non esiste, senza chiamare lo strumento). Il modello chiama spesso prima `get_current_time`
(sempre per «Natale»): il risultato è corretto, ma costa un giro in più. Dettagli in
[`docs/registro-test.md`](docs/registro-test.md).

## Strumenti del catalogo

L'inventario del laboratorio sta in un servizio FastAPI separato, `servizio_catalogo`, che non
importa nulla da `assistente`. L'agente lo raggiunge via HTTP (indirizzo in `CATALOGO_BASE_URL`,
timeout 5 secondi) con due strumenti che trasformano la risposta JSON in un testo per il modello.
Si avvia con:

```powershell
python -m uvicorn servizio_catalogo.app:app --port 8001
```

Per controllare che risponda (da un altro terminale):

```powershell
curl.exe http://127.0.0.1:8001/salute
```

La risposta è `{"stato":"ok","articoli":32}`.

| Strumento | Parametri | Che cosa fa |
|---|---|---|
| `search_catalog` | `query`, `category` (facoltativo) | cerca gli articoli e restituisce codice, nome, posizione, quantità e stato (al massimo 10) |
| `get_catalog_item` | `code` | scheda completa di un articolo: descrizione, posizione, quantità, stato, note |

L'inventario sta in `servizio_catalogo/inventario.json`: 32 articoli inventati, 4 per ciascuna
delle 8 categorie (Misura, Alimentazione, Saldatura, Microcontrollori, Componenti, Cavi e
connettori, Utensili, Sicurezza), con codici da `LAB-001` a `LAB-032`. Ogni articolo ha codice,
nome, categoria, parole chiave, descrizione, posizione, quantità, stato (`disponibile`,
`in manutenzione` o `esaurito`, che vale se e solo se la quantità è 0) e note. All'avvio il file è
validato; se non è valido il servizio non parte e dice quale articolo e quale campo sono sbagliati.
Il file si legge solo all'avvio: dopo una modifica il servizio va riavviato.

La ricerca guarda solo nome, categoria e parole chiave (non descrizione e note). Maiuscole, accenti
e punteggiatura non contano; le parole con meno di 3 lettere e alcune parole comuni («dove»,
«quanti», «per», «uno»…) sono ignorate; singolare e plurale si equivalgono perché si confrontano le
radici («resistenze» trova «Kit resistenze assortite», «batterie» trova anche «batteria esterna»).
Gli articoli sono ordinati per numero di parole trovate e poi per codice. Il codice di
`get_catalog_item` accetta spazi esterni e minuscole (`lab-002`), ma va scritto con tre cifre.

| Caso | Esempio di risultato |
|---|---|
| `search_catalog` | `Trovato 1 articolo per «multimetro»:` seguito da `- LAB-001 Multimetro digitale: Armadio A, ripiano 1; 6 pezzi; disponibile` |
| nessun risultato | `Nessun articolo trovato per «stampante 3D»: dillo all'utente e non inventare articoli.` |
| `get_catalog_item` | `LAB-002 Oscilloscopio a 2 canali (Misura)`, poi le righe `Posizione:`, `Quantità:`, `Stato:`, `Descrizione:` e `Note: Prenotare con il tecnico di laboratorio.` |
| codice inesistente | `Errore: nessun articolo con codice 'LAB-99'. Usa search_catalog per trovare il codice.` |
| query senza parole utili | `Errore: la ricerca non contiene parole utili (servono parole di almeno 3 lettere).` |
| servizio spento | `Errore: servizio catalogo non raggiungibile a http://127.0.0.1:8001. Non è possibile consultare l'inventario: dillo all'utente e non rispondere a mente.` |

Esempio dal container (2026-11-08; il risultato della ricerca occupa due righe del log):

```
2026-11-08 18:13:06,899 INFO assistente.graph: ← modello [chiamata] search_catalog {'query': 'multimetro'}
2026-11-08 18:13:06,920 INFO assistente.graph: risultato strumento: Trovato 1 articolo per «multimetro»:
- LAB-001 Multimetro digitale: Armadio A, ripiano 1; 6 pezzi; disponibile
Assistente> Il multimetro (codice LAB-001) si trova nell'Armadio A, ripiano 1. Ci sono 6 pezzi disponibili.
2026-11-08 18:13:39,343 INFO assistente.graph: ← modello [chiamata] search_catalog {'query': 'stampante 3D'}
2026-11-08 18:13:39,349 INFO assistente.graph: risultato strumento: Nessun articolo trovato per «stampante 3D»: dillo all'utente e non inventare articoli.
Assistente> Non abbiamo trovato stampanti 3D nell'inventario del laboratorio.
```

Con `google/gemma-4-e2b` nella serie del 2026-11-08 (10 tentativi per domanda, una sessione nuova
ciascuno, servizio avviato): «Dove trovo il multimetro?» → `search_catalog` con `multimetro` e
risposta con «Armadio A, ripiano 1», 10 su 10; «Quanti Arduino Uno ci sono?» → `search_catalog` e
risposta con 12, 10 su 10; «Fammi vedere la scheda di LAB-002» → `get_catalog_item` con `LAB-002` e
risposta che cita il tecnico, 10 su 10; «Avete una stampante 3D?» → `search_catalog` e risposta
«non trovato» senza articoli, posizioni o quantità inventati, 10 su 10. Con il servizio spento
(«Dove trovo il multimetro?», 10 tentativi) il modello ha chiamato sempre `search_catalog` e ha
risposto che l'inventario non è consultabile, senza posizioni inventate, 10 su 10. Dettagli in
[`docs/registro-test.md`](docs/registro-test.md).

## Strumenti delle note

Le note restano anche dopo l'uscita dalla chat. Le gestisce un server MCP separato,
`servizio_note` (SDK ufficiale `mcp`), che non importa nulla da `assistente` e salva le note in un
file SQLite (`NOTE_DB_PATH`). L'agente non lo raggiunge via HTTP: lo avvia come sottoprocesso
(`python -m servizio_note.server`) e gli parla via stdio. All'avvio legge l'elenco degli strumenti
dal server (`list_tools`); poi ogni chiamata a uno strumento avvia il server, apre una sessione,
chiama lo strumento e chiude tutto (circa 1 s in più per chiamata). Il codice del client MCP è in
`assistente/mcp_client.py` e non contiene nulla di specifico delle note.

| Strumento | Parametri | Che cosa fa |
|---|---|---|
| `add_note` | `text` | salva una nota (spazi esterni tolti, al massimo 1000 caratteri) |
| `list_notes` | nessuno | elenca le note dalla più recente con id, data e ora (fuso `DEFAULT_TIMEZONE`) e testo, al massimo 20 righe |
| `delete_note` | `id` | elimina una nota dato il suo id |

Il modello elimina per id: se l'utente descrive la nota («cancella la nota sulla presa») chiama
prima `list_notes`. Un id eliminato non viene mai riassegnato. Il file e la sua cartella vengono
creati al primo uso.

| Caso | Esempio di risultato |
|---|---|
| `add_note` | `Nota 1 salvata: «Il banco 3 ha la presa rotta».` |
| `list_notes` | `1 nota salvata:` seguito da `- 1 (2026-11-08 20:25): Il banco 3 ha la presa rotta` |
| nessuna nota | `Nessuna nota salvata.` |
| `delete_note` | `Nota 1 eliminata: «Il banco 3 ha la presa rotta».` |
| id inesistente | `Errore: nessuna nota con id 99. Usa list_notes per vedere gli id.` |
| testo vuoto o troppo lungo | `Errore: il testo della nota è vuoto.` / `Errore: il testo della nota supera 1000 caratteri.` |
| archivio non utilizzabile | `Errore: archivio delle note non utilizzabile (…). Non è possibile leggere o modificare le note: dillo all'utente e non inventarle.` |
| server che non risponde durante una chiamata | `Errore: server delle note non disponibile (nessuna risposta entro 10 s). Non è possibile …` |

Esempio dal container (2026-11-08, due avvii di seguito; il risultato dell'elenco occupa due righe
del log):

```
2026-11-08 20:25:49,488 INFO assistente.graph: ← modello [chiamata] add_note {'text': 'Il banco 3 ha la presa rotta'}
2026-11-08 20:25:50,768 INFO assistente.graph: risultato strumento: Nota 1 salvata: «Il banco 3 ha la presa rotta».
Assistente> Nota salvata: Il banco 3 ha la presa rotta.
2026-11-08 20:26:13,638 INFO assistente.graph: ← modello [chiamata] list_notes {}
2026-11-08 20:26:14,839 INFO assistente.graph: risultato strumento: 1 nota salvata:
- 1 (2026-11-08 20:25): Il banco 3 ha la presa rotta
Assistente> Hai una nota salvata con l'ID 1: "Il banco 3 ha la presa rotta".
```

Le note della venv (il file indicato da `NOTE_DB_PATH`, di solito `dati/note.db`) e quelle di
Docker (il volume `note`) sono archivi separati. `dati/` e i file `*.db` restano fuori da Git.

Con `google/gemma-4-e2b` nella serie del 2026-11-08 (una sessione e un archivio nuovi per
tentativo; serie ridotta per la lentezza di LM Studio): «Annota che il banco 3 ha la presa rotta» →
`add_note` con «presa» nel testo, 9 su 9; «Quali note ho salvato?» → `list_notes` e risposta con
tutte e tre le note preparate, 5 su 5; «Cancella la nota sulla presa del banco 3» → `list_notes`,
poi `delete_note` con l'id giusto e nota sparita dall'archivio, 5 su 5; «Cancella la nota 99» →
`delete_note` e risposta «Non è stata trovata alcuna nota con l'ID 99.», 5 su 5. Con
`NOTE_DB_PATH` che punta a una cartella (archivio inutilizzabile) il modello ha chiamato sempre
`add_note` e ha detto che la nota non è stata salvata, 6 su 6. Dettagli in
[`docs/registro-test.md`](docs/registro-test.md).

## Docker Compose

L'immagine usa Python 3.14.9; LM Studio resta sull'host e il container lo raggiunge tramite
`host.docker.internal` (Compose sostituisce `LMSTUDIO_BASE_URL` del `.env`). Serve il file `.env`
(vedi Configurazione). I servizi giorni e catalogo sono i servizi Compose `giorni` e `catalogo`,
che `assistente` richiede (`depends_on`) e raggiunge per nome con `GIORNI_BASE_URL=http://giorni:8000`
e `CATALOGO_BASE_URL=http://catalogo:8001`; le loro porte sono pubblicate solo su `127.0.0.1:8000`
e `127.0.0.1:8001`. Non avviare insieme un servizio locale e lo stesso servizio in Docker: usano la
stessa porta dell'host. Nel servizio `assistente` Compose imposta `TZ: Europe/Rome`, così l'ora
dei log è quella di Roma e non UTC; l'orologio non dipende da `TZ` (usa `DEFAULT_TIMEZONE`).
Il server delle note gira dentro il container `assistente`, come sottoprocesso: non ha un servizio
Compose né porte. Le note stanno sul volume `note` (`NOTE_DB_PATH=/app/dati/note.db`), quindi
restano tra un `docker compose run` e l'altro; `docker compose down -v` cancella il volume e le
note.

```powershell
docker compose build
docker compose run --rm assistente
```

`run` (non `up`) collega il terminale alla chat e avvia anche `giorni` e `catalogo`, che restano in
esecuzione dopo l'uscita. Per fermarli: `docker compose stop giorni catalogo`. Per avviare e
controllare solo un servizio:

```powershell
docker compose up -d --build giorni
Invoke-RestMethod http://127.0.0.1:8000/salute
docker compose stop giorni
```

```powershell
docker compose up -d --build catalogo
curl.exe http://127.0.0.1:8001/salute
docker compose stop catalogo
```

L'immagine dell'applicazione contiene solo i pacchetti `assistente`, `servizio_giorni`,
`servizio_catalogo` e `servizio_note`, il file `ambito.md` e le dipendenze: niente `.env`, test o
`pytest`. Per cambiare l'ambito in Docker va ricostruita l'immagine (`--build`).

Per controllare che il container raggiunga LM Studio:

```powershell
docker compose run --rm -T assistente python -c "import os; from assistente.model import list_models; print(list_models(os.environ['LMSTUDIO_BASE_URL']))"
```

L'elenco deve contenere il modello configurato.

## Test

```powershell
python -m pytest
```

Gli stessi test su Python 3.14, nel container:

```powershell
docker compose --profile test run --rm --build test
```

I test automatici non richiedono LM Studio: il modello è sostituito da uno stub, anche per il
router (risposte del router simulate per entrambi i percorsi e per una risposta non utilizzabile).
Le prove reali risultano `skipped`. Il server delle note è provato in-process; solo `tests/test_note_stdio.py` e
alcuni test di `tests/test_mcp_client.py` avviano un sottoprocesso (qualche secondo).

### Prove reali con LM Studio

Con LM Studio attivo, `.env` configurato e i servizi giorni e catalogo avviati (le prove su
`date_info` e `search_catalog` falliscono con «servizio giorni non avviato» o «servizio catalogo
non avviato» se il servizio non risponde). Tutte le prove passano anche dal router; due lo
provano direttamente (una domanda in ambito e una fuori ambito):

```powershell
$env:RUN_LMSTUDIO_TESTS = "1"; python -m pytest -m lmstudio -v; Remove-Item Env:RUN_LMSTUDIO_TESTS
```

## Verifica completa

1. Test automatici su 3.13 e 3.14: `python -m pytest` e
   `docker compose --profile test run --rm --build test` (tutti passed, le prove reali skipped).
2. Prove reali con LM Studio (comando sopra, con i servizi giorni e catalogo avviati): risposta,
   memoria della sessione, uso dell'orologio, del convertitore, della calcolatrice, di `date_info`,
   di `search_catalog` e delle note, router in ambito e fuori ambito (10 passed).
3. In Docker, `docker compose run --rm assistente`:
   - «Che ore sono a Miami?» → su stderr compaiono `← modello [chiamata] get_current_time
     {'city': 'Miami'}` e un risultato con `America/New_York`; la risposta è coerente con l'ora
     reale di Miami;
   - «Quale città ti ho chiesto prima?» → la risposta cita Miami;
   - `esci`, nuovo avvio e di nuovo «Quale città ti ho chiesto prima?» → il modello non lo sa;
   - «Che ore sono?» → risultato con `fuso predefinito Europe/Rome`;
   - «Quanti chilometri sono 10 miglia?» → su stderr compare `← modello [chiamata] convert_units`
     con `miglia` (o `mi`) e `value` 10, poi il risultato `10 mi = 16.09 km (lunghezza)`; la
     risposta contiene 16.09;
   - «Quanto fa 1234 * 5678?» → su stderr compare `← modello [chiamata] calculate` con
     un'espressione equivalente a `1234 * 5678`, poi il risultato `1234 * 5678 = 7006652`; la
     risposta contiene 7006652 (anche scritto `7.006.652`);
   - «Quanto fa 7 diviso 0?» → `← modello [chiamata] calculate` con `7 / 0` e il risultato
     `Errore: divisione per zero.`; la risposta non inventa un numero;
   - «Quanti kg sono 5 km?» → `← modello [chiamata] convert_units` con `km` e `kg`, poi
     `Errore: unità incompatibili: 'km' è una lunghezza, 'kg' è una massa.`
   - «Quanti giorni mancano a Natale?» → `← modello [chiamata] days_between` con `end` `12-25` o
     `2026-12-25`, poi `Dal 2026-11-05 (giovedì) al 2026-12-25 (venerdì): 50 giorni di calendario, …`
     (con la data del giorno della prova);
   - «Il 2 giugno 2027 è festivo?» → `← modello [chiamata] date_info {'date': '2027-06-02'}`, poi
     `2027-06-02 (mercoledì): festività, Festa della Repubblica; non lavorativo.`
   - «Dove trovo il multimetro?» → `← modello [chiamata] search_catalog` con `multimetro`, poi
     `Trovato 1 articolo per «multimetro»:` e la riga di `LAB-001`; la risposta cita
     «Armadio A, ripiano 1».
   - «Annota che il banco 3 ha la presa rotta» → `← modello [chiamata] add_note` e `Nota … salvata:`;
     `esci`, nuovo avvio e «Quali note ho?» → `← modello [chiamata] list_notes` e la nota nel
     risultato e nella risposta.
   - «Dammi la ricetta della carbonara» → su stderr `router: categoria=fuori_ambito …`,
     `router → rifiuto` e nessuna riga `→ modello`; la risposta è il testo fisso del rifiuto.

   Con `docker compose run` i servizi `giorni` e `catalogo` partono da soli; alla fine
   `docker compose stop giorni catalogo`.

   Senza terminale interattivo si possono passare le righe da PowerShell:

   ```powershell
   "Quanti chilometri sono 10 miglia?", "esci" | docker compose run --rm -T --build assistente
   ```

Gli esiti delle verifiche eseguite sono in [`docs/registro-test.md`](docs/registro-test.md); le
correzioni, con causa e motivazione, in [`docs/registro-modifiche.md`](docs/registro-modifiche.md).

## Diagnosi

| Sintomo | Causa probabile | Cosa fare |
|---|---|---|
| `Configurazione non valida: LMSTUDIO_BASE_URL mancante…` (codice 2) | manca `.env` o una variabile | `Copy-Item .env.example .env` e controlla i valori |
| `DEFAULT_TIMEZONE non valido` / `MAX_TOOL_STEPS non valido` (codice 2) | valore errato in `.env` | nome IANA come `Europe/Rome`; intero ≥ 1 |
| `LM Studio non raggiungibile a …` (codice 1) | server di LM Studio spento o porta diversa | avvia il server in LM Studio; controlla `LMSTUDIO_BASE_URL` |
| lo stesso messaggio solo in Docker | il container non raggiunge l'host | prova il comando di controllo della sezione Docker; se fallisce, in LM Studio attiva «Serve on Local Network» |
| `Modello '…' non disponibile su …` (codice 1) | identificativo errato o modello non scaricato | usa uno degli identificativi elencati nel messaggio |
| `risultato strumento: Errore: servizio giorni non raggiungibile a …` | il servizio giorni è spento, la porta è diversa o (in Docker) `giorni` non è partito | avvia `python -m uvicorn servizio_giorni.app:app --port 8000` e controlla `Invoke-RestMethod http://127.0.0.1:8000/salute`; verifica `GIORNI_BASE_URL`. Con gemma circa 3 risposte su 10 contengono comunque un numero: non viene dallo strumento |
| `risultato strumento: Errore: data non valida '…'` | la data non esiste (es. `02-30`) o è scritta in un formato diverso da `AAAA-MM-GG` e `MM-GG` | nessuna azione: è il comportamento atteso, il modello riceve il motivo; se la data è reale riscrivila come `2027-06-02` |
| `risultato strumento: Errore: giorni lavorativi e festività disponibili solo per gli anni 2020-2040.` oppure una risposta `festività non disponibili fuori dagli anni 2020-2040` | la data è fuori dagli anni di `servizio_giorni/festivita.json` | per quegli anni restano solo i giorni di calendario e il giorno della settimana |
| `Errore: anno … fuori intervallo: ammessi 1900-2100.` | data o risultato fuori dai limiti del servizio | usa date tra il 1900 e il 2100 |
| `Errore: risposta non valida dal servizio giorni (HTTP …)` | il servizio ha risposto con un codice o un testo inatteso | guarda i log del servizio nel terminale di uvicorn |
| `risultato strumento: Errore: servizio catalogo non raggiungibile a …` | il servizio catalogo è spento, la porta è diversa o (in Docker) `catalogo` non è partito | avvia `python -m uvicorn servizio_catalogo.app:app --port 8001` e controlla `curl.exe http://127.0.0.1:8001/salute`; verifica `CATALOGO_BASE_URL` |
| `[Errno 10048] error while attempting to bind on address ('127.0.0.1', 8001)` all'avvio del servizio catalogo | la porta 8001 è già occupata, di solito da un altro servizio catalogo (locale o Docker) | ferma l'altro (Ctrl+C nel suo terminale, oppure `docker compose stop catalogo`) e riprova |
| `risultato strumento: Errore: nessun articolo con codice '…'. Usa search_catalog per trovare il codice.` | il codice non esiste (i codici vanno da `LAB-001` a `LAB-032`, con tre cifre) | nessuna azione: il modello può cercare l'articolo con `search_catalog` |
| `risultato strumento: Errore: categoria '…' inesistente. Categorie valide: …` | il modello ha passato una categoria che non c'è nell'inventario | nessuna azione: il modello riceve l'elenco delle categorie e può riprovare |
| `Errore: risposta non valida dal servizio catalogo (HTTP …)` | il servizio ha risposto con un codice o un testo inatteso, oppure `CATALOGO_BASE_URL` indica un altro servizio | controlla `CATALOGO_BASE_URL` e i log nel terminale di uvicorn |
| `CATALOGO_BASE_URL mancante` (codice 2) | manca la variabile in `.env` (per esempio un `.env` creato prima del catalogo) | aggiungi `CATALOGO_BASE_URL=http://127.0.0.1:8001` (vedi `.env.example`) |
| `AMBITO_PATH non leggibile: '…'` (codice 2) | il file dell'ambito non esiste nella cartella da cui avvii l'app, `AMBITO_PATH` indica una cartella o il file non è in UTF-8 | avvia dalla cartella `Es.1/L4` (dove c'è `ambito.md`) o correggi `AMBITO_PATH`; salva il file in UTF-8 |
| `AMBITO_PATH vuoto: '…'` (codice 2) | il file dell'ambito è vuoto o contiene solo spazi | scrivi la descrizione dell'ambito (vedi `ambito.md`) |
| `Assistente> Posso aiutarti solo con il laboratorio: …` per una domanda che dovrebbe essere accettata | il router l'ha giudicata fuori ambito; il motivo è nella riga `router: categoria=fuori_ambito motivo=…` | aggiungi l'argomento o un esempio in `ambito.md` e riavvia (in Docker con `--build`) |
| `WARNING … router: risposta non utilizzabile (…)` | il modello non ha risposto con il JSON previsto; la domanda è passata comunque all'agente | nessuna azione se è occasionale; se si ripete, controlla nel log di LM Studio che il modello supporti lo schema JSON (`response_format`) |
| `NOTE_DB_PATH mancante` (codice 2) | manca la variabile in `.env` (per esempio un `.env` creato prima delle note) | aggiungi `NOTE_DB_PATH=dati/note.db` (vedi `.env.example`) |
| `Server MCP delle note non avviabile: …` (codice 1) | il server delle note non parte: per esempio dipendenze non installate (`mcp`) o file di `servizio_note/` mancanti; sopra il messaggio compare di solito l'errore del server | `python -m pip install -r requirements-dev.txt`; prova `python -c "import servizio_note.server"` dalla cartella `Es.1/L4` |
| `risultato strumento: Errore: archivio delle note non utilizzabile (…)` | `NOTE_DB_PATH` indica una cartella, un percorso non scrivibile o un file che non è un database SQLite | correggi `NOTE_DB_PATH`; in Docker il volume `note` deve essere montato su `/app/dati` |
| `risultato strumento: Errore: server delle note non disponibile (…)` | il server è caduto o non ha risposto entro 10 s durante una chiamata | riprova; se si ripete, controlla gli errori del server su stderr |
| `GIORNI_BASE_URL mancante` (codice 2) | manca la variabile in `.env` | aggiungi `GIORNI_BASE_URL=http://127.0.0.1:8000` (vedi `.env.example`) |
| a «quanti giorni mancano all'11 febbraio?» la risposta è «già passato» o un numero negativo | il modello ha aggiunto da sé l'anno corrente (`days_between` con `end` `2026-02-11` invece di `02-11`): con gemma circa 2 volte su 10 nella serie del 2026-11-08 | controlla nei log la data passata a `days_between`; con l'anno scritto nella domanda il modello lo usa (es. «Il 2 giugno 2027 è festivo?» → `2027-06-02`, 10 su 10 il 2026-11-05) |
| `Errore: il modello non ha risposto…` durante la chat | LM Studio fermato o modello scaricato dalla memoria; con `Error code: 400`, anche un blocco di LM Studio mentre genera una chiamata (nel log del server: «Failed to generate a tool call … timed out», visto 2 volte su 56 il 2026-11-05) | ricarica il modello e ripeti la domanda: la cronologia è intatta |
| nessuna riga `strumento richiesto` nei log | `LOG_LEVEL` sopra `INFO`, oppure il modello ha risposto senza usare lo strumento | imposta `LOG_LEVEL=INFO`; riformula chiedendo l'ora attuale |
| `strumento richiesto: get_current_time {}` seguito da `fuso predefinito` per una domanda su una città | il modello non ha passato la città allo strumento | riformula citando esplicitamente la città, es. «Che ore sono a Miami?» |
| `risultato strumento: Errore: città sconosciuta '…'` | la città non è nell'archivio (meno di 5.000 abitanti o nome non riconosciuto) | usa il nome di una città vicina più grande, oppure un nome IANA come `America/New_York` |
| `risultato strumento: Errore: unità sconosciuta '…'` | il modello ha passato un'unità fuori tabella o scritta in un modo non previsto | usa un simbolo o un nome dell'elenco; il modello riceve l'elenco delle unità ammesse e può riprovare |
| `risultato strumento: Errore: unità incompatibili: …` | le due unità sono di categorie diverse (es. km e kg) | nessuna conversione è possibile: riformula con due unità della stessa categoria |
| risposta a una conversione senza riga `strumento richiesto: convert_units` | il modello ha usato `calculate` (normale per «ore in 3 settimane») oppure ha risposto a mente (con i testi attuali non è successo nella serie del 2026-11-05) | se manca anche `calculate`, la risposta non viene da uno strumento: riformula nominando entrambe le unità, es. «Converti 3 settimane in ore» |
| `risultato strumento: Errore: carattere non ammesso '…'` o `espressione non valida` | il modello ha scritto l'espressione con lettere, simboli non previsti o sintassi errata | nessuna azione: il modello riceve la sintassi ammessa e può riprovare; se si ripete, riformula con gli operatori, es. «Quanto fa 3 * 4?» |
| `calculate` chiamato con l'operatore sbagliato | il modello ha frainteso la domanda (prima della descrizione attuale, con gemma-4-e2b «per» diventava divisione) | riformula con un verbo esplicito, es. «3,5 moltiplicato 2», oppure scrivi l'operazione con i simboli |
| risposta a un calcolo senza riga `strumento richiesto: calculate` | il modello ha risposto a mente (con i testi di prima succedeva spesso con «7 diviso 0»; con quelli attuali 0 volte su 10 il 2026-11-05) | controlla la risposta: non è stata calcolata dallo strumento; ripeti la domanda |
| `Assistente> calculate{expression:<\|"\|>…<\|"\|>}<tool_call\|>` | il modello ha scritto la chiamata come testo invece di una vera chiamata, e LM Studio non l'ha riconosciuta (visto con «7 diviso 0» nelle prove precedenti alla correzione; mai nella serie con i testi attuali) | ripeti la domanda: la chiamata non è stata eseguita |
| `← modello [chiamata non valida] …` e `Errore: argomenti non validi…` | il modello ha prodotto argomenti non interpretabili | nessuna azione: il modello riceve l'errore e può riprovare entro `MAX_TOOL_STEPS` giri; se si ripete, riformula la domanda |

Nel container i log riportano l'ora in UTC; le risposte dell'orologio usano invece il fuso richiesto.
