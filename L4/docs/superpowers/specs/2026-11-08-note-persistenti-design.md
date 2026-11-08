# Note persistenti

Data: 2026-11-08, approvata dall'utente il 2026-11-08. Branch: `feat/note-persistenti` (da `dev` = `b70a8a7`). Quinto
strumento della roadmap in `CLAUDE.md`, primo server MCP. Il client MCP dell'agente è generico: il
sesto strumento (meteo, anch'esso un server MCP) lo riuserà senza modificarlo.

## 1. Obiettivo

Il modello può salvare, elencare ed eliminare note che restano anche dopo la fine della sessione. La
logica sta in un server MCP separato, `servizio_note`, che conserva le note in un file SQLite;
l'agente lo avvia come sottoprocesso e gli parla via stdio con l'SDK ufficiale `mcp`. Nomi,
descrizioni e parametri degli strumenti sono dichiarati dal server e letti dall'agente con
`list_tools`.

Scopo dichiarato dall'utente: esercitare il meccanismo MCP + SQLite. Il contenuto delle note conta
poco; conta che il modello vero aggiunga, elenchi ed elimini chiamando davvero gli strumenti e che
le note sopravvivano al riavvio dell'applicazione, anche in Docker.

### Scelte dell'utente (brainstorming del 2026-11-08)

- Scopo: esercizio sul meccanismo (opzione C); una nota è id, testo, data di creazione.
- Eliminazione per id (opzione A): se l'utente descrive la nota, il modello chiama prima
  `list_notes`. Nessuna eliminazione di massa.
- Client MCP con una sessione per chiamata (approccio 1): ogni chiamata avvia il sottoprocesso,
  apre la sessione, chiama lo strumento e chiude tutto. Scartati: sessione unica con thread ponte
  (ciclo di vita, chiusura e riavvio da gestire) e `langchain-mcp-adapters` (dipendenza in più,
  strumenti solo asincroni, nasconde il meccanismo).
- Note e meteo non si sviluppano in parallelo: prima le note, con il client pensato per il riuso.

### Criteri di successo

- Con LM Studio e `google/gemma-4-e2b`, in almeno 8 tentativi su 10 per ciascuna domanda (serie del
  §7), con una cronologia nuova a ogni tentativo:
  1. «Annota che il banco 3 ha la presa rotta» → `add_note` con «presa» nel testo;
  2. «Quali note ho salvato?» (archivio con note) → `list_notes` e risposta che cita le note;
  3. «Cancella la nota sulla presa del banco 3» → `list_notes`, poi `delete_note` con l'id giusto, e
     la nota non è più nell'archivio;
  4. «Cancella la nota 99» (id inesistente) → `delete_note` e risposta che non dice che la nota è
     stata eliminata.
- Una nota salvata in una sessione compare in una sessione successiva, sia dalla venv sia in Docker
  (due `docker compose run` di seguito).
- La suite senza modello passa su Python 3.13 (venv) e 3.14 (container).
- Gli strumenti esistenti continuano a funzionare: i loro test passano senza modifiche.

### Fuori ambito

Modifica del testo di una nota, ricerca nelle note, eliminazione di più note in una chiamata,
categorie o titoli, paginazione oltre le 20 righe, più utenti, autenticazione, sessione MCP unica
per tutta la chat, trasporti diversi da stdio, uso del server da altri client MCP (possibile ma non
verificato), migrazioni dello schema.

## 2. Gli strumenti visti dal modello

Nomi e parametri in inglese, testi in italiano, come gli strumenti esistenti. Tre strumenti; con
quelli attuali (9) diventano 12.

| Strumento | Parametri |
|---|---|
| `add_note` | `text: str` |
| `list_notes` | nessuno |
| `delete_note` | `id: int` |

### 2.1 Descrizioni esatte (docstring degli strumenti nel server)

- `add_note`: «Salva una nota nell'archivio delle note persistenti, che restano anche dopo la fine
  della sessione. Parametro text: il testo della nota, come l'utente vuole ricordarlo. Usalo quando
  l'utente chiede di annotare, segnare o ricordare qualcosa.»
- `list_notes`: «Elenca le note salvate, dalla più recente, con id, data e testo. Usalo per mostrare
  le note all'utente e per trovare l'id di una nota da eliminare.»
- `delete_note`: «Elimina una nota dato il suo id, un numero intero. Se non conosci l'id usa prima
  list_notes: non indovinarlo.»

### 2.2 Frase nel prompt di sistema (in coda a `SYSTEM_PROMPT`)

«Per salvare, elencare o eliminare note usa add_note, list_notes e delete_note; per eliminare una
nota serve il suo id: se non lo conosci chiama prima list_notes. Non dire che una nota è stata
salvata o eliminata se lo strumento non lo conferma.»

### 2.3 Testi di successo

- `add_note`: il testo viene ripulito dagli spazi iniziali e finali; duplicati ammessi.
  `Nota 3 salvata: «calibrare il multimetro».`
- `list_notes`, dalla più recente (id decrescente), al massimo 20 righe:
  ```
  3 note salvate, dalla più recente:
  - 3 (2026-11-08 21:40): calibrare il multimetro
  - 2 (2026-11-08 18:02): banco 3, presa rotta
  - 1 (2026-11-07 09:15): ordinare resistenze da 220 ohm
  ```
  - con una sola nota la prima riga è `1 nota salvata:`;
  - oltre 20 note, dopo le 20 righe: `Altre N note non mostrate.` (`Altra 1 nota non mostrata.` se
    N = 1); la prima riga riporta il totale;
  - nessuna nota: `Nessuna nota salvata.`
  - data e ora: `creata` (UTC) convertita nel fuso `NOTE_TIMEZONE`, formato `AAAA-MM-GG HH:MM`.
- `delete_note`: `Nota 3 eliminata: «calibrare il multimetro».`

### 2.4 Testi d'errore

Il server segnala gli errori previsti con `ToolError` (risultato MCP con `isError`). L'SDK antepone
`Error executing tool <nome>: `; il client lo toglie e restituisce `Errore: <messaggio>`.

| Caso | Testo restituito al modello |
|---|---|
| testo vuoto o di soli spazi | `Errore: il testo della nota è vuoto.` |
| testo oltre 1000 caratteri (dopo la pulizia) | `Errore: il testo della nota supera 1000 caratteri.` |
| id inesistente (anche 0 o negativo) | `Errore: nessuna nota con id 7. Usa list_notes per vedere gli id.` |
| argomenti rifiutati dall'SDK (es. `id: "x"`) | `Errore: <testo di validazione dell'SDK>`, così com'è |
| archivio inutilizzabile (`sqlite3.Error`, `NOTE_DB_PATH` mancante, `NOTE_TIMEZONE` non valido) | `Errore: archivio delle note non utilizzabile (<dettaglio>). <NOTE_FAILURE_HINT>` |
| guasto del server (§6) | `Errore: server delle note non disponibile (<motivo>). <NOTE_FAILURE_HINT>` |

`NOTE_FAILURE_HINT` = `Non è possibile leggere o modificare le note: dillo all'utente e non
inventarle.`

## 3. Il server MCP

### 3.1 Archivio SQLite

- Tabella creata al primo uso, insieme alla cartella del file:
  `CREATE TABLE IF NOT EXISTS note (id INTEGER PRIMARY KEY AUTOINCREMENT, testo TEXT NOT NULL,
  creata TEXT NOT NULL)`.
- `AUTOINCREMENT` di proposito: un id eliminato non viene mai riassegnato, quindi un «elimina la 3»
  detto più tardi non colpisce una nota nuova.
- `creata`: istante UTC in ISO 8601 con secondi e offset, es. `2026-11-08T20:40:12+00:00`.
- Una connessione per operazione, chiusa alla fine (il processo dura una chiamata).

### 3.2 Configurazione del server (variabili d'ambiente, lette a ogni chiamata)

- `NOTE_DB_PATH`: percorso del file SQLite. Mancante o vuota → archivio inutilizzabile (§2.4).
- `NOTE_TIMEZONE`: nome IANA per mostrare le date; mancante → `Europe/Rome`; non valido → archivio
  inutilizzabile (§2.4).

### 3.3 Avvio e log

- `python -m servizio_note.server` avvia il server su stdio.
- `MCPServer("note", log_level="WARNING")`: i `ToolError` previsti, che l'SDK registra a `INFO`
  sullo stderr ereditato dall'agente, non compaiono nel terminale della chat; un crash resta
  visibile.

## 4. Struttura del codice

| File | Contenuto |
|---|---|
| `servizio_note/__init__.py` | vuoto |
| `servizio_note/archivio.py` | `Note` (`dataclass(frozen=True)`: `id`, `testo`, `creata: datetime`), `add(path, text, now) -> Note`, `list_recent(path, limit) -> tuple[list[Note], int]` (note e totale), `delete(path, id) -> Note \| None`. Solo libreria standard: nessuna dipendenza da `mcp`. Gli `sqlite3.Error` salgono al chiamante. |
| `servizio_note/server.py` | `NOTE_FAILURE_HINT`, `MAX_TEXT = 1000`, `MAX_ROWS = 20`, `server = MCPServer("note", log_level="WARNING")`, i tre strumenti del §2 (validazione, formattazione, `sqlite3.Error` → `ToolError`), `_now()` (istante UTC, sostituibile nei test), `main()`. |
| `assistente/mcp_client.py` | `MCPStartupError`, `load_mcp_tools(server, failure_hint, timeout=10.0) -> list[BaseTool]`. Nulla di specifico delle note. |
| `assistente/notes.py` | `NOTE_FAILURE_HINT` (copia identica di quella del server), `make_note_tools(db_path, timezone, timeout=10.0)`. |
| `assistente/config.py` | `NOTE_DB_PATH` obbligatoria, resa assoluta rispetto alla cartella corrente; campo `Settings.note_db_path` (predefinito `dati/note.db`, solo per i test che costruiscono `Settings` a mano). |
| `assistente/cli.py` | frase del §2.2; `make_tools` con gli strumenti delle note (12 in tutto); `main()` gestisce `MCPStartupError`. |

### 4.1 `load_mcp_tools`

- `server` è ciò che accetta `mcp.Client`: `StdioServerParameters` (sottoprocesso) oppure, nei test,
  un `MCPServer` collegato in-process.
- All'avvio: una sessione, `list_tools`, chiusura. Per ogni strumento uno `StructuredTool` con
  `name` e `description` del server e `args_schema` = `input_schema` del server (dizionario JSON
  Schema). Qualsiasi errore, compreso il tempo limite → `MCPStartupError` con un motivo leggibile.
- Funzione sincrona di ogni strumento: `asyncio.run(...)` di una sessione nuova (avvio, `call_tool`,
  chiusura), tutta sotto il tempo limite; poi conversione del risultato in testo:
  - non errore → testo dei blocchi di contenuto testuale uniti da `\n`;
  - errore con prefisso `Error executing tool <nome>: ` → `Errore: <resto>`;
  - errore senza quel prefisso, o risultato senza testo → guasto con motivo `errore interno del
    server`.
- Gli strumenti non sollevano mai eccezioni verso il grafo, tranne `KeyboardInterrupt` (§6).

### 4.2 `make_note_tools`

`StdioServerParameters(command=sys.executable, args=["-m", "servizio_note.server"],
env={"NOTE_DB_PATH": db_path, "NOTE_TIMEZONE": timezone}, cwd=<cartella del progetto>)`, dove la
cartella del progetto è quella che contiene `assistente/` (così `servizio_note` è importabile da
qualsiasi cartella corrente). Poi `load_mcp_tools(params, NOTE_FAILURE_HINT, timeout)`.

## 5. Configurazione, dipendenze e Docker

- Dipendenza nuova: `mcp==2.3.0` in `requirements.txt` (SDK ufficiale; `MCPServer` per il server,
  `Client` e `StdioServerParameters` per il client). Prova del 2026-11-08 in una venv usa e getta
  con le dipendenze attuali: installazione riuscita, `pip check` senza problemi, giro stdio di circa
  1 s per chiamata su Windows.
- `.env.example`: `NOTE_DB_PATH=dati/note.db` con un commento (percorso relativo alla cartella da
  cui si avvia l'app). Il `.env` locale dell'utente va aggiornato allo stesso modo.
- `.gitignore`: `dati/` e `*.db`. `.dockerignore`: `dati`.
- `Dockerfile`: `COPY servizio_note/ servizio_note/` negli stage `test` e `app`; nello stage `app`,
  prima di `USER assistente`, `RUN mkdir -p /app/dati && chown assistente /app/dati`, così il volume
  nasce scrivibile dall'utente del container.
- `compose.yaml`: nessun servizio nuovo (il server è un sottoprocesso dell'agente, nessuna porta);
  il servizio `assistente` riceve `NOTE_DB_PATH: /app/dati/note.db` e il volume con nome `note`
  montato su `/app/dati`. `docker compose down -v` cancella le note.
- Le note della venv (file in `dati/`) e quelle di Docker (volume) sono archivi separati.

## 6. Errori, tempi e chiusura

- **Avvio dell'app**: se `list_tools` non riesce (server che non parte, errore di import, tempo
  limite), `main()` stampa `Server MCP delle note non avviabile: <motivo>` su stderr ed esce con
  codice 1. Non si parte senza note: il prompt nominerebbe strumenti assenti.
- **Tempo limite**: 10 s per l'intera sessione, avvio compreso, all'avvio e in ogni chiamata.
  Scaduto: la sessione si chiude (l'SDK termina il sottoprocesso) e il testo è il guasto con motivo
  `nessuna risposta entro <limite> s` (con il limite predefinito: `nessuna risposta entro 10 s`).
- **Guasti durante una chiamata** (avvio fallito, processo caduto, errore di protocollo): testo di
  guasto con motivo = prima riga del messaggio dell'eccezione, o il nome della sua classe se il
  messaggio è vuoto.
- **Chiusura**: con una sessione per chiamata non c'è nulla da chiudere all'uscita. Un Ctrl+C
  durante una chiamata interrompe `asyncio.run`, l'SDK termina il sottoprocesso e
  `KeyboardInterrupt` arriva a `run_chat`, che esce come oggi.
- **Log dell'agente**: invariati (`strumento richiesto`, `risultato strumento`); `graph.py` non
  cambia.

## 7. Test e verifiche

### Test automatici (senza modello e senza rete, scritti prima del codice)

- `tests/test_archivio_note.py` (`tmp_path`): file e cartella creati al primo uso; `add` restituisce
  la nota con id e `creata` dall'istante passato; `list_recent` dalla più recente con limite e
  totale; `delete` restituisce la nota eliminata o `None`; id non riusati dopo un'eliminazione;
  dati presenti in connessioni successive.
- `tests/test_server_note.py`: server in-process con `mcp.Client(server)` dentro `asyncio.run`
  (nessuna dipendenza `pytest-asyncio`); `NOTE_DB_PATH` e `NOTE_TIMEZONE` impostate con
  `monkeypatch`, `_now` sostituita. Nomi, descrizioni e schemi da `list_tools`; tutti i testi dei
  §2.3 e §2.4 (singolare e plurale, 20 righe, «Altre N»/«Altra 1», pulizia degli spazi, limite di
  1000 caratteri, id inesistente, archivio inutilizzabile con `NOTE_DB_PATH` mancante, con un
  percorso che è una cartella e con `NOTE_TIMEZONE` non valido); ora mostrata nel fuso indicato con
  un istante controllato (anche a cavallo della mezzanotte UTC).
- `tests/test_mcp_client.py`: piccolo `MCPServer` finto in-process. Conversione in `StructuredTool`
  (nome, descrizione, schema); risultato testuale; prefisso dell'SDK tolto; errore senza prefisso →
  guasto con la coda passata; tempo limite con uno strumento lento e un limite ridotto; errore in
  `list_tools` → `MCPStartupError`.
- `tests/test_note_stdio.py`: un test con il sottoprocesso vero, `make_note_tools` su un archivio
  temporaneo: aggiungi (testo con accenti e virgolette basse) → elenca → elimina via stdio. Nessun
  modello né rete: gira nella suite normale su 3.13 e 3.14.
- `tests/test_config.py`: `NOTE_DB_PATH` mancante → errore; valore relativo reso assoluto.
- `tests/test_cli.py`: `make_tools` con un `make_note_tools` finto restituisce 12 strumenti con
  nomi distinti; `SYSTEM_PROMPT` contiene la frase del §2.2; `main()` con `MCPStartupError` →
  codice 1 e messaggio; le due copie di `NOTE_FAILURE_HINT` coincidono.

### Prove reali (separate, attivate esplicitamente)

- `tests/integration/test_lmstudio.py`: `test_real_model_uses_notes` su un archivio temporaneo.
  Sessione 1: «Annota che il banco 3 ha la presa rotta» → chiamata a `add_note`. Sessione 2 (nuova
  cronologia, stesso archivio): «Quali note ho?» → chiamata a `list_notes` e risposta con «presa».
- Serie con `google/gemma-4-e2b`, 10 tentativi per ciascuna domanda del §1, cronologia nuova a ogni
  tentativo, archivio preparato per ciascuna domanda (vuoto per la 1, con note per la 2-4), script
  usa e getta nella scratchpad che registra strumenti chiamati, argomenti, risultati e risposta.
  Esito sotto la soglia: si riporta all'utente, nessuna correzione senza accordo.
- Archivio inutilizzabile (`NOTE_DB_PATH` che punta a una cartella): 10 tentativi di «Annota che il
  banco 3 ha la presa rotta»; si contano le risposte che dicono che la nota è salvata. Nessuna
  soglia: esito riportato all'utente.
- Persistenza dalla venv: nota salvata in una sessione di `python -m assistente`, elencata dopo il
  riavvio.
- Checklist Docker: `"Annota che il banco 3 ha la presa rotta", "esci" | docker compose run --rm -T
  --build assistente`, poi `"Quali note ho?", "esci" | docker compose run --rm -T assistente` → la
  nota compare; più le voci esistenti nella verifica completa prima del push.

## 8. Documentazione e commit

- README: configurazione (`NOTE_DB_PATH`), sezione «Strumenti delle note» (server MCP, sottoprocesso
  stdio, archivio, volume Docker, cancellazione delle note, archivi separati venv/Docker), testi
  d'esempio dai log reali, diagnosi (server non avviabile, archivio non utilizzabile, tempo limite);
  solo comandi verificati.
- `CLAUDE.md`: struttura (`servizio_note/`, `mcp_client.py`, `notes.py`), `NOTE_DB_PATH`
  obbligatoria, volume `note`; modifica proposta all'utente prima di farla.
- `tests/test-manuali.txt` (escluso da Git): voci delle note.
- `docs/registro-test.md`: esiti; `docs/registro-modifiche.md` per eventuali correzioni.
- Piano approvato copiato in `Es.1/plan.md` (commit `docs:`).
- Commit in Conventional Commits in italiano (`feat(note): …`, `test(note): …`, `build: …`,
  `docs: …`); merge in `dev` con l'ok dell'utente, push solo su richiesta.

## 9. Correzione dopo la revisione finale (2026-11-08, approvata dall'utente il 2026-11-08)

La revisione finale del branch (subagent opus, `b70a8a7..1f1122a`) ha dato «Ready to merge» con 0
problemi critici, 0 importanti e 5 minori. L'utente ha chiesto di correggere il primo.

### 9.1 Un id fuori dagli interi di SQLite è un id inesistente

`delete_note` con un id fuori dai 64 bit con segno (es. `10**30`) passava la validazione dell'SDK,
poi `sqlite3` sollevava `OverflowError`, che non è un `sqlite3.Error`: l'SDK lo trattava come un
crash, con il traceback del server nel terminale della chat e il testo «server delle note non
disponibile (errore interno del server)» per un id che semplicemente non esiste.

Correzione: un id fuori da `-(2**63)`…`2**63 - 1` dà lo stesso testo di un id inesistente
(§2.4), senza interrogare l'archivio.

### 9.2 Minori lasciati all'utente

- Il tempo limite reale è circa limite + 2 s (attesa di chiusura del processo nell'SDK).
- `list_notes` comprime in uno spazio anche tabulazioni e spazi multipli, non solo gli a capo.
- In `archivio._connect` la connessione non si chiude se la creazione della tabella fallisce.
- `test_startup_server_hangs` non verifica che il processo figlio sia terminato.
