# Assistente del laboratorio

Progetto del corso «Deep Learning e LLM: costruire chatbot e agenti».
La cartella del progetto è `Es.1/L4`; all'inizio contiene soltanto questo file.
Struttura, dipendenze e comandi verranno definiti con la specifica e il piano.

## Obiettivo
Un'applicazione da terminale in Python che conversa con un modello locale e:
- organizza il flusso in un grafo LangGraph esplicito (stato, nodi, instradamento riconoscibili);
- usa un modello servito da LM Studio, che resta sul computer host;
- conserva la cronologia della conversazione per la durata della sessione (nessuna persistenza);
- offre uno strumento orologio con fuso orario esplicito, richiesto dal modello tramite tool calling
  ed eseguito davvero dal programma;
- offrirà altri strumenti, sviluppati uno alla volta e in quest'ordine: convertitore di unità e
  calcolatrice sicura (locali, come l'orologio), giorni e scadenze e catalogo locale (servizi
  FastAPI), note persistenti e meteo (un server MCP ciascuno);
- si avvia anche con Docker Compose.

## Confini
- Implementare solo i requisiti concordati, uno strumento alla volta: non anticipare quelli
  successivi. Workflow e RAG arriveranno nelle lezioni successive.
- Niente interfacce grafiche o framework non concordati.
- Servizi esterni (per esempio API pubbliche via HTTP) ammessi solo se concordati per uno
  strumento; nessuna credenziale nel codice o in Git.
- Persistenza su disco ammessa solo per i dati dello strumento che la richiede (le note
  persistenti, su SQLite); la cronologia della conversazione resta solo in memoria.
- Lavorare solo dentro `Es.1/L4`. La repository contiene altre lezioni:
  non leggerle per copiarne il codice e non modificarle.

## Scelte tecniche
- Python, codice sincrono e moduli piccoli, con una separazione semplice tra
  grafo, collegamento al modello, strumenti e interfaccia da terminale.
- LM Studio sull'host, raggiunto tramite la sua API compatibile con OpenAI.
- Indirizzo del server e identificativo del modello solo da variabili d'ambiente.
  L'identificativo è quello restituito dal server (`GET /v1/models`), mai inventato.
- Un file di configurazione di esempio senza credenziali; il file reale resta fuori da Git.
- Docker Compose per l'applicazione; LM Studio non va containerizzato.
- Dipendenze motivate, concordate e con versioni fissate.
- Comandi documentati anche per PowerShell (Windows).

## Struttura e comandi
- Pacchetto `assistente/`: `config.py` (variabili d'ambiente), `tools.py` (orologio, convertitore),
  `units.py` (tabella delle unità e conversione),
  `cities.py` (ricerca città → fuso su archivio locale), `graph.py` (stato, nodi, instradamento,
  log dei messaggi al modello), `model.py` (collegamento a LM Studio), `cli.py` (ciclo da
  terminale, cronologia, log), `__main__.py` (`python -m assistente`).
- Registri in `docs/`: `registro-test.md` (esiti delle verifiche eseguite) e
  `registro-modifiche.md` (correzioni con causa, soluzione, ragionamento, commit e verifica).
- Docker: `Dockerfile` multi-stage (`app` predefinito, `test` per la suite) e `compose.yaml`
  (progetto `assistente-laboratorio`, servizi `assistente` e `test` con profilo `test`).
- Test in `tests/`; `tests/fakes.py` contiene il modello finto `ScriptedModel`.
- Ambiente locale: `py -3.13 -m venv .venv`, poi `.\.venv\Scripts\Activate.ps1` e
  `python -m pip install -r requirements-dev.txt`.
- Test: `python -m pytest` (Python 3.13, venv locale) e
  `docker compose --profile test run --rm --build test` (Python 3.14). La suite deve passare su
  entrambe le versioni.
- Prove reali con LM Studio: `$env:RUN_LMSTUDIO_TESTS = "1"; python -m pytest -m lmstudio -v`.

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
