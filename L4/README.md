# Assistente del laboratorio

Chat da terminale in Python che organizza il flusso in un grafo LangGraph esplicito e usa un
modello servito da LM Studio sull'host. La cronologia vale per la sessione e si perde all'uscita.
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
| `LMSTUDIO_BASE_URL` | sì | — | indirizzo dell'API di LM Studio, es. `http://localhost:1234/v1` |
| `LMSTUDIO_MODEL` | sì | — | identificativo del modello come restituito da `GET /v1/models` |
| `LOG_LEVEL` | no | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |

In LM Studio: carica il modello (es. `google/gemma-4-e2b`) e avvia il server locale (porta 1234).
Per vedere gli identificativi disponibili:

```powershell
Invoke-RestMethod http://localhost:1234/v1/models | Select-Object -ExpandProperty data | Select-Object id
```

## Avvio

```powershell
python -m assistente
```

All'avvio l'applicazione controlla che LM Studio risponda e che il modello configurato sia
disponibile; altrimenti termina con codice 1 e un messaggio che riporta l'indirizzo e i modelli
disponibili. Una variabile mancante o non valida fa terminare con codice 2.

Scrivi una domanda dopo `Tu>`. Per uscire: `esci`, `exit`, Ctrl+C oppure Ctrl+Z seguito da Invio
(Ctrl+D su Linux/macOS). Se il modello non risponde durante la sessione, la domanda viene scartata
e si può riprovare.

## Test

```powershell
python -m pytest
```

I test automatici non richiedono LM Studio: il modello è sostituito da uno stub. Le prove reali
risultano `skipped`.

### Prove reali con LM Studio

Con LM Studio attivo e `.env` configurato:

```powershell
$env:RUN_LMSTUDIO_TESTS = "1"; python -m pytest -m lmstudio -v; Remove-Item Env:RUN_LMSTUDIO_TESTS
```
