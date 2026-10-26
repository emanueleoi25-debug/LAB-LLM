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
- si avvia anche con Docker Compose.

## Confini
- Implementare solo i requisiti concordati. Altri strumenti, MCP, workflow e RAG arriveranno
  nelle lezioni successive: non anticiparli.
- Niente interfacce grafiche, servizi cloud o framework non concordati.
- Lavorare solo dentro `Es.1/L4`. La repository contiene altre lezioni:
  non leggerle per copiarne il codice e non modificarle.
- Lavorare nel branch corrente; nessun branch o worktree nuovo se non richiesto.

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
- Pacchetto `assistente/`: `config.py` (variabili d'ambiente), `tools.py` (orologio), `graph.py`
  (stato, nodi, instradamento), `model.py` (collegamento a LM Studio), `cli.py` (ciclo da
  terminale, cronologia, log), `__main__.py` (`python -m assistente`).
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

## Documentazione
- Tenere aggiornato il README con configurazione, avvio, test e diagnosi, riportando solo
  comandi verificati.
- Aggiornare questo file quando cambiano convenzioni stabili (struttura, comandi di test,
  regole di lavoro), non per annotare l'avanzamento.
