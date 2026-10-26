# Assistente del laboratorio — grafo LangGraph con strumento orologio

Data: 2026-10-26
Stato: in revisione

## 1. Obiettivo

Applicazione Python da terminale che conversa con un modello servito da LM Studio sull'host,
organizzando il flusso in un grafo LangGraph esplicito. Il modello può richiedere uno strumento
orologio; il grafo lo esegue, restituisce il risultato al modello e ottiene la risposta finale.
La cronologia vale per la sessione e si perde alla chiusura. L'applicazione si avvia anche con
Docker Compose; LM Studio resta sull'host.

### Criteri di successo

- Con `docker compose run --rm assistente`, alla domanda «Che ore sono a Tokyo?» compare nei log
  la chiamata a `get_current_time` e la risposta è coerente con l'ora reale di Tokyo.
- Una domanda successiva che si riferisce alla precedente riceve una risposta che ne tiene conto.
- Dopo l'uscita e un nuovo avvio la cronologia è vuota.
- `pytest` passa con LM Studio spento, sia nel venv locale (Python 3.13) sia nel container
  (Python 3.14).
- La prova reale con LM Studio (`google/gemma-4-e2b`) dimostra almeno una chiamata effettiva
  allo strumento.

### Fuori ambito

MCP, RAG, workflow, altri strumenti, interfacce web o grafiche, servizi cloud, persistenza della
cronologia, streaming delle risposte.

## 2. Contesto e posizione

- La radice del progetto è `Es.1/L4` (la cartella che `CLAUDE.md` chiama `assistente-laboratorio/`).
- Spec e piano stanno in `L4/docs/superpowers/specs/` e `L4/docs/superpowers/plans/`; ogni piano
  approvato viene inoltre aggiunto a `Es.1/plan.md`.
- Le altre lezioni (`L3/`) non vengono lette né modificate.
- Stato iniziale: `L4/` contiene solo `CLAUDE.md` (non tracciato); `L4/main.py` (vuoto in HEAD)
  risulta cancellato e non in stage; nessun `.gitignore` alla radice della repository.

## 3. Scelte tecniche

| Ambito | Scelta |
|---|---|
| Linguaggio | Python, codice sincrono; venv locale con Python 3.13, immagine Docker con Python 3.14 |
| Grafo | `langgraph`, `StateGraph` con nodi e instradamento scritti a mano |
| Modello | `langchain-openai` (`ChatOpenAI`) verso l'API compatibile OpenAI di LM Studio, con `bind_tools` |
| Strumento | `@tool` di `langchain-core`; fuso orario con `zoneinfo` + pacchetto `tzdata` |
| Configurazione | variabili d'ambiente; `python-dotenv` per leggere `.env` fuori da Docker |
| Test | `pytest` (solo in `requirements-dev.txt`) |
| Container | `Dockerfile` + `compose.yaml`; LM Studio non containerizzato |

Tutte le dipendenze hanno versione fissata (`==`) in `requirements.txt` / `requirements-dev.txt`,
scelte tra le ultime stabili compatibili con Python 3.13 e 3.14 (vedi §3.1). Approccio scartato:
`create_react_agent` di LangGraph, perché nasconde la struttura del grafo. Scartato anche l'uso
diretto dell'SDK `openai`, che richiederebbe più codice e allontanerebbe dall'ecosistema LangChain
usato nelle lezioni successive.

### 3.1 Compatibilità Python 3.13 (locale) e 3.14 (Docker)

Le due versioni possono comportarsi in modo diverso; il codice deve funzionare su entrambe e
questo va verificato, non presunto.

- **Codice:** solo sintassi e API disponibili in 3.13 e non deprecate/rimosse in 3.14. Vietati
  template string (`t"..."`), `except A, B:` senza parentesi, `annotationlib` e ogni
  introspezione manuale delle annotazioni.
- **Annotazioni (PEP 649):** in 3.14 la valutazione è differita e `@tool` ricava lo schema dalla
  firma; un test controlla lo schema JSON generato per `get_current_time` (nome, parametro
  `timezone` opzionale di tipo stringa), così una differenza tra le versioni emerge subito.
- **Dipendenze:** prima di fissare una versione si verifica che esistano wheel binarie per
  cp313 e cp314 (`pip download --only-binary=:all: --python-version 3.14 ...`), soprattutto per i
  pacchetti compilati (es. `pydantic-core`).
- **Test su entrambe:** la suite automatica gira nel venv locale (3.13) e nel container (3.14)
  tramite il target `test` del `Dockerfile` (§10). Un incremento è completo solo se passa su
  entrambe.
- **Ambienti allineati:** si confronta `pip freeze` del venv e del container; versioni transitive
  diverse vanno spiegate o fissate.

## 4. Struttura dei file

```
L4/
  assistente/
    __init__.py
    __main__.py   avvio con `python -m assistente`
    config.py     lettura e validazione delle variabili d'ambiente → Settings
    tools.py      strumento get_current_time con orologio iniettabile
    model.py      creazione del ChatOpenAI con lo strumento collegato; controllo del modello
    graph.py      stato, nodi, instradamento, build_graph(...)
    cli.py        ciclo da terminale, cronologia di sessione, configurazione dei log
  tests/
    test_tools.py
    test_config.py
    test_graph.py
    test_cli.py
    integration/
      test_lmstudio.py
  docs/superpowers/specs/, docs/superpowers/plans/
  requirements.txt, requirements-dev.txt, pytest.ini
  .env.example, .gitignore, .dockerignore
  Dockerfile, compose.yaml
  README.md, CLAUDE.md
```

Ogni modulo ha una sola responsabilità. `graph.py` non dipende da `ChatOpenAI`: riceve un oggetto
modello con metodo `invoke(messages) -> AIMessage` e un elenco di strumenti, così i test usano
uno stub.

## 5. Strumento orologio

`get_current_time(timezone: str | None = None) -> str`

- `timezone` è un nome IANA (es. `Asia/Tokyo`). Se manca si usa `DEFAULT_TIMEZONE`.
- Restituisce l'istante in ISO 8601 con offset e il nome del fuso, es.
  `2026-10-26T01:05:00+09:00 (Asia/Tokyo)`.
- Con un fuso sconosciuto restituisce un testo d'errore, es.
  `Errore: fuso orario sconosciuto 'Marte/Base'. Usa un nome IANA come 'Europe/Rome'.`
  Nessuna eccezione verso il grafo.
- La sorgente dell'istante è iniettabile (una funzione che restituisce un `datetime` UTC), così i
  test usano un istante fisso. Il fuso predefinito viene passato quando si costruisce lo strumento.

## 6. Grafo

### Stato

```
messages:   list[BaseMessage]   con reducer add_messages
tool_steps: int                 giri modello→strumenti eseguiti per la domanda corrente
```

### Nodi

- **modello**: invoca il modello con `messages` e aggiunge la `AIMessage` ricevuta.
- **strumenti**: per ogni `tool_call` dell'ultima `AIMessage` registra nel log nome e argomenti,
  esegue lo strumento, registra il risultato e aggiunge una `ToolMessage` con lo stesso
  `tool_call_id`. Strumento sconosciuto o eccezione → `ToolMessage` con il testo dell'errore.
  Incrementa `tool_steps` di 1.
- **limite**: per ogni `tool_call` in sospeso aggiunge una `ToolMessage`
  «non eseguito: limite di passaggi raggiunto», poi una `AIMessage` finale che spiega
  l'interruzione; registra un WARNING. Così la cronologia resta valida per la domanda successiva.

### Instradamento

```
START → modello
modello → strumenti   se l'ultima AIMessage ha tool_calls e tool_steps < MAX_TOOL_STEPS
modello → limite      se l'ultima AIMessage ha tool_calls e tool_steps >= MAX_TOOL_STEPS
modello → END         se l'ultima AIMessage non ha tool_calls
strumenti → modello
limite → END
```

## 7. Configurazione

| Variabile | Obbligatoria | Default | Esempio in `.env.example` |
|---|---|---|---|
| `LMSTUDIO_BASE_URL` | sì | — | `http://localhost:1234/v1` |
| `LMSTUDIO_MODEL` | sì | — | `google/gemma-4-e2b` |
| `DEFAULT_TIMEZONE` | no | `Europe/Rome` | `Europe/Rome` |
| `MAX_TOOL_STEPS` | no | `3` | `3` |
| `LOG_LEVEL` | no | `INFO` | `INFO` |

- Una variabile obbligatoria mancante, un `MAX_TOOL_STEPS` non intero o minore di 1, oppure un
  `DEFAULT_TIMEZONE` sconosciuto fermano l'avvio con un messaggio che nomina la variabile.
- Fuori da Docker `.env` viene letto con `python-dotenv`; le variabili già presenti
  nell'ambiente hanno la precedenza.
- `.env` è escluso da Git; `.env.example` non contiene credenziali. LM Studio non richiede una
  chiave: a `ChatOpenAI` si passa un valore fittizio fisso (`lm-studio`), non configurabile.

## 8. Interfaccia da terminale

- All'avvio: lettura della configurazione, configurazione dei log, controllo del modello
  (`GET /v1/models`). Se LM Studio non risponde, o `LMSTUDIO_MODEL` non è nell'elenco, uscita
  con codice diverso da zero e un messaggio che riporta l'indirizzo e i modelli disponibili.
- La cronologia è una lista in memoria che inizia con un messaggio di sistema breve in italiano
  (assistente del laboratorio; per l'ora attuale usa lo strumento `get_current_time`).
- Ciclo: prompt `Tu> `; righe vuote ignorate; `esci` / `exit`, Ctrl+D o Ctrl+C terminano in modo
  pulito. A ogni domanda il grafo viene invocato con
  `{messages: cronologia + [HumanMessage], tool_steps: 0}`; la cronologia viene sostituita con i
  `messages` restituiti e il contenuto dell'ultima `AIMessage` viene stampato come
  `Assistente> ...` su stdout.
- Errore di connessione o dell'API durante una domanda: messaggio leggibile su stderr, domanda
  scartata (cronologia invariata), il ciclo continua.
- La CLI riceve grafo, funzione di input e flusso di output come parametri, così è testabile.

## 9. Log

- Modulo `logging` su stderr; livello da `LOG_LEVEL`; formato `ora livello nome: messaggio`.
- INFO: `strumento richiesto: get_current_time {'timezone': 'Asia/Tokyo'}` e
  `risultato strumento: 2026-10-26T01:05:00+09:00 (Asia/Tokyo)`.
- WARNING: limite di passaggi raggiunto.
- I logger `httpx`, `httpcore` e `openai` vengono portati a WARNING.

## 10. Docker

- `Dockerfile` multi-stage, base `python:3.14-slim`, fissata in implementazione all'ultima patch
  3.14 disponibile sul registro:
  - target `app` (predefinito, ultimo stage): installa prima `requirements.txt`, poi copia
    `assistente/`; `PYTHONUNBUFFERED=1`, utente non root, `CMD ["python", "-m", "assistente"]`.
    Non contiene `pytest` né i test.
  - target `test`: parte dalle dipendenze dell'app, aggiunge `requirements-dev.txt`, `tests/` e
    `pytest.ini`; `CMD ["python", "-m", "pytest"]`.
- `compose.yaml`:
  - servizio `assistente` (target `app`) con `env_file: .env`,
    `environment: LMSTUDIO_BASE_URL=http://host.docker.internal:1234/v1` (sostituisce il valore
    locale), `extra_hosts: ["host.docker.internal:host-gateway"]`, `stdin_open: true`, `tty: true`;
  - servizio `test` (target `test`, `profiles: ["test"]`), così non parte con i comandi normali.
- Avvio: `docker compose build` e `docker compose run --rm assistente`.
- Test su 3.14: `docker compose --profile test run --rm --build test`.
- `.dockerignore`: `.env`, `.venv`, `__pycache__`, `.pytest_cache`, `docs`, `.git` (`tests/`
  resta nel contesto di build perché serve al target `test`, ma non viene copiato nel target `app`).
- Rischio: se LM Studio ascolta solo su `127.0.0.1` il container potrebbe non raggiungerlo; il
  README spiega come attivare «Serve on Local Network» e come verificare la connessione dal
  container.

## 11. Test e verifiche

### Automatici (senza modello)

Eseguiti con `python -m pytest` nel venv locale (3.13) e con
`docker compose --profile test run --rm --build test` (3.14); i test d'integrazione sono saltati.

- `test_tools.py`: istante fisso → ora corretta per `Asia/Tokyo`; argomento assente → fuso
  predefinito; fuso non valido → testo d'errore; schema JSON dello strumento come atteso.
- `test_config.py`: variabili obbligatorie mancanti → errore che le nomina; valori predefiniti;
  `MAX_TOOL_STEPS` e `DEFAULT_TIMEZONE` non validi → errore.
- `test_graph.py` (modello stub con risposte preparate):
  1. senza `tool_calls` → una sola chiamata al modello, fine;
  2. con una `tool_call` → strumento eseguito, il modello riceve la `ToolMessage` al secondo
     giro, risposta finale;
  3. modello che chiede sempre lo strumento con `MAX_TOOL_STEPS=2` → esattamente 2 esecuzioni,
     nodo `limite`, ogni `tool_call` ha la sua `ToolMessage`;
  4. strumento sconosciuto o in errore → `ToolMessage` d'errore, nessuna eccezione;
  5. i log contengono la chiamata e il risultato dello strumento (`caplog`);
  6. due turni consecutivi → al secondo il modello riceve domanda e risposta del primo.
- `test_cli.py`: comandi di uscita, righe vuote ignorate, errore di connessione → cronologia
  invariata e ciclo che continua.

### Reali (attivazione esplicita)

- `tests/integration/test_lmstudio.py`, marcatore `lmstudio`, saltato se `RUN_LMSTUDIO_TESTS`
  non vale `1`. Con il modello reale chiede «Che ore sono adesso a Tokyo?» e verifica almeno una
  `ToolMessage` di `get_current_time` e una risposta finale non vuota. Una risposta simulata non
  dimostra che il modello sappia usare lo strumento: questa prova sì.
- Checklist manuale nel README per Docker (PowerShell): build, avvio, domanda sull'ora con
  verifica del log, domanda di seguito per la cronologia, uscita e nuovo avvio con cronologia
  vuota, diagnosi della connessione a LM Studio.

## 12. Documentazione e Git

- README: requisiti, configurazione, avvio locale e in Docker, test automatici, prove reali,
  diagnosi. Solo comandi verificati, anche per PowerShell.
- `.gitignore` in `L4/`: `.env`, `.venv/`, `__pycache__/`, `.pytest_cache/`.
- Conventional Commits in italiano, incrementi piccoli verificati prima del commit, staging
  selettivo, nessun push senza richiesta.
