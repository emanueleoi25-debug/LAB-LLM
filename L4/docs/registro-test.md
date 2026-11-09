# Registro dei test

Esiti delle verifiche eseguite sull'assistente. Ogni sessione indica data, commit, ambiente e
comandi; i test elencati per nome sono quelli raccolti da pytest.

## Sessione del 2026-11-09 (14) — commit `1c5962b`

Router, step 1 della lezione 6 (spec `2026-11-09-router-design.md`, piano Task 1-6, branch
`feat/router`, esecuzione Native). **LM Studio spento per tutta la sessione**: spike, prove reali,
serie e checklist Docker non eseguiti (vedi «Resta da provare»).

| Verifica | Ambiente | Comando | Esito |
|---|---|---|---|
| Suite senza modello, su `1c5962b` | venv locale, Python 3.13 | `python -m pytest` | 562 passed, 10 skipped (le prove reali, comprese le 2 nuove del router) |
| Suite senza modello, su `1c5962b` | container `test`, Python 3.14.9 | `docker compose --profile test run --rm --build test` | 562 passed, 10 skipped |
| File dell'ambito mancante | venv locale | `python -m assistente` con `AMBITO_PATH=manca.md` | `Configurazione non valida: AMBITO_PATH non leggibile: 'manca.md' ([Errno 2] No such file or directory: 'manca.md')`, uscita 2 |
| File dell'ambito vuoto | venv locale | `python -m assistente` con `AMBITO_PATH` = un file di soli spazi | `Configurazione non valida: AMBITO_PATH vuoto: '…'`, uscita 2 |
| Ambito predefinito | venv locale, LM Studio spento | `python -m assistente` | configurazione accettata; `LM Studio non raggiungibile a http://127.0.0.1:1234/v1: …`, uscita 1 |
| `ambito.md` nell'immagine | container `assistente` | `docker compose run --rm -T --build assistente python -c "from assistente.config import load_settings; print(repr(load_settings().ambito[:45]))"` | `"# Ambito dell'assistente del laboratorio\n\nRie"` |

Test nuovi, ciascun gruppo visto fallire prima del codice: 7 in `tests/test_config.py` (ambito
predefinito, percorso, BOM, file mancante, cartella, file non UTF-8, file vuoto); 17 in
`tests/test_router.py` (decisioni valide, 10 risposte non utilizzabili, contenuto non testuale,
prompt e ambito, contesto degli ultimi 4 messaggi, contesto vuoto); 1 in `tests/test_model.py`
(modello del router con schema, `temperature=0`, senza strumenti); 8 in `tests/test_graph.py`
(nodi, in ambito, fuori ambito senza agente, risposta non utilizzabile, cronologia, ciclo strumenti
e limite dopo il router, rifiuto seguito da una domanda in ambito); 2 in `tests/test_cli.py`
(`create_graph` con il router, errore del router che scarta la domanda); 2 prove reali in
`tests/integration/test_lmstudio.py` (skipped). I due test sui nomi dei nodi passano da `modello` ad
`agente`; `test_environment_wins_over_dotenv` crea un `ambito.md` di prova nella cartella
temporanea.

### Resta da provare

- Spike del `response_format` con `google/gemma-4-e2b` (Task 1): LM Studio accetta lo schema e
  gemma lo rispetta?
- Prove reali con LM Studio e i servizi giorni e catalogo avviati: atteso 10 passed.
- Serie del router (spec §7.2 punto 3): 6 domande in ambito e 4 fuori ambito; criterio 0 falsi
  rifiuti e almeno 3 rifiuti su 4.
- Checklist Docker: «Dammi la ricetta della carbonara» → rifiuto, senza righe `→ modello`.
- Esempio di log reale del router nel README (oggi il README riporta il formato delle righe).

## Sessione del 2026-11-08 (13) — commit `9cef1c5`

Note persistenti (spec `2026-11-08-note-persistenti-design.md`, piano Task 1-6, branch
`feat/note-persistenti`). Modello `google/gemma-4-e2b` in LM Studio sull'host. Il `.env` locale non
ha ancora `CATALOGO_BASE_URL` e `NOTE_DB_PATH`: nelle prove dalla venv le variabili sono state
passate nell'ambiente del comando, con l'archivio nella scratchpad. Serie con uno script usa e
getta nella scratchpad (`create_graph` + `ask`, una sessione e un archivio nuovi per tentativo).

| Verifica | Ambiente | Comando | Esito |
|---|---|---|---|
| Suite senza modello, su `0a00074` | venv locale, Python 3.13.14 | `python -m pytest` | 524 passed, 7 skipped |
| Suite senza modello, su `1421b3d` | container `test`, Python 3.14.9 | `docker compose --profile test run --rm --build test` | 524 passed, 7 skipped (compreso il test stdio nel container) |
| Dipendenza `mcp==2.3.0` | venv locale | `python -m pip install -r requirements-dev.txt`, `python -m pip check` | `No broken requirements found.` |
| Persistenza dalla venv | venv locale | due `python -m assistente` di seguito: «Annota che il banco 3 ha la presa rotta», poi «Quali note ho?» | `add_note` → `Nota 1 salvata: «Il banco 3 ha la presa rotta».`; al secondo avvio `list_notes` → la nota, risposta che la cita |
| Avvio senza la variabile | venv locale | `python -m assistente` con `NOTE_DB_PATH` vuota | `Configurazione non valida: NOTE_DB_PATH mancante`, uscita 2 |
| Server delle note che non parte | venv locale, script usa e getta con `PROJECT_DIR` senza `servizio_note` | `main()` | sopra, l'errore del server `No module named 'servizio_note'`; poi `Server MCP delle note non avviabile: Connection closed`, uscita 1 |
| Persistenza in Docker | container `assistente` + LM Studio sull'host | `"Annota che il banco 3 ha la presa rotta", "esci" \| docker compose run --rm -T --build assistente`, poi `"Quali note ho?", "esci" \| docker compose run --rm -T assistente` | `add_note` e poi `list_notes` con `- 1 (2026-11-08 20:25): Il banco 3 ha la presa rotta`; volume `assistente-laboratorio_note` creato |
| Errore previsto in Docker | come sopra | `"Cancella la nota 99", "esci" \| docker compose run --rm -T assistente` | `delete_note {'id': 99}` → `Errore: nessuna nota con id 99. Usa list_notes per vedere gli id.`; risposta «Non è stata trovata alcuna nota con l'ID 99.»; nessuna riga `Tool '…' failed` su stderr |
| Prove reali con LM Studio, servizi giorni e catalogo avviati | venv locale | `RUN_LMSTUDIO_TESTS=1 … python -m pytest -m lmstudio -v` | 8 passed (731,76 s: LM Studio più lento del solito, 143 s il 2026-11-08 per 7 prove) |
| Serie della spec §7 | venv locale | 30 tentativi (vedi sotto) | 30 su 30 |

Test nuovi: `tests/test_archivio_note.py` (6), `tests/test_server_note.py` (21, server in-process
con `mcp.Client`), `tests/test_mcp_client.py` (9, compresi tre avvii di sottoprocessi che falliscono
o non rispondono), `tests/test_note_stdio.py` (1, server vero via stdio), 2 in
`tests/test_config.py`, 3 in `tests/test_cli.py`; `test_system_prompt_ends_with_catalog_rule` è
diventato `test_system_prompt_contains_catalog_rule`. Ogni gruppo è stato visto fallire prima del
codice. Dopo il test del server bloccato non resta alcun processo `python` orfano.

Serie (decisione dell'utente: 30 tentativi invece di 50 per la lentezza di LM Studio, soglia della
spec letta in proporzione; nessun errore di LM Studio, nessuna chiamata scritta come testo):

| Domanda | Archivio | Esito |
|---|---|---|
| «Annota che il banco 3 ha la presa rotta» | vuoto | 9 su 9 `add_note` con «presa» nel testo (serie fermata durante il decimo tentativo) |
| «Quali note ho salvato?» | 3 note | 5 su 5 `list_notes` e risposta con le tre note e i loro id; ora delle note (18:00 UTC) riportata come 19:00 |
| «Cancella la nota sulla presa del banco 3» | 3 note | 5 su 5 `list_notes` poi `delete_note {'id': 2}`; nell'archivio restano le note 1 e 3 |
| «Cancella la nota 99» | 3 note | 5 su 5 `delete_note {'id': 99}` e risposta «Non è stata trovata alcuna nota con l'ID 99.» |
| «Annota che il banco 3 ha la presa rotta» | `NOTE_DB_PATH` = una cartella | 6 su 6 `add_note` → `Errore: archivio delle note non utilizzabile (unable to open database file). …`; risposte come «Mi dispiace, non sono riuscito a salvare la nota. L'archivio delle note non è utilizzabile in questo momento.»; nessuna dice che la nota è salvata |

Correzione dopo la revisione (spec §9.1, commit `a3f90e0`): `test_delete_note_huge_id_is_unknown`
fallito prima della correzione (testo `Error executing tool delete_note`, cioè il crash) e superato
dopo; suite 527 passed, 8 skipped su 3.13.14; via stdio vero `delete_note` con `10**30` →
`Errore: nessuna nota con id 1000000000000000000000000000000. Usa list_notes per vedere gli id.` e
nessuna riga su stderr. Revisione finale (subagent opus): «Ready to merge», 0 critici, 0 importanti.

### Resta da provare

- Checklist da terminale interattivo vero (senza `-T`), con le voci delle note.
- La verifica completa prima del push (tutte le voci della checklist Docker).
- Nel volume Docker `assistente-laboratorio_note` resta la nota 1 di prova.

## Sessione del 2026-11-08 (12) — commit `7123f77`

Correzione dopo la revisione finale del catalogo (spec §9.1, piano Task 7, branch
`feat/catalogo-locale`): un 404 di `/articolo` senza il testo `nessun articolo con codice ` è una
risposta non valida.

| Verifica | Ambiente | Comando | Esito |
|---|---|---|---|
| Test nuovo prima della correzione | venv locale, Python 3.13.14 | `python -m pytest tests/test_catalog.py` | 1 failed (`test_invalid_responses[get_catalog_item-…-404]`: `Errore: Not Found Usa search_catalog…`), 34 passed |
| Stesso file dopo la correzione | venv locale, Python 3.13.14 | `python -m pytest tests/test_catalog.py` | 35 passed |
| Suite senza modello | venv locale, Python 3.13.14 | `python -m pytest` | 482 passed, 7 skipped |
| Suite senza modello | container `test`, Python 3.14.9 | `docker compose --profile test run --rm --build test` | 482 passed, 7 skipped |

Prove reali non rieseguite: la correzione non cambia i testi visti dal modello con il servizio
catalogo corretto.

### Resta da provare

- La verifica completa prima del push (suite 3.13 e 3.14, LM Studio, checklist Docker di tutti gli
  strumenti).

## Sessione del 2026-11-08 (11) — commit `60155c1`, suite rieseguite su `ac907fb`

Catalogo locale (spec `2026-11-08-catalogo-locale-design.md`, piano Task 1-6, branch
`feat/catalogo-locale`). Servizi, prove reali, serie e checklist sono stati eseguiti su `3dbcaf3`
(codice completo) e `60155c1` (in più la prova reale del catalogo). Modello `google/gemma-4-e2b` in LM Studio sull'host. Il `.env` locale non
ha ancora `CATALOGO_BASE_URL`: nelle prove dalla venv la variabile è stata passata nell'ambiente del
comando (`CATALOGO_BASE_URL=http://127.0.0.1:8001`). Serie con uno script usa e getta nella
scratchpad (`create_graph` + `ask`, una sessione nuova per tentativo).

| Verifica | Ambiente | Comando | Esito |
|---|---|---|---|
| Suite senza modello, su `3dbcaf3` | venv locale, Python 3.13.14 | `python -m pytest` | 481 passed, 6 skipped |
| Suite senza modello, su `3dbcaf3` | container `test`, Python 3.14.9 | `docker compose --profile test run --rm --build test` | 481 passed, 6 skipped |
| Suite senza modello, su `ac907fb` (dopo la revisione finale) | venv locale, Python 3.13.14, e container `test`, Python 3.14.9 | gli stessi due comandi | 481 passed, 7 skipped su entrambe (la settima prova saltata è `test_real_model_uses_catalog`) |
| Servizio catalogo locale | venv locale | `python -m uvicorn servizio_catalogo.app:app --port 8001`, poi `curl` su `/cerca?q=multimetro` e `/articolo?codice=LAB-99` | JSON con LAB-001; 404 `nessun articolo con codice 'LAB-99'.` |
| Servizio catalogo in Compose | container `catalogo`, Python 3.14.9 | `docker compose up -d --build catalogo`, `curl.exe http://127.0.0.1:8001/salute` (Git Bash e PowerShell) | `{"stato":"ok","articoli":32}`; poi `docker compose stop catalogo` |
| Porta 8001 occupata | venv locale, servizio già avviato | secondo `python -m uvicorn servizio_catalogo.app:app --port 8001` | `[Errno 10048] error while attempting to bind on address ('127.0.0.1', 8001)`, uscita 3 |
| Avvio con il `.env` senza la variabile | venv locale | `python -m assistente` | `Configurazione non valida: CATALOGO_BASE_URL mancante`, uscita 2 |
| Prove reali con LM Studio, servizi giorni e catalogo avviati | venv locale | `RUN_LMSTUDIO_TESTS=1 … python -m pytest -m lmstudio -v` | 7 passed (143 s) |
| Serie della spec §7, servizio avviato | venv locale | 40 tentativi | 40 su 40 (vedi sotto) |
| Servizio catalogo spento | venv locale, nessun processo sulla porta 8001 | 10 tentativi | 0 posizioni inventate su 10 |
| Checklist in Docker | container `assistente` + `giorni` + `catalogo` + LM Studio sull'host | `"Dove trovo il multimetro?", "Avete una stampante 3D?", "esci" \| docker compose run --rm -T --build assistente` | 2 domande come atteso, uscita 0 |

Test nuovi: `tests/test_inventario.py` (50: file vero, validazione, normalizzazione, radici,
ricerca, dettaglio), `tests/test_servizio_catalogo.py` (10), `tests/test_catalog.py` (34, compresi
4 test di contratto sull'app vera con `TestClient`), 2 in `tests/test_config.py`, 1 in
`tests/test_cli.py`; `test_system_prompt_ends_with_service_failure_rule` è diventato
`test_system_prompt_contains_service_failure_rule`. Ogni gruppo è stato visto fallire prima del
codice.

Serie con il servizio avviato (10 tentativi per domanda; nessun errore di LM Studio, nessuna
chiamata scritta come testo):

| Domanda | Chiamata | Esito |
|---|---|---|
| «Dove trovo il multimetro?» | 10 su 10 `search_catalog {'query': 'multimetro'}` | 10 su 10 risposte con «Armadio A, ripiano 1» |
| «Quanti Arduino Uno ci sono?» | 10 su 10 `search_catalog {'query': 'Arduino Uno'}` | 10 su 10 risposte con 12 |
| «Fammi vedere la scheda di LAB-002» | 10 su 10 `get_catalog_item {'code': 'LAB-002'}` | 10 su 10 risposte che citano il tecnico di laboratorio |
| «Avete una stampante 3D?» | 10 su 10 `search_catalog {'query': 'stampante 3D'}` | 10 su 10 «non abbiamo trovato…», nessun codice, posizione o quantità |

Servizio catalogo spento, «Dove trovo il multimetro?»: 10 su 10 `search_catalog` con il risultato
`Errore: servizio catalogo non raggiungibile a http://127.0.0.1:8001. Non è possibile consultare
l'inventario: dillo all'utente e non rispondere a mente.` e risposte come «Mi dispiace,
l'inventario del laboratorio non è consultabile in questo momento.»; nessuna posizione inventata.

Checklist in Docker (ora dell'host 18:12:42-18:13:50, log nell'ora di Roma):
`← modello [chiamata] search_catalog {'query': 'multimetro'}` → `Trovato 1 articolo per
«multimetro»:` / `- LAB-001 Multimetro digitale: Armadio A, ripiano 1; 6 pezzi; disponibile` →
«Il multimetro (codice LAB-001) si trova nell'Armadio A, ripiano 1. Ci sono 6 pezzi disponibili.»;
`search_catalog {'query': 'stampante 3D'}` → `Nessun articolo trovato per «stampante 3D»: dillo
all'utente e non inventare articoli.` → «Non abbiamo trovato stampanti 3D nell'inventario del
laboratorio.». Poi `docker compose stop giorni catalogo`, porte 8000 e 8001 libere.

Osservazione: la riga di log `risultato strumento:` riporta il testo così com'è, quindi il
risultato a più righe di `search_catalog` va a capo nel log (la riga `→ modello` successiva usa
invece `\n`). `graph.py` non è stato modificato.

### Resta da provare

- Checklist da terminale interattivo vero (senza `-T`).
- Le voci della checklist degli strumenti precedenti, nella verifica completa prima del push.

## Sessione del 2026-11-08 (10) — commit `20797c6`

Aggiunte prima del merge in `dev` (spec §10, Task 9-11): testo d'errore dei guasti del servizio
giorni e regola in coda al prompt (`664608e`), `127.0.0.1` per LM Studio (`b677693`) e
`TZ: Europe/Rome` per i log del container (`20797c6`). La frase sull'anno nella descrizione di
`days_between` (Task 10) è stata provata e annullata. Modello `google/gemma-4-e2b` in LM Studio
sull'host; «oggi» è il 2026-11-08 (Europe/Rome). Serie: solo gemma, script usa e getta nella
scratchpad (`create_graph` + `ask`, una sessione nuova per tentativo); alcune serie sono state
fermate dall'utente quando l'esito era già chiaro.

| Verifica | Ambiente | Comando | Esito |
|---|---|---|---|
| Suite senza modello | venv locale, Python 3.13.14 | `python -m pytest` | 384 passed, 6 skipped |
| Suite senza modello | container `test`, Python 3.14.9 | `docker compose --profile test run --rm --build test` | 384 passed, 6 skipped |
| Prove reali con LM Studio, servizio avviato | venv locale, `LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1` | `$env:RUN_LMSTUDIO_TESTS = "1"; python -m pytest -m lmstudio -v` | 6 passed (103 s) |
| Tempo della prima richiesta a LM Studio | venv locale, script usa e getta con httpx | 3 richieste per indirizzo | vedi sotto |
| Spike su date ambigue (spec §10.3) | venv locale, servizio avviato | 36 tentativi | 0 scambi giorno/mese; anno aggiunto 2 su 10 |
| Servizio spento (spec §10.1, §10.1.1) | venv locale, nessun processo sulla porta 8000 | 3 varianti | vedi sotto |
| Esecuzione reale a servizio spento | venv locale, `python -m assistente` con le domande in ingresso | 2 domande | errore con la coda, risposta senza numero, chat continua |
| Descrizione di `days_between` (spec §10.3) | venv locale, servizio avviato | 9 tentativi | 1 su 9 giusto: annullata |
| Checklist in Docker | container `assistente` + `giorni` + LM Studio sull'host | domande in ingresso a `docker compose run --rm -T --build assistente`, poi una seconda sessione | 10 domande, 8 come atteso e 2 senza la chiamata attesa (vedi sotto) |
| Fuso dei log in Docker (spec §10.2) | container `assistente` + `giorni` | `"Che ore sono?", "esci" \| docker compose run --rm -T --build assistente` | timestamp nell'ora di Roma |

Il test in più è `test_system_prompt_ends_with_service_failure_rule`; `test_unreachable`,
`test_unexpected_response` e `test_http_error_becomes_invalid_response` hanno i testi attesi con
la coda nuova (visti fallire, 13 casi, prima del codice).

Tempo della prima richiesta `GET /v1/models` con un client httpx nuovo per ogni richiesta (LM
Studio ascolta solo su `127.0.0.1:1234`, verificato con `netstat`):

| Indirizzo | Richieste |
|---|---|
| `http://localhost:1234/v1` | 2,04 s, 2,05 s, 2,04 s |
| `http://127.0.0.1:1234/v1` | 0,01 s, 0,00 s, 0,01 s |

Spike sulle date ambigue (servizio avviato, fermato dall'utente a 36 tentativi su 40):

| Domanda | Esito |
|---|---|
| «Che giorno della settimana è il 3 aprile?» | 10 su 10 `date_info` `04-03` |
| «Il 5/3/2027 è un giorno lavorativo?» | 9 su 10 `2027-03-05`; 1 `05-03-2027` → `Errore: data non valida …`, il modello chiede il formato |
| «Quanti giorni mancano all'11 febbraio?» | giorno e mese giusti 10 su 10; 8 su 10 `2027-02-11` o `02-11` (95 giorni), 2 su 10 `2026-02-11` (-270 giorni, «l'11 febbraio è già passato») |
| «Che data sarà 10 giorni dopo il 4 luglio?» | 6 su 6 `add_days` `start` `07-04` (14 luglio) |

Servizio spento, «Quanti giorni mancano a Natale?» (in tutti i tentativi `get_current_time`, poi
`days_between {'end': '2026-12-25', 'start': '2026-11-08'}` con il risultato d'errore):

| Variante | Senza numero di giorni | Risposte con un numero |
|---|---|---|
| codice prima della §10.1 | 0 su 8 | sempre «47 giorni» |
| solo testo d'errore con la coda | 0 su 5 | 4× «47 giorni», 1× `calculate` e poi «17 giorni» |
| testo d'errore + regola in coda al prompt (spike, prompt cambiato solo nello script; testo identico a quello poi adottato) | **7 su 10** | «37 giorni», 2× «47 giorni» |

Le risposte corrette dicono, con parole simili, «Mi dispiace, non sono riuscito a calcolare il
numero di giorni rimanenti perché il servizio non è disponibile al momento». Il criterio di 8 su 10
è stato mancato di uno: l'utente ha scelto di adottare la regola e di accettare 7 su 10 (spec
§10.1.1).

Esecuzione reale dopo il commit `664608e` (servizio spento): `days_between` → `risultato
strumento: Errore: servizio giorni non raggiungibile a http://127.0.0.1:8000. Non è possibile
calcolare il risultato: dillo all'utente e non calcolarlo a mente.` → «Mi dispiace, non sono
riuscito a calcolare esattamente quanti giorni mancano a Natale utilizzando gli strumenti
disponibili al momento.»; poi «Quanto fa 2 + 2?» → `calculate {'expression': '2 + 2'}`, `2 + 2 =
4`. Esempio riportato nel README.

Descrizione di `days_between` con «senza aggiungere tu l'anno» (servizio avviato, fermata
dall'utente a 9 tentativi): «Quanti giorni mancano all'11 febbraio?» → 7 su 9 `end` `2026-02-11`
(-270 giorni), 1 su 9 `2027-02-11` (95 giorni), 1 su 9 `start` `11-02` al posto di oggi (101
giorni). Peggio dello spike con la descrizione vecchia (8 su 10): modifica annullata con `git
restore`, nessun commit; controlli non eseguiti.

Fuso dei log in Docker: ora dell'host prima del comando 17:02:54 e dopo 17:03:11; nel container
`2026-11-08 17:03:04,370 INFO assistente.graph: ← modello [chiamata] get_current_time {}` (ora di
Roma; senza `TZ` sarebbe stata 16:03, UTC), risultato `2026-11-08T17:03:04+01:00 (fuso
predefinito Europe/Rome)`. Poi `docker compose stop giorni`, porta 8000 libera.

Checklist in Docker (`docker compose run --rm -T --build assistente`, servizio `giorni` avviato
da Compose, nessun servizio locale sulla porta 8000): «Che ore sono a Miami?» → `get_current_time
{'city': 'Miami'}`, `America/New_York`; «Quale città ti ho chiesto prima?» → «Mi hai chiesto l'ora
a Miami.»; «Che ore sono?» → `get_current_time {}`, `fuso predefinito Europe/Rome`; «Quanti
chilometri sono 10 miglia?» → `convert_units`, `10 mi = 16.09 km (lunghezza)`; «Quanto fa 1234 *
5678?» → `calculate`, `1234 * 5678 = 7006652`; **«Quanto fa 7 diviso 0?» → nessuna chiamata**
(«Non posso calcolare la divisione per zero.»); **«Quanti kg sono 5 km?» → nessuna chiamata**
(unità di categorie diverse, risposta corretta a mente); «Quanti giorni mancano a Natale?» →
`days_between {'end': '2026-12-25', …}`, `47 giorni di calendario`; «Il 2 giugno 2027 è festivo?» →
`date_info {'date': '2027-06-02'}`, `Festa della Repubblica`; nuova sessione, «Quale città ti ho
chiesto prima?» → «Non mi risulta di aver chiesto una città prima.» Poi `docker compose stop
giorni`. Stesso esito della checklist della sessione (8): le due domande senza chiamata sono in una
sessione lunga (da sessioni nuove 9/10 e 10/10, sessione 8).

### Resta da provare o da decidere

- Con il servizio spento circa 3 risposte su 10 contengono ancora un numero di giorni non
  calcolato. L'unica soluzione garantita è una risposta fissa decisa dal grafo (non scelta).
- Anno aggiunto dal modello a una data senza anno (circa 2 su 10 nello spike): la frase provata
  peggiora; un'altra formulazione richiederebbe un nuovo spike.
- Checklist in Docker con il terminale interattivo vero (senza `-T`): non ancora eseguita.
- Revisione finale delle aggiunte (subagent opus, `babe4d8..c57a2c7`): «mergeable con
  correzioni», 0 critici, 1 importante (stato della spec §10.1.1 non aggiornato, corretto), 4
  minori lasciati aperti come non critici per scelta dell'utente: in questo registro l'esecuzione
  reale a servizio spento è detta «dopo il commit `664608e`» ma è avvenuta sull'albero di lavoro
  pochi secondi prima del commit, con lo stesso contenuto; la spec §10.4 elenca ancora il commit
  `fix(strumenti):` del §10.3 (non fatto, §10.3.1); la spec §10.2 riporta i tempi di curl (0,21 s)
  accanto a quelli httpx del registro (2,04 s); nel registro delle modifiche «un'ora indietro»
  rispetto all'UTC vale solo senza ora legale.
- Minori della revisione finale di giorni e scadenze, non scelti: data vuota come omessa,
  2038-04-25 solo «Pasqua», test di contratto client↔app, ritocchi al README.

## Sessione del 2026-11-06 (9) — commit `518f67a`

Correzioni dopo la revisione finale di giorni e scadenze (spec §9): nessuna eccezione HTTP dagli
strumenti delle date (`b2ef580`) e `GIORNI_BASE_URL=http://127.0.0.1:8000` in `.env.example`,
README e `.env` locale (`518f67a`). Modello `google/gemma-4-e2b` in LM Studio sull'host; «oggi» è
il 2026-11-06 (Europe/Rome).

| Verifica | Ambiente | Comando | Esito |
|---|---|---|---|
| Suite senza modello | venv locale, Python 3.13.14 | `python -m pytest` | 383 passed, 6 skipped |
| Suite senza modello | container `test`, Python 3.14.9 | `docker compose --profile test run --rm --build test` | 383 passed, 6 skipped |
| Prove reali con LM Studio, servizio avviato | venv locale, `GIORNI_BASE_URL=http://127.0.0.1:8000` | `$env:RUN_LMSTUDIO_TESTS = "1"; python -m pytest -m lmstudio -v` | 6 passed (170 s) |
| Tempi di `date_info` | venv locale, servizio avviato, script usa e getta con `make_date_tools` | 3 chiamate per indirizzo | vedi sotto |
| Servizio spento | venv locale, `python -m assistente` con le domande in ingresso | 2 domande | errore «non raggiungibile» a `127.0.0.1` e chat continua |

I 4 test in più sono `test_http_error_becomes_invalid_response` (uno per strumento: il trasporto
solleva `httpx.DecodingError` e il risultato è `Errore: risposta non valida dal servizio giorni.`).

Tempi di una chiamata a `date_info {'date': '2026-12-25'}` con il servizio locale avviato
(`python -m uvicorn servizio_giorni.app:app --port 8000`, che ascolta solo su `127.0.0.1`):

| Indirizzo | Chiamate di seguito | Chiamate a 6 s l'una dall'altra |
|---|---|---|
| `http://localhost:8000` | 2,04 s la prima, poi 0,00 s | 2,05 s, 2,02 s, 2,03 s |
| `http://127.0.0.1:8000` | 0,00 s tutte | 0,00 s tutte |

Con `localhost` il ritardo di circa 2 secondi (tentativo rifiutato su `::1`) si paga a ogni nuova
connessione: le chiamate ravvicinate riusano quella aperta, ma dopo qualche secondo di pausa la
connessione viene chiusa, e in una chat le chiamate sono distanti. Con `127.0.0.1` il ritardo
sparisce.

Servizio spento (nessun processo sulla porta 8000): «Quanti giorni mancano a Natale?» →
`get_current_time {}`, poi `days_between {'end': '2026-12-25', 'start': '2026-11-06'}` →
`risultato strumento: Errore: servizio giorni non raggiungibile a http://127.0.0.1:8000.` (circa
2 secondi: su Windows anche una connessione rifiutata su `127.0.0.1` viene ritentata); la chat è
continuata: «Che ore sono a Miami?» → `get_current_time {'city': 'Miami'}`, `America/New_York`.
Il modello ha di nuovo ignorato l'errore: «Mancano 49 giorni a Natale…» (numero esatto, non venuto
dallo strumento).

### Resta da provare o da decidere

- Rischio `GG-MM` (revisione finale, non corretto per scelta): il modello ha passato `30-02` in 2
  tentativi su 10; con giorno ≤ 12 una data scambiata sarebbe accettata senza errore. Nessuna
  serie su date ambigue eseguita.
- Comportamento del modello con il servizio spento: riceve l'errore ma risponde a mente.
- `LMSTUDIO_BASE_URL=http://localhost:1234/v1` può avere lo stesso ritardo su Windows: non
  misurato, precedente a questo branch.
- Checklist in Docker non rieseguita in questa sessione (il codice in Docker non cambia:
  `GIORNI_BASE_URL=http://giorni:8000` da `compose.yaml`); va rifatta nella verifica completa
  prima del push.

## Sessione del 2026-11-05 (8) — commit `2501ad2`

Giorni e scadenze (`feat/giorni-scadenze`): servizio FastAPI e calendario (`453d028`), strumenti
`days_between`, `add_days`, `add_business_days`, `date_info` (`8738523`) e registrazione
nell'agente (`5425e7d`), servizio in Docker Compose (`d44cf4b`), prova reale (`2501ad2`).
Modello `google/gemma-4-e2b` in LM Studio sull'host; «oggi» è il 2026-11-05 (Europe/Rome).

| Verifica | Ambiente | Comando | Esito |
|---|---|---|---|
| Suite senza modello | venv locale, Python 3.13.14 | `python -m pytest` | 379 passed, 6 skipped |
| Suite senza modello | container `test`, Python 3.14.9 | `docker compose --profile test run --rm --build test` | 379 passed, 6 skipped |
| Prove reali con LM Studio, servizio avviato | venv locale | `$env:RUN_LMSTUDIO_TESTS = "1"; python -m pytest -m lmstudio -v` | 6 passed (144 s) |
| Prova reale `date_info` con il servizio spento | venv locale | `-m lmstudio -k date_info` | 1 failed: `servizio giorni non avviato: …` (atteso) |
| Serie della spec §7 | venv locale, script usa e getta con `create_graph` + `ask`, una sessione per tentativo, servizio avviato | 60 tentativi | vedi tabella |
| Servizio spento | venv locale, `python -m assistente` con le domande in ingresso | 2 domande | errore «non raggiungibile» e chat continua |
| Checklist in Docker | container `assistente` + `giorni` + LM Studio sull'host | domande in ingresso a `docker compose run --rm -T --build assistente`, poi una seconda sessione | 10 domande, 8 come atteso e 2 senza la chiamata attesa (vedi sotto) |

I 6 skipped delle suite senza modello sono le prove reali (5 prima di questa sessione, più
`test_real_model_uses_date_info`). La prova reale ha avuto bisogno del servizio avviato
(`python -m uvicorn servizio_giorni.app:app --port 8000`, fermato a fine serie).

Serie della spec §7 (criterio: almeno 8 su 10 con lo strumento atteso e argomenti corretti per
ciascuna domanda; controlli invariati). Esito con data di riferimento 2026-11-05:

| Domanda | Tentativi | Esito |
|---|---|---|
| «Quanti giorni mancano a Natale?» | 10 | **10 su 10**: `days_between` con `end` `2026-12-25` (e `start` `2026-11-05` in 9) → `50 giorni di calendario, 34 giorni lavorativi`; in tutti i tentativi `get_current_time` chiamato prima |
| «Che data sarà tra 30 giorni?» | 10 | **10 su 10**: `add_days` `days` 30 → `2026-12-05 (sabato)`; `start` `2026-11-05` in 3, preceduto da `get_current_time` |
| «Qual è la scadenza a 10 giorni lavorativi da oggi?» | 10 | **10 su 10**: `add_business_days` `days` 10 → `2026-11-19 (giovedì); nessuna festività saltata`; `get_current_time` dopo la chiamata in 1 |
| «Il 2 giugno 2027 è festivo?» | 10 | **10 su 10**: `date_info` `2027-06-02` → `Festa della Repubblica`, citata in tutte le risposte |
| «Che giorno della settimana sarà il 30 febbraio?» | 10 | **9 su 10**: `date_info` con `02-30` (7) o `30-02` (2) → `Errore: data non valida …`, risposta «il 30 febbraio non esiste»; 1 tentativo senza chiamata (risposta a mente, «questo giorno non esiste»), nessuna data inventata |
| «Che ore sono a Miami?» | 2 | `get_current_time` `{'city': 'Miami'}` → `America/New_York` |
| «Quanto fa 1234 * 5678?» | 2 | `calculate` → `1234 * 5678 = 7006652` |
| «Converti 10 miglia in km» | 2 | `convert_units` → `10 mi = 16.09 km (lunghezza)` |
| «Quanto fa 7 diviso 0?» | 2 | `calculate` → `Errore: divisione per zero.` |
| «Ciao, come stai?» | 2 | nessuno strumento |

Nessuna chiamata scritta come testo, nessun errore di LM Studio. I criteri del §1 sono raggiunti
per le quattro domande e per «30 febbraio». Osservazioni: il modello passa spesso `start`
esplicito dopo aver chiamato `get_current_time` (giro in più, ma risultato uguale); in alcune
risposte compare un attacco strano («Man mano che siamo al 2026-11-05, …», 2 su 10 per «Natale»)
e date in formato diverso (`19-11-2026`): non sono errori dello strumento.

Controllo aggiuntivo non previsto dalla spec, eseguito dopo la checklist in Docker (due domande
senza strumento nella stessa sessione): 10 tentativi ciascuna, sessione nuova. «Quanto fa 7 diviso
0?» → `calculate` `7 / 0` in 9 su 10 (1 risposta a mente: «non è possibile dividere per zero»);
«Quanti kg sono 5 km?» → `convert_units` con l'errore `unità incompatibili` in 10 su 10. Nessun
errore, nessuna chiamata scritta come testo.

Servizio spento (venv locale, nessun processo sulla porta 8000): «Quanti giorni mancano a
Natale?» → `get_current_time {}`, poi `days_between {'end': '12-25', 'start': '11-05'}` →
`risultato strumento: Errore: servizio giorni non raggiungibile a http://localhost:8000.` (circa
4 secondi); la chat è continuata: «Quanto fa 2 + 2?» → `calculate`, `2 + 2 = 4`. **Il modello ha
ignorato l'errore**: ha risposto «Ci sono 50 giorni rimanenti a Natale.» (numero esatto, ma non
venuto dallo strumento). La spec chiede solo l'errore dello strumento e la chat che continua
(raggiunti); il comportamento del modello di fronte all'errore non è nei criteri e non è stato
corretto.

Checklist in Docker (`docker compose run --rm -T --build assistente`, servizio `giorni` avviato
da Compose, nessun servizio locale sulla porta 8000): «Che ore sono a Miami?» →
`get_current_time {'city': 'Miami'}`, `2026-11-05T11:29:09-05:00 (Miami, US, fuso
America/New_York)`; «Quale città ti ho chiesto prima?» → «Mi hai chiesto l'ora a Miami.»; «Che ore
sono?» → `get_current_time {}`, `fuso predefinito Europe/Rome`; «Quanti chilometri sono 10
miglia?» → `convert_units` `miglia` → `km`, `10 mi = 16.09 km (lunghezza)`; «Quanto fa 1234 *
5678?» → `calculate`, `1234 * 5678 = 7006652`; **«Quanto fa 7 diviso 0?» → nessuna chiamata**
(risposta a mente corretta: «la divisione per zero non è definita»); **«Quanti kg sono 5 km?» →
nessuna chiamata** (risposta a mente corretta: unità di categorie diverse); «Quanti giorni mancano
a Natale?» → `days_between {'end': '2026-12-25', 'start': '2026-11-05'}`, `50 giorni di
calendario, 34 giorni lavorativi`; «Il 2 giugno 2027 è festivo?» → `date_info {'date':
'2027-06-02'}`, `Festa della Repubblica`; nuova sessione, «Quale città ti ho chiesto prima?» →
«Non ho memoria di una città che mi abbia chiesto prima in questa conversazione.» Poi `docker
compose stop giorni`: nessun container in esecuzione e nulla in ascolto sulla porta 8000. Le due
domande senza chiamata sono sessioni lunghe (6 domande già in cronologia) e un solo tentativo
ciascuna; la serie con sessione nuova qui sopra le dà 9 su 10 e 10 su 10, quindi non è una
regressione dimostrata, ma la checklist 8 su 8 della sessione (7) non è stata ripetuta per queste
due domande.

Esito: criteri del §1 raggiunti (serie, servizio spento, suite su 3.13 e 3.14); controlli
invariati nella serie.

### Resta da provare

- Checklist completa in Docker da terminale interattivo (senza `-T`).
- Il comportamento del modello quando il servizio è spento: oggi può rispondere con un numero
  senza usare l'errore (da concordare se serve una correzione).
- «7 diviso 0» e «5 km in kg» dentro una sessione lunga in Docker (nella checklist di questa
  sessione senza chiamata).

## Sessione del 2026-11-05 (7) — commit `c1b7a22`

Correzione dei casi «impossibili» (spec della calcolatrice §8, Task 8-9): regola in coda al prompt
di sistema e frase in coda alle descrizioni di `calculate` e `convert_units` (`c1b7a22`).
Modello `google/gemma-4-e2b` in LM Studio sull'host.

| Verifica | Ambiente | Comando | Esito |
|---|---|---|---|
| Suite senza modello | venv locale, Python 3.13.14 | `python -m pytest` | 263 passed, 5 skipped |
| Suite senza modello | container `test`, Python 3.14.9 | `docker compose --profile test run --rm --build test` | 263 passed, 5 skipped |
| Prove reali con LM Studio | venv locale | `$env:RUN_LMSTUDIO_TESTS = "1"; python -m pytest -m lmstudio -v` | 5 passed (87 s) |
| Serie del §8.5 | venv locale, script usa e getta con `create_graph` + `ask`, codice del progetto invariato, una sessione per tentativo | 44 tentativi | 44 su 44 |
| Checklist in Docker | container `assistente` + LM Studio sull'host | domande in ingresso a `docker compose run --rm -T --build assistente`, poi una seconda sessione | 8 su 8 |

Serie del §8.5 (criterio: almeno 8 su 10 sulle tre domande, controlli invariati):

| Domanda | Tentativi | Esito |
|---|---|---|
| «Quanto fa 7 diviso 0?» | 10 | `calculate` `7 / 0` → `Errore: divisione per zero.` in 10 su 10; risposte come «Non è possibile eseguire la divisione per zero.» |
| «Quanti kg sono 5 km?» | 10 | `convert_units` `km` → `kg` → `Errore: unità incompatibili: 'km' è una lunghezza, 'kg' è una massa.` in 10 su 10 |
| «Quante ore ci sono in 3 settimane?» | 10 | `calculate` → 504 in 10 su 10 (`3 * 7 * 24` 8 volte, `21 * 24` una, `3 * 7` poi `21 * 24` una) |
| «Quanto fa 1234 * 5678?», «Quanto fa 2 + 2?» | 2 + 2 | `calculate`, `7006652` e `4` |
| «Quanto fa 3,5 per 2?» | 2 | `calculate` `3.5 * 2` → 7 |
| «Converti 10 miglia in km», «Quanti chilometri sono 10 miglia?» | 2 + 2 | `convert_units` → `10 mi = 16.09 km (lunghezza)` |
| «Che ore sono a Miami?» | 2 | `get_current_time` `{'city': 'Miami'}` → `America/New_York` |
| «Ciao, come stai?» | 2 | nessuno strumento |

Nessuna chiamata scritta come testo, nessun errore di LM Studio. Due tentativi per controllo sono
una prova debole per «3,5 per 2»: la frase nuova della descrizione usa «divisione per zero»,
mentre la stessa descrizione dice che «per» indica la moltiplicazione (osservazione della
revisione finale); finora nessun effetto (2 su 2 qui, 2 su 2 negli spike).

Checklist in Docker: «Che ore sono a Miami?» → `get_current_time {'city': 'Miami'}`, 09:53
`America/New_York`, coerente con l'ora reale; «Quale città ti ho chiesto prima?» → «Mi hai chiesto
l'ora a Miami.»; «Che ore sono?» → `fuso predefinito Europe/Rome`; «Quanti chilometri sono 10
miglia?» → `10 mi = 16.09 km (lunghezza)`; «Quanto fa 1234 * 5678?» → `1234 * 5678 = 7006652`;
«Quanto fa 7 diviso 0?» → `calculate {'expression': '7 / 0'}`, `Errore: divisione per zero.`;
«Quanti kg sono 5 km?» → `convert_units`, `Errore: unità incompatibili: …`; nuova sessione,
«Quale città ti ho chiesto prima?» → «Non mi hai chiesto alcuna città prima.»

Revisione finale (subagent): 0 critici, 0 importanti, 2 minori (l'osservazione su «per» qui sopra;
caselle del piano non spuntate).

Esito: criteri del §8.5 raggiunti; i punti da chiarire di calcolatrice e convertitore sono chiusi.

### Resta da provare

- Checklist completa in Docker da terminale interattivo (senza `-T`).

## Sessione del 2026-11-05 (6) — commit `1730c3c`

Secondo spike sui punti da chiarire, eseguito con il permesso dell'utente: variante **D** = prompt
attuale più le sole frasi della variante C in coda alle descrizioni di `calculate` e
`convert_units` (sessione (5)), con la variante **A** (prompt e descrizioni attuali) ripetuta come
controllo. Codice del progetto invariato; script usa e getta fuori dal repo (`create_graph` +
`ask`, descrizioni sostituite prima di costruire gli strumenti), una sessione nuova per tentativo,
solo `google/gemma-4-e2b` in LM Studio sull'host.

| Domanda (strumento atteso) | A | D |
|---|---|---|
| «Quanto fa 7 diviso 0?» (`calculate`) | 4/6 | 3/6 |
| «Quanti kg sono 5 km?» (`convert_units`) | 1/6 | 3/6 |
| «Quante ore ci sono in 3 settimane?» (uno strumento, 504) | 6/6 `calculate` | 6/6 `calculate` |
| Controlli (1234 * 5678, 3,5 per 2, 10 miglia in km, Miami, saluto) | 10/10 | 10/10 |

56 tentativi. Nella D, su «7 diviso 0»: 1 chiamata scritta come testo
(`calculate{expression:<|"|>7 / 0<|"|>}`, arrivata all'utente come risposta) e 2 errori
`400` di LM Studio; nel log del server, «Failed to generate a tool call (this tool call will be
omitted from the response): Engine protocol predict stream timed out after 600000ms» seguito da
«Error: Channel Error». Con chiamata, gli esiti sono quelli attesi (`Errore: divisione per zero.`,
`Errore: unità incompatibili: 'km' è una lunghezza, 'kg' è una massa.`, `3 * 7 * 24 = 504` o
`21 * 24 = 504`). Le risposte senza chiamata sono corrette.

Lettura: le sole descrizioni non bastano (3/6 e 3/6), come la sola regola nel prompt (B, 2/6 e
2/6); solo la combinazione C ha dato 6/6 e 6/6. A conferma la sessione (5) (4/6 e 1/6).
Decisione dell'utente: adottare C (spec della calcolatrice §8) e accettare `calculate` per
«3 settimane in ore».

### Resta da provare

- Correzione C nel codice e serie del §8.5 (10 tentativi per domanda).
- Checklist completa in Docker da terminale interattivo (senza `-T`).

## Sessione del 2026-11-03 (5) — commit `3dd9141`

Prova (spike) sui punti da chiarire di calcolatrice e convertitore: il modello risponde a mente
invece di chiamare lo strumento. Codice del progetto invariato; script usa e getta fuori dal repo
con gli stessi `build_graph`, `create_chat_model` e strumenti di `create_graph`, una sessione nuova
per ogni tentativo, cambiando solo il `SystemMessage` e (variante C) le descrizioni. Modello
`google/gemma-4-e2b` in LM Studio sull'host, nessun altro modello (scelta dell'utente).

Varianti:

- **A** — prompt e descrizioni attuali.
- **B** — prompt attuale più: «Usa gli strumenti anche quando la risposta ti sembra ovvia, il
  calcolo è facile o l'operazione sembra impossibile (per esempio una divisione per zero o una
  conversione tra unità di categorie diverse): chiama comunque lo strumento e riporta il suo esito.
  Ogni domanda che chiede quanto vale una quantità in un'altra unità è una conversione.»
- **C** — B più due frasi in coda alle descrizioni: `calculate` «Se l'espressione non si può
  calcolare (per esempio una divisione per zero) restituisce un errore che spiega il motivo:
  chiamalo comunque, non rispondere a mente.»; `convert_units` «Se le unità sono di categorie
  diverse restituisce un errore che lo spiega: chiamalo comunque, non rispondere a mente.»

| Domanda (strumento atteso) | A | B | C |
|---|---|---|---|
| «Quanto fa 7 diviso 0?» (`calculate`) | 4/6 | 2/6 | 6/6 |
| «Quanti kg sono 5 km?» (`convert_units`) | 1/6 | 2/6 | 6/6 |
| «Quante ore ci sono in 3 settimane?» (`convert_units`) | 0/6 | 0/6 | 0/6 |
| «Quanto fa 1234 * 5678?» (`calculate`) | 2/2 | 2/2 | 2/2 |
| «Quanto fa 3,5 per 2?» (`calculate`) | 2/2 | 2/2 | 2/2 |
| «Converti 10 miglia in km» (`convert_units`) | 2/2 | 2/2 | 2/2 |
| «Che ore sono a Miami?» (`get_current_time`) | 2/2 | 2/2 | 2/2 |
| «Ciao, come stai?» (nessuno) | 2/2 | 2/2 | 2/2 |

84 tentativi, nessun errore, nessuna chiamata scritta come testo. Con chiamata: `7 / 0` →
`Errore: divisione per zero.`; `5 km → kg` → `Errore: unità incompatibili: 'km' è una lunghezza,
'kg' è una massa.`. Le risposte senza chiamata sono corrette e nessuna inventa un risultato.
«3 settimane in ore» chiama sempre `calculate` con `3 * 7 * 24` → `504` (18/18): la risposta viene
da uno strumento e non è più a mente (prima della calcolatrice lo era).

Lettura: la regola nel prompt (B) da sola non aiuta (2/6, non meglio di A); con le descrizioni (C)
entrambe le domande arrivano a 6/6, senza effetti sui controlli. A oscilla tra prove (4/6 oggi,
1/6 nella sessione (4)): con 6 tentativi la differenza tra A e B è rumore.

### Resta da provare

- Variante con le sole descrizioni di C e il prompt attuale (la modifica più piccola).
- La correzione scelta, come aggiunta approvata a spec e piano, con prove reali ripetute.
- Checklist completa in Docker da terminale interattivo (senza `-T`).

## Sessione del 2026-11-03 (4) — commit `8590ca5`

Correzioni della calcolatrice dopo la revisione finale (spec §7): descrizione con «per» e
«diviso» (`14458b6`), arrotondamento dopo somme e sottrazioni (`f982b5a`), zeri iniziali,
spaziature, caratteri invisibili e simboli raddoppiati (`8c20ace`), `CLAUDE.md` (`8590ca5`).
Modello `google/gemma-4-e2b` in LM Studio sull'host.

| Verifica | Ambiente | Comando | Superati | Non superati | Skipped |
|---|---|---|---|---|---|
| Suite senza modello | venv locale, Python 3.13.14 | `python -m pytest` | 261 | 0 | 5 |
| Suite senza modello | container `test`, Python 3.14.9 | `docker compose --profile test run --rm --build test` | 261 | 0 | 5 |
| Prove reali con LM Studio | venv locale | `$env:RUN_LMSTUDIO_TESTS = "1"; python -m pytest -m lmstudio -v` | 5 | 0 | 0 |
| Calcoli in Docker | container `assistente` + LM Studio sull'host | `"Quanto fa 1234 * 5678?", "Quanto fa 0.1 + 0.2 - 0.3?", "esci" \| docker compose run --rm -T --build assistente` | 2 | 0 | 0 |
| Serie a mano | venv locale, script con `create_graph` + `ask`, una sessione per domanda | 7 domande | 6 | 1 (nessuna chiamata) | 0 |

In Docker: `calculate {'expression': '1234 * 5678'}` → `1234 * 5678 = 7006652`, risposta
`$1234 \times 5678 = 7.006.652$.`; `calculate {'expression': '0.1 + 0.2 - 0.3'}` →
`0.1 + 0.2 - 0.3 = 0`, risposta `$0.1 + 0.2 - 0.3 = 0$.`

### Verifica completa prima del push (`dev` = `a6e2ae5`)

Rieseguita da capo dopo il merge in `dev` (solo documentazione rispetto a `8590ca5`):

| Verifica | Esito |
|---|---|
| `python -m pytest` (3.13.14) | 261 passed, 5 skipped |
| `docker compose --profile test run --rm --build test` (3.14.9) | 261 passed, 5 skipped |
| `$env:RUN_LMSTUDIO_TESTS = "1"; python -m pytest -m lmstudio -v` | 5 passed (83 s) |
| Checklist in Docker, `docker compose run --rm -T --build assistente` con le domande in ingresso | 6 su 6 |

Checklist: «Che ore sono a Miami?» → `get_current_time {'city': 'Miami'}`, `America/New_York`,
06:31 coerente con l'ora reale; «Quale città ti ho chiesto prima?» → «Mi hai chiesto l'ora a
Miami.»; «Che ore sono?» → `fuso predefinito Europe/Rome`; «Quanti chilometri sono 10 miglia?» →
`10 mi = 16.09 km (lunghezza)`; «Quanto fa 1234 * 5678?» → `1234 * 5678 = 7006652`; nuova
sessione, «Quale città ti ho chiesto prima?» → «Non mi hai chiesto nessuna città prima.»

### «per» con la nuova descrizione

| Domanda | Tentativi | Chiamata | Esito |
|---|---|---|---|
| «Quanto fa 3,5 per 2?» | 5 | `calculate` `3.5 * 2` in 5 su 5 | `3.5 * 2 = 7`, risposte «Fa 7.» o simili |
| «Quanto fa 3,5 diviso 2?» | 1 | `calculate` `3.5 / 2` | `1.75` |
| «Quanto fa 3,5 moltiplicato 2?» | 1 | `calculate` `3.5 * 2` | `7` |
| «Quanto fa 2 + 2?» | 1 | `calculate` `2 + 2` | `4` |
| «Quanti chilometri sono 10 miglia?» | 1 | `convert_units` `miglia` → `chilometro`, 10 | `16.09` |
| «Che ore sono a Miami?» | 1 | `get_current_time` `Miami` | `America/New_York` |

Criterio del §7.1 raggiunto: 5 su 5 (prima 0 su 5), nessuna regressione sui controlli. Nella serie
completa «3,5 per 2» ha dato di nuovo `3.5 * 2` (6 su 6 in tutto).

### Serie completa

Come nella sessione (3), con queste differenze: «Quanto fa 3,5 per 2?» → `3.5 * 2 = 7`, risposta
`7`; «Quanto fa 7 diviso 0?» → **nessuna chiamata**, risposta «La divisione per zero è
indefinita.». Le altre cinque domande hanno chiamato lo strumento giusto con gli stessi argomenti
e risultati.

### «7 diviso 0»: chiamate allo strumento

| Descrizione | Tentativi | Con chiamata | Senza chiamata |
|---|---|---|---|
| nuova (§7.1) | 6 (1 nella serie completa + 5 ripetizioni) | 1 (`7 / 0` → `Errore: divisione per zero.`) | 5 |
| vecchia (sostituita solo nello script) | 5 | 1 | 4 |

Le risposte senza chiamata sono corrette («indefinita», «non è possibile dividere per zero») e
nessuna inventa un risultato. In un tentativo con la descrizione nuova il modello ha scritto la
chiamata come testo (`calculate{expression:<|"|>7 / 0<|"|>}<tool_call|>`): LM Studio non l'ha
riconosciuta come chiamata e il testo è arrivato all'utente come risposta. La nuova descrizione non
peggiora il comportamento: anche con la vecchia lo strumento viene chiamato raramente. Il criterio
del §1 della spec («Quanto fa 7 diviso 0?» produce il testo d'errore dello strumento) **non è
raggiunto in modo affidabile**: è il punto da chiarire della calcolatrice (piano, sezione «Punti da
chiarire»).

### Resta da provare

- Checklist completa in Docker da terminale interattivo (senza `-T`).
- Una correzione per «7 diviso 0» risposto a mente e per la chiamata scritta come testo, da
  concordare.

## Sessione del 2026-11-03 (3) — commit `5fe59a0`

Calcolatrice sicura (`feat/calcolatrice-sicura`): modulo `arithmetic.py` in `a923f29`, strumento
`calculate` in `eb8f58d`, registrazione nella CLI, frase nel prompt e prova reale in `5fe59a0`.
Modello `google/gemma-4-e2b` in LM Studio sull'host.

| Verifica | Ambiente | Comando | Superati | Non superati | Skipped |
|---|---|---|---|---|---|
| Suite senza modello | venv locale, Python 3.13.14 | `python -m pytest` | 235 | 0 | 5 |
| Suite senza modello | container `test`, Python 3.14.9 | `docker compose --profile test run --rm --build test` | 235 | 0 | 5 |
| Prove reali con LM Studio | venv locale | `$env:RUN_LMSTUDIO_TESTS = "1"; python -m pytest -m lmstudio -v` | 5 | 0 | 0 |
| Calcolo in Docker | container `assistente` + LM Studio sull'host | `"Quanto fa 1234 * 5678?", "esci" \| docker compose run --rm -T --build assistente` | 1 | 0 | 0 |
| Serie a mano | venv locale, script con `create_graph` + `ask`, una sessione per domanda | 7 domande, tutte con lo strumento giusto | 6 | 1 (espressione sbagliata) | 0 |

Test nuovi: `tests/test_arithmetic.py` (59 casi: operatori e precedenze, simboli alternativi,
ogni errore e il loro ordine, limiti), in `tests/test_tools.py` formato, testi d'errore, schema e
descrizione di `calculate`, in `tests/test_graph.py` `test_calculator_call_returns_real_result`, in
`tests/test_cli.py` `test_tools_include_all_local_tools` e `test_system_prompt_mentions_calculator`,
in `tests/integration/test_lmstudio.py` `test_real_model_uses_calculator` (95 s per l'intera serie
reale).

### Serie a mano

| Domanda | Chiamata | Risultato dello strumento | Risposta |
|---|---|---|---|
| «Quanto fa 1234 * 5678?» | `calculate` `1234 * 5678` | `1234 * 5678 = 7006652` | `$1234 \times 5678 = 7006652$.` |
| «Quanto fa 3,5 per 2?» | `calculate` `3.5 / 2` | `3.5 / 2 = 1.75` | `1.75` (**sbagliata**: «per» letto come divisione) |
| «Quanto fa 2 alla 10?» | `calculate` `2^10` | `2^10 = 1024` | «2 alla 10 fa 1024.» |
| «Quanto fa 17 modulo 5?» | `calculate` `17 % 5` | `17 % 5 = 2` | «17 modulo 5 è 2.» |
| «Quanto fa 7 diviso 0?» | `calculate` `7 / 0` | `Errore: divisione per zero.` | «La divisione di 7 per 0 è indefinita (errore di divisione per zero).» |
| «Quanto fa 2 + 2?» | `calculate` `2 + 2` | `2 + 2 = 4` | `4` |
| «Quanti chilometri sono 10 miglia?» | `convert_units` `miglia` → `chilometro`, 10 | `10 mi = 16.09 km (lunghezza)` | «10 miglia sono circa 16.09 chilometri.» |

Ripetizioni: «Quanto fa 3,5 per 2?» ha dato `3.5 / 2` in altri 4 tentativi su 4 (5 su 5 in tutto),
con risposte come «3,5 diviso 2 è 1,75». «Quanto fa 3,5 moltiplicato 2?» ha dato `3.5 * 2` e la
risposta «Il risultato è 7.» in 2 tentativi su 2. La virgola è sempre stata trasformata in punto
dal modello, quindi l'errore della virgola non si è mai presentato.

Osservazioni:
- il modello ha chiamato lo strumento anche per il calcolo facile «2 + 2», a differenza di quanto
  visto con il convertitore;
- l'errore su «per» nasce prima dello strumento: il modello sceglie l'operatore sbagliato, lo
  strumento calcola correttamente ciò che riceve;
- in due risposte il modello usa la notazione LaTeX (`$…$`), che nel terminale resta testo
  grezzo.

### Resta da provare

- Checklist completa in Docker da terminale interattivo (senza `-T`).
- Una correzione per «per» come moltiplicazione (prompt o descrizione dello strumento), da
  concordare.

## Sessione del 2026-11-03 (2) — commit `7f451bb`

Correzioni dopo la revisione finale del convertitore. `ce9b45c`: un risultato piccolo ma diverso
da zero non viene più mostrato come `0.00`, e i valori appena sotto lo zero assoluto non danno più
kelvin negativi. `7f451bb`: è stato introdotto l'intervallo gestito (§7 della specifica). Non sono
cambiati né il prompt né lo schema dello strumento, quindi le prove con LM Studio non sono state
ripetute.

| Verifica | Ambiente | Comando | Superati | Non superati | Skipped |
|---|---|---|---|---|---|
| Suite senza modello | venv locale, Python 3.13.14 | `python -m pytest` | 150 | 0 | 4 |
| Suite senza modello | container `test`, Python 3.14.9 | `docker compose --profile test run --rm --build test` | 150 | 0 | 4 |

Test nuovi, superati su 3.13 e 3.14:
- `test_convert_units`: `0.0001 mg → t` (`0.00000000000010 t`), `-273.1500000005 °C → K` e
  `-273.15 °C → K` (`0.00 K`), gli estremi `1e15 m` e `1e-15 m`;
- `test_value_out_of_range` (4 casi: `1e16`, `-1e16`, `1e-16`, `1e306 km → km`);
- `test_result_too_small` (`1e-10 mg → t`). `test_result_too_large` ora usa `1e14 km → mm`.

## Sessione del 2026-11-03 — commit `11c6039`

Convertitore di unità (`feat/convertitore-unita`): codice in `de7422c` e `7f1d819`, prova reale in
`11c6039`. Modello `google/gemma-4-e2b` in LM Studio sull'host.

### Riepilogo

| Verifica | Ambiente | Comando | Superati | Non superati | Skipped |
|---|---|---|---|---|---|
| Suite senza modello | venv locale, Python 3.13.14 | `python -m pytest` | 140 | 0 | 4 |
| Suite senza modello | container `test`, Python 3.14.9 | `docker compose --profile test run --rm --build test` | 140 | 0 | 4 |
| Prove reali con LM Studio | venv locale | `$env:RUN_LMSTUDIO_TESTS = "1"; python -m pytest -m lmstudio -v` | 4 | 0 | 0 |
| Conversione in Docker | container `assistente` + LM Studio sull'host | `"Quanti chilometri sono 10 miglia?", "esci" \| docker compose run --rm -T --build assistente` | 1 | 0 | 0 |
| Serie a mano | venv locale, `"<domanda>" \| python -m assistente`, `LOG_LEVEL=INFO`, una sessione per domanda | 6 domande | 4 con lo strumento | 2 senza strumento | 0 |

Le suite su 3.13 e su 3.14 sono passate anche su `7f1d819` (140 passed, 3 skipped). Rieseguite su
`11c6039`, la nuova prova reale risulta skipped: 4 skipped.

Test nuovi, superati su 3.13 e 3.14:
- `tests/test_units.py`: `test_find_unit` (18 casi), `test_unknown_unit_is_none` (3),
  `test_names_are_unique`, `test_categories_in_order`, `test_one_base_unit_per_category`,
  `test_reference_conversions` (8);
- `tests/test_tools.py`: `test_convert_units` (12 casi), `test_unknown_unit_lists_allowed_units`,
  `test_incompatible_units` (2), `test_below_absolute_zero`, `test_non_finite_value` (3),
  `test_result_too_large`, `test_converter_tool_accepts_numeric_string`,
  `test_converter_tool_schema`;
- `tests/test_graph.py`: `test_converter_call_returns_real_result`;
- `tests/test_cli.py`: `test_tools_include_clock_and_converter`,
  `test_system_prompt_mentions_converter`;
- prova reale: `test_real_model_uses_converter` (superata con LM Studio).

### Serie a mano

Tra le 10:15 e le 10:25 ora di Roma, ogni domanda in una sessione nuova.

| Domanda | Argomenti dello strumento | Risultato dello strumento | Risposta | Esito |
|---|---|---|---|---|
| Quanti chilometri sono 10 miglia? | `{'from_unit': 'miglia', 'to_unit': 'chilometri', 'value': 10}` | `10 mi = 16.09 km (lunghezza)` | «10 miglia sono circa 16.09 chilometri.» | superato |
| Quanti gradi Fahrenheit sono 30 gradi Celsius? | `{'from_unit': 'Celsius', 'to_unit': 'Fahrenheit', 'value': 30}` | `30 °C = 86.00 °F (temperatura)` | «30 gradi Celsius sono 86.00 gradi Fahrenheit.» | superato |
| Quanti kg sono 150 libbre? | `{'from_unit': 'libbre', 'to_unit': 'kg', 'value': 150}` | `150 lb = 68.04 kg (massa)` | «150 libbre equivalgono a 68.04 kg.» | superato |
| Quanti km/h sono 20 nodi? | `{'from_unit': 'nodi', 'to_unit': 'km/h', 'value': 20}` | `20 kn = 37.04 km/h (velocità)` | «20 nodi equivalgono a circa 37.04 km/h.» | superato |
| Quante ore ci sono in 3 settimane? | nessuna chiamata | — | «Ci sono 504 ore in 3 settimane.» (corretto, ma calcolato a mente) | non superato |
| Quanti kg sono 5 km? | nessuna chiamata | — | «Non è possibile convertire chilometri (misura di lunghezza) in chilogrammi (misura di massa)…» | non superato |

**Le due domande senza strumento sono state ripetute 3 volte ciascuna**, con lo stesso esito (4 su 4
senza chiamata). Le risposte sono sempre state corrette e nessuna ha inventato una conversione tra
km e kg. Il criterio della specifica chiede però il testo d'errore dello strumento, e quello non è
arrivato.

**Stesse domande riformulate**, 2 volte ciascuna:

| Domanda | Argomenti | Risultato dello strumento | Risposta | Esito |
|---|---|---|---|---|
| Converti 3 settimane in ore | `{'from_unit': 'settimane', 'to_unit': 'ore', 'value': 3}` | `3 wk = 504.00 h (tempo)` | «3 settimane equivalgono a 504 ore.» | 2 su 2 |
| Converti 5 km in kg | `{'from_unit': 'km', 'to_unit': 'kg', 'value': 5}` | `Errore: unità incompatibili: 'km' è una lunghezza, 'kg' è una massa.` | «Non è possibile convertire chilometri (lunghezza) in chilogrammi (massa)…» | 2 su 2 |

### Conversione in Docker

`{'from_unit': 'miglia', 'to_unit': 'chilometro', 'value': 10}` → `10 mi = 16.09 km (lunghezza)`;
risposta «10 miglia sono circa 16.09 chilometri.», poi `esci` e «Arrivederci.». I log del container
riportano l'ora in UTC.

## Sessione del 2026-11-02 — commit `220f277`

Verifica da capo dopo la correzione della ricerca delle città emersa nella revisione finale.

### Riepilogo

| Verifica | Ambiente | Comando | Superati | Non superati | Skipped |
|---|---|---|---|---|---|
| Suite senza modello | venv locale, Python 3.13.14 | `python -m pytest` | 83 | 0 | 3 |
| Suite senza modello | container `test`, Python 3.14.9 | `docker compose --profile test run --rm --build test` | 83 | 0 | 3 |
| Prove reali con LM Studio | venv locale, modello `google/gemma-4-e2b` | `$env:RUN_LMSTUDIO_TESTS = "1"; python -m pytest -m lmstudio -v` | 3 | 0 | 0 |
| Checklist manuale in Docker | container `assistente` + LM Studio sull'host | `docker compose run --rm -T --build assistente` | 4 | 0 | 0 |
| Serie di città | venv locale, `python -m assistente`, una sessione per domanda | «Che ore sono a <città>?» | 20 | 0 | 0 |

Test nuovi, superati su 3.13 e 3.14:
- `test_main_name_beats_alternate_name_of_bigger_city[Zaragoza]`, `[Islamabad]`, `[Cancun]`;
- `test_much_bigger_city_wins_with_alternate_name[Roma]`, `[Mexico]`.

### Checklist manuale in Docker

| Passo | Osservato | Esito |
|---|---|---|
| «Che ore sono a Miami?» | `{'city': 'Miami'}` → `2026-11-02T04:19:35-05:00 (Miami, US, fuso America/New_York)` | superato |
| «Quale città ti ho chiesto prima?» | «Mi hai chiesto l'ora a Miami.» | superato |
| nuovo avvio, stessa domanda | «Non mi hai chiesto una città prima in questa conversazione.» | superato |
| «Che ore sono?» | `{}` → `2026-11-02T10:20:25+01:00 (fuso predefinito Europe/Rome)` | superato |

### Serie di città

Tra le 10:20 e le 10:39 ora di Roma, ogni domanda in una sessione nuova. Le 17 città della
sessione su `5df730f` hanno dato gli stessi argomenti e gli stessi fusi (Miami 5 su 5 con
`{'city': 'Miami'}`). Città aggiunte per la correzione:

| Città | Argomenti dello strumento | Risultato | Esito |
|---|---|---|---|
| Saragozza | `{'city': 'Saragozza'}` | `Zaragoza, ES, fuso Europe/Madrid` | superato |
| Islamabad | `{'city': 'Islamabad'}` | `Islamabad, PK, fuso Asia/Karachi` | superato |
| Roma | `{'city': 'Roma'}` | `Rome, IT, fuso Europe/Rome` | superato |

**San Francisco, primo tentativo: errore di LM Studio.** La domanda è rimasta senza risposta per
12 minuti, poi l'applicazione ha mostrato `Errore: il modello non ha risposto (Error code: 400).
Domanda scartata, riprova.` e si è chiusa regolarmente.
- Nel log del server (`~/.lmstudio/server-logs`) il prompt è stato elaborato alle 10:24:15; alle
  10:36:15 compare `[ERROR][google/gemma-4-e2b] Error: Channel Error` e il task viene annullato.
- È quindi un errore interno di LM Studio. La domanda successiva ha funzionato normalmente.
- Ripetuta in una sessione nuova alle 10:39: `{'city': 'San Francisco'}` →
  `2026-11-02T01:39:42-08:00 (San Francisco, US, fuso America/Los_Angeles)`, superato.

### Resta da provare

- La checklist da un terminale interattivo vero (`docker compose run --rm assistente`, senza `-T`).

## Sessione del 2026-11-02 — commit `5df730f`

Stato dopo l'orologio per città (`8cddce3`) e i log dei messaggi al modello (`5df730f`).

### Riepilogo

| Verifica | Ambiente | Comando | Superati | Non superati | Skipped |
|---|---|---|---|---|---|
| Suite senza modello | venv locale, Python 3.13.14 | `python -m pytest -v` | 78 | 0 | 3 |
| Suite senza modello | container `test`, Python 3.14.9 | `docker compose --profile test run --rm --build test` | 78 | 0 | 3 |
| Prove reali con LM Studio | venv locale, modello `google/gemma-4-e2b` | `$env:RUN_LMSTUDIO_TESTS = "1"; python -m pytest -m lmstudio -v` | 3 | 0 | 0 |
| Checklist manuale in Docker | container `assistente` + LM Studio sull'host | `docker compose run --rm -T --build assistente` | 4 | 0 | 0 |
| Serie di città | venv locale, `python -m assistente`, una sessione per domanda | «Che ore sono a <città>?» | 17 | 0 | 0 |

I 3 skipped delle suite senza modello sono le prove reali, superate nell'esecuzione dedicata.
Su 3.13 e 3.14 l'esito di ogni singolo test è identico (confronto delle due esecuzioni con `-v`).

### Suite senza modello (3.13 e 3.14)

Per file: `test_cities.py` 13, `test_cli.py` 19, `test_config.py` 10, `test_graph.py` 20,
`test_model.py` 5, `test_tools.py` 11, tutti superati; `integration/test_lmstudio.py` 3 skipped.
I test già presenti nella sessione del 2026-10-29 sono tutti superati. Test nuovi o modificati:

| File | Test | Esito |
|---|---|---|
| `test_cities.py` | `test_find_city[Miami]`, `[Nuova York]`, `[pechino]`, `[Città del Messico]`, `[Citta del Messico]`, `[  KYOTO ]` | superati |
| `test_cities.py` | `test_homonyms_pick_most_populous` | superato |
| `test_cities.py` | `test_country_after_comma_is_ignored[Miami, Florida]`, `[Miami, USA]` | superati |
| `test_cities.py` | `test_unknown_or_empty_city[Xyzville]`, `[]`, `[   ]`, `[,]` | superati |
| `test_tools.py` | `test_time_in_city` | superato |
| `test_tools.py` | `test_iana_name_is_accepted[Asia/Tokyo]`, `[ asia/tokyo ]` | superati |
| `test_tools.py` | `test_missing_city_uses_default[None]`, `[]`, `[   ]` | superati |
| `test_tools.py` | `test_unknown_city_returns_error_text[Xyzville]`, `[../etc/passwd]` | superati |
| `test_tools.py` | `test_tool_uses_injected_clock`, `test_old_timezone_argument_falls_back_to_default`, `test_tool_schema` | superati |
| `test_graph.py` | `test_model_exchange_is_logged` | superato |
| `test_graph.py` | `test_system_prompt_logged_only_on_first_question` | superato |
| `test_graph.py` | `test_newlines_are_escaped_in_logs` | superato |
| `test_graph.py` | `test_invalid_call_is_logged` | superato |
| `test_graph.py` | `test_block_content_is_logged_as_text` | superato |
| `test_cli.py` | `test_system_prompt_mentions_city_parameter` | superato |

I vecchi test sul parametro `timezone` di `test_tools.py` sono stati sostituiti da quelli sopra.

### Prove reali con LM Studio

| Test | Esito |
|---|---|
| `test_real_model_answers` | superato |
| `test_real_model_remembers_previous_turn` | superato |
| `test_real_model_uses_clock_tool` (ora chiede Miami e verifica `America/New_York`) | superato |

### Checklist manuale in Docker

Domande inviate da stdin, due sessioni, alle 10:09 ora di Roma (04:09 a Miami).

| Passo | Atteso | Osservato | Esito |
|---|---|---|---|
| «Che ore sono a Miami?» | chiamata con la città, fuso `America/New_York`, righe `→`/`←` nei log | `← modello [chiamata] get_current_time {'city': 'Miami'}` → `2026-11-02T04:09:01-05:00 (Miami, US, fuso America/New_York)`; «sono le 04:09» | superato |
| «Quale città ti ho chiesto prima?» | la risposta cita Miami | «Mi hai chiesto le ore a Miami.» | superato |
| `esci`, nuovo avvio, stessa domanda | il modello non lo sa | «Non mi hai chiesto prima alcuna città.» | superato |
| «Che ore sono?» | fuso predefinito | `get_current_time {}` → `2026-11-02T10:09:45+01:00 (fuso predefinito Europe/Rome)`; «le ore 10:09:45» | superato |

### Serie di città

Ogni domanda in una sessione nuova, tra le 10:02 e le 10:07 ora di Roma. Ore controllate con
`zoneinfo` di Python.

| Città | Argomenti dello strumento | Fuso nel risultato | Risposta coerente |
|---|---|---|---|
| Miami (5 volte) | `{'city': 'Miami'}` ×5 | `America/New_York` (−05:00) | sì ×5 (04:02–04:03) |
| Bari | `{'city': 'Bari'}` | `Europe/Rome` | sì |
| Kyoto | `{'city': 'Kyoto'}` | `Asia/Tokyo` | sì |
| Pechino | `{'city': 'Pechino'}` | `Asia/Shanghai` (Beijing) | sì |
| Nuova York | `{'city': 'Nuova York'}` | `America/New_York` (New York City) | sì |
| Monaco di Baviera | `{'city': 'Monaco di Baviera'}` | `Europe/Berlin` (Munich) | sì |
| San Francisco | `{'city': 'San Francisco'}` | `America/Los_Angeles` | sì |
| Buenos Aires | `{'city': 'Buenos Aires'}` | `America/Argentina/Buenos_Aires` | sì |
| Mumbai | `{'city': 'Mumbai'}` | `Asia/Kolkata` (+05:30) | sì |
| Dubai | `{'city': 'Dubai'}` | `Asia/Dubai` | sì |
| Sydney | `{'city': 'Sydney'}` | `Australia/Sydney` (+11:00) | sì |
| Città del Messico | `{'city': 'Città del Messico'}` | `America/Mexico_City` | sì |
| Chioggia | `{'city': 'Chioggia'}` | `Europe/Rome` | sì |

Confronto con la sessione di base: Miami passa da 1 risposta giusta su 5 a 5 su 5; Bari ora ha
la città negli argomenti invece di `{}`.

### Resta da provare

- La checklist da un terminale interattivo vero (`docker compose run --rm assistente`, senza `-T`).

## Sessione del 2026-10-29 — commit `302f4a8` (sessione di base, prima dell'orologio per città)

### Riepilogo

| Verifica | Ambiente | Comando | Superati | Non superati | Skipped |
|---|---|---|---|---|---|
| Suite senza modello | venv locale, Python 3.13.14 | `python -m pytest -v` | 57 | 0 | 3 |
| Suite senza modello | container `test`, Python 3.14.9 | `docker compose --profile test run --rm --build test` | 57 | 0 | 3 |
| Prove reali con LM Studio | venv locale, modello `google/gemma-4-e2b` | `$env:RUN_LMSTUDIO_TESTS = "1"; python -m pytest -m lmstudio -v` | 3 | 0 | 0 |
| Checklist manuale in Docker | container `assistente` + LM Studio sull'host | `docker compose run --rm assistente` | 3 | 0 | 0 |

I 3 skipped delle suite senza modello sono le prove reali di `tests/integration/test_lmstudio.py`,
disattivate senza `RUN_LMSTUDIO_TESTS=1` e superate nell'esecuzione dedicata della riga 3.
Su 3.13 e 3.14 l'esito di ogni singolo test è identico.

### Suite senza modello (3.13 e 3.14)

`tests/test_cli.py` — 18 superati

| Test | Esito |
|---|---|
| `test_exit_words_end_loop[esci]` | superato |
| `test_exit_words_end_loop[exit]` | superato |
| `test_exit_words_end_loop[  Esci ]` | superato |
| `test_exit_words_end_loop[EXIT]` | superato |
| `test_eof_and_ctrl_c_end_loop[EOFError]` | superato |
| `test_eof_and_ctrl_c_end_loop[KeyboardInterrupt]` | superato |
| `test_blank_lines_are_ignored` | superato |
| `test_reply_is_printed` | superato |
| `test_history_is_kept_between_turns` | superato |
| `test_empty_reply_prints_placeholder` | superato |
| `test_ctrl_c_while_waiting_exits_cleanly` | superato |
| `test_model_error_discards_question_and_continues` | superato |
| `test_main_fails_with_missing_config` | superato |
| `test_http_client_loggers_are_quiet[httpx]` | superato |
| `test_http_client_loggers_are_quiet[httpx2]` | superato |
| `test_http_client_loggers_are_quiet[httpcore]` | superato |
| `test_http_client_loggers_are_quiet[openai]` | superato |
| `test_unexpected_model_error_discards_question_and_continues` | superato |

`tests/test_config.py` — 10 superati

| Test | Esito |
|---|---|
| `test_missing_required_variables_are_named` | superato |
| `test_blank_value_counts_as_missing` | superato |
| `test_values_are_read_and_stripped` | superato |
| `test_log_level_is_normalized_and_validated` | superato |
| `test_environment_wins_over_dotenv` | superato |
| `test_tool_defaults` | superato |
| `test_invalid_max_tool_steps[0]` | superato |
| `test_invalid_max_tool_steps[-1]` | superato |
| `test_invalid_max_tool_steps[tre]` | superato |
| `test_default_timezone_is_validated_and_canonical` | superato |

`tests/test_graph.py` — 15 superati

| Test | Esito |
|---|---|
| `test_reply_without_tool_calls_ends_after_one_model_call` | superato |
| `test_model_receives_all_messages` | superato |
| `test_graph_has_model_node` | superato |
| `test_graph_has_tool_and_limit_nodes` | superato |
| `test_tool_call_runs_tool_and_returns_result_to_model` | superato |
| `test_parallel_tool_calls_count_as_one_step` | superato |
| `test_limit_stops_the_loop` | superato |
| `test_limit_is_logged_as_warning` | superato |
| `test_unknown_tool_returns_error` | superato |
| `test_tool_exception_returns_error` | superato |
| `test_malformed_tool_args_return_error` | superato |
| `test_tool_calls_are_logged` | superato |
| `test_history_after_tool_turn_is_valid_for_next_turn` | superato |
| `test_invalid_tool_call_gets_error_reply` | superato |
| `test_limit_closes_invalid_tool_calls` | superato |

`tests/test_model.py` — 5 superati

| Test | Esito |
|---|---|
| `test_check_model_accepts_listed_model` | superato |
| `test_check_model_lists_available_models` | superato |
| `test_check_model_reports_unreachable_server` | superato |
| `test_create_chat_model_uses_settings` | superato |
| `test_create_chat_model_binds_clock_tool` | superato |

`tests/test_tools.py` — 9 superati

| Test | Esito |
|---|---|
| `test_time_in_requested_zone` | superato |
| `test_missing_zone_uses_default[None]` | superato |
| `test_missing_zone_uses_default[]` | superato |
| `test_missing_zone_uses_default[   ]` | superato |
| `test_zone_name_is_case_and_space_insensitive` | superato |
| `test_unknown_zone_returns_error_text[Marte/Base]` | superato |
| `test_unknown_zone_returns_error_text[../etc/passwd]` | superato |
| `test_tool_uses_injected_clock` | superato |
| `test_tool_schema` | superato |

`tests/integration/test_lmstudio.py` — 3 skipped (motivo: `prova reale: imposta RUN_LMSTUDIO_TESTS=1`)

### Prove reali con LM Studio

| Test | Esito |
|---|---|
| `test_real_model_answers` | superato |
| `test_real_model_remembers_previous_turn` | superato |
| `test_real_model_uses_clock_tool` | superato |

### Checklist manuale in Docker

Domande inviate da stdin (`docker compose run --rm -T assistente`) alle 10:15 ora di Roma.

| Passo | Atteso | Osservato | Esito |
|---|---|---|---|
| «Che ore sono a Tokyo?» | riga `strumento richiesto: get_current_time …` su stderr, ora coerente | `get_current_time {'timezone': 'Asia/Tokyo'}` → `2026-10-29T18:15:19+09:00`; risposta «le ore 18:15» | superato |
| «Quale città ti ho chiesto prima?» | la risposta cita Tokyo | «Mi hai chiesto le ore a Tokyo.» | superato |
| `esci`, nuovo avvio, stessa domanda | il modello non lo sa | «Non mi hai chiesto alcuna città prima in questa conversazione.» | superato |

### Serie di città (prima della modifica)

Strumento con il solo parametro `timezone` (nome IANA), una sessione per domanda.

| Città | Esito |
|---|---|
| Miami (5 volte) | 1 risposta giusta su 5; nelle altre 4 il modello ha chiamato `get_current_time {}` e lo strumento ha usato `Europe/Rome` |
| Bari | chiamata `{}`; risposta giusta solo perché Bari ha lo stesso fuso di Roma |
| Kyoto, Pechino, Nuova York | fuso corretto |

Questo esito ha motivato l'orologio per città (vedi `registro-modifiche.md`).

### Resta da provare

- La checklist da un terminale interattivo vero (`docker compose run --rm assistente`, senza `-T`).
