# Assistente del laboratorio

Progetto del corso «Deep Learning e LLM: costruire chatbot e agenti».
La cartella del progetto è `Es.1/L4`; all'inizio contiene soltanto questo file.
Struttura, dipendenze e comandi verranno definiti con la specifica e il piano.

## Obiettivo
Un'applicazione in Python che conversa con un modello locale e:
- organizza il flusso in un grafo LangGraph esplicito (stato, nodi, instradamento riconoscibili);
- usa un modello servito da LM Studio, che resta sul computer host;
- nella CLI conserva la cronologia della conversazione per la durata della sessione, solo in memoria;
- offre uno strumento orologio con fuso orario esplicito, richiesto dal modello tramite tool calling
  ed eseguito davvero dal programma;
- offre altri strumenti, sviluppati uno alla volta e in quest'ordine: convertitore di unità e
  calcolatrice sicura (locali, come l'orologio), giorni e scadenze e catalogo locale (servizi
  FastAPI), note persistenti e meteo (un server MCP ciascuno). Il meteo è sospeso: resta da
  terminare;
- evolve per step (lezione 6), uno alla volta e in quest'ordine: 1 router (conversazione o fuori
  ambito), 2 revisore (risposta coerente con la domanda), 3 riassunto della cronologia,
  4 resource MCP (preferenze dell'utente), 5 prompt MCP (comandi `/prompts` e `/prompt`),
  6 agente come servizio HTTP, 7 back-end con API e chat salvate su database, 8 front-end web
  di chat, 9 Docker Compose con un container per componente;
- si avvia anche con Docker Compose.

La CLI da terminale resta anche dopo l'arrivo dell'interfaccia web, come strumento per le prove
manuali durante lo sviluppo.

## Confini
- Implementare solo i requisiti concordati, uno strumento o uno step alla volta: non anticipare
  quelli successivi. RAG e altri workflow arriveranno nelle lezioni successive.
- Interfaccia grafica ammessa: il front-end web di chat (step 8), con tecnologia concordata nella
  sua specifica. Niente framework non concordati.
- Servizi esterni (per esempio API pubbliche via HTTP) ammessi solo se concordati per uno
  strumento o uno step; nessuna credenziale nel codice o in Git.
- Persistenza su disco ammessa per i dati delle note (SQLite) e per chat e messaggi salvati dal
  back-end in un database (step 7, tecnologia concordata nella sua specifica). La cronologia
  della CLI resta solo in memoria.
- Lavorare solo dentro `Es.1/L4`. La repository contiene altre lezioni:
  non leggerle per copiarne il codice e non modificarle.

## Scelte tecniche
- Python, codice sincrono e moduli piccoli, con una separazione semplice tra
  grafo, collegamento al modello, strumenti e interfacce (CLI e, dagli step 6-8, API HTTP,
  back-end e front-end).
- LM Studio sull'host, raggiunto tramite la sua API compatibile con OpenAI.
- Indirizzo del server e identificativo del modello solo da variabili d'ambiente.
  L'identificativo è quello restituito dal server (`GET /v1/models`), mai inventato.
- Un file di configurazione di esempio senza credenziali; il file reale resta fuori da Git.
- Docker Compose per l'applicazione; LM Studio non va containerizzato.
- Dipendenze motivate, concordate e con versioni fissate.
- Comandi documentati anche per PowerShell (Windows).

## Struttura e comandi
- Pacchetto `assistente/`: `config.py` (variabili d'ambiente, `GIORNI_BASE_URL`,
  `CATALOGO_BASE_URL` e `NOTE_DB_PATH` obbligatorie, `AMBITO_PATH` e `MAX_REVISIONI` facoltative),
  `tools.py` (orologio, convertitore, calcolatrice), `dates.py` (strumenti delle date, client HTTP
  del servizio giorni), `catalog.py` (strumenti del catalogo, client HTTP del servizio catalogo),
  `mcp_client.py` (client MCP generico: strumenti da `list_tools`, una sessione stdio per
  chiamata), `notes.py` (strumenti delle note, parametri del sottoprocesso del server delle note),
  `units.py` (tabella delle unità e conversione), `arithmetic.py` (analisi e calcolo
  sicuro delle espressioni aritmetiche),
  `cities.py` (ricerca città → fuso su archivio locale), `graph.py` (stato, nodi `router`,
  `agente`, `strumenti`, `limite`, `rifiuto` e `revisore`, instradamento, pulizia della cronologia a
  fine turno, log dei messaggi al modello),
  `router.py` (prompt, contesto e lettura validata della decisione del router), `revisore.py`
  (prompt, schema e lettura validata della revisione), `contesto.py` (contesto recente condiviso da
  router e revisore), `model.py` (collegamento a LM Studio: modello dell'agente con gli strumenti e
  modelli del router e del revisore con schema JSON), `cli.py` (ciclo da
  terminale, cronologia, log), `__main__.py` (`python -m assistente`).
- `ambito.md`: descrizione dell'ambito dell'assistente usata dal router (versionata; percorso
  cambiabile con `AMBITO_PATH`).
- Servizio `servizio_giorni/` (FastAPI, indipendente da `assistente/`): `calendario.py`, `app.py`,
  `festivita.json` (festività nazionali 2020-2040). Avvio locale in un secondo terminale:
  `python -m uvicorn servizio_giorni.app:app --port 8000`.
- Servizio `servizio_catalogo/` (FastAPI, indipendente da `assistente/`): `inventario.py`, `app.py`,
  `inventario.json` (32 articoli inventati). Avvio locale in un terzo terminale:
  `python -m uvicorn servizio_catalogo.app:app --port 8001`.
- Server MCP `servizio_note/` (SDK `mcp`, indipendente da `assistente/`): `archivio.py` (SQLite),
  `server.py` (strumenti `add_note`, `list_notes`, `delete_note`). Non si avvia a mano: l'agente
  lo lancia come sottoprocesso stdio (`python -m servizio_note.server`).
- Registri in `docs/`: `registro-test.md` (esiti delle verifiche eseguite) e
  `registro-modifiche.md` (correzioni con causa, soluzione, ragionamento, commit e verifica).
- Docker: `Dockerfile` multi-stage (`app` predefinito, `test` per la suite) e `compose.yaml`
  (progetto `assistente-laboratorio`, servizi `assistente`, `giorni` (porta `127.0.0.1:8000`),
  `catalogo` (porta `127.0.0.1:8001`) e `test` con profilo `test`; volume `note` per l'archivio
  delle note, montato su `/app/dati` del servizio `assistente`).
- Test in `tests/`; `tests/fakes.py` contiene il modello finto `ScriptedModel`.
- Ambiente locale: `py -3.13 -m venv .venv`, poi `.\.venv\Scripts\Activate.ps1` e
  `python -m pip install -r requirements-dev.txt`.
- Test: `python -m pytest` (Python 3.13, venv locale) e
  `docker compose --profile test run --rm --build test` (Python 3.14). La suite deve passare su
  entrambe le versioni.
- Prove reali con LM Studio, con i servizi giorni e catalogo avviati: `$env:RUN_LMSTUDIO_TESTS = "1"; python -m pytest -m lmstudio -v`.

## Metodo: Superpowers
- Usare le skill di Superpowers per brainstorming, specifica, piano, implementazione e verifica.
- Non scrivere codice prima che io abbia approvato la specifica e poi il piano.
- Salvare specifica e piano in `Es.1/L4/docs/superpowers/` (`specs/` e `plans/`);
  ogni piano approvato va aggiunto anche a `Es.1/plan.md`.
- Procedere per incrementi piccoli, ciascuno verificato prima del commit.

## Test e verifiche
- Test automatici ripetibili che non richiedono un modello attivo (grafo, cronologia,
  instradamento, strumento con istante controllato).
- Prove reali con LM Studio e con Docker tenute separate e attivate esplicitamente.
- Una risposta simulata non dimostra che il modello locale sappia usare lo strumento.
- Nel resoconto indicare che cosa è stato eseguito, con quale esito, e che cosa resta da provare.

## Git
- Conventional Commits in italiano, per esempio `feat(grafo): ...`, `test(strumenti): ...`,
  `docs: ...`.
- Prima di ogni commit: `git status`, controllo del diff, staging selettivo dei soli file pertinenti.
- Mai versionare credenziali, `.env`, ambienti virtuali, cache o pesi dei modelli.
- Push soltanto su mia richiesta.
- Branch di lavoro: `dev`. Ogni nuova feature si sviluppa in un branch `feat/<nome-feature>`
  creato da `dev` e, a feature completata e verificata, riunito in `dev`.
- Merge su `main` solo con il mio permesso esplicito.
- Niente worktree se non richiesti.

## Documentazione
- Tenere aggiornato il README con configurazione, avvio, test e diagnosi, riportando solo
  comandi verificati.
- Aggiornare questo file quando cambiano convenzioni stabili (struttura, comandi di test,
  regole di lavoro), non per annotare l'avanzamento.
