# Assistente del laboratorio

Chat da terminale in Python che organizza il flusso in un grafo LangGraph esplicito.
Progetto del corso «Deep Learning e LLM: costruire chatbot e agenti» (lezione L4).

Stato attuale: il grafo risponde con un testo fisso; il collegamento a LM Studio arriva nel
prossimo incremento.

## Requisiti

- Python 3.13 per l'ambiente locale (in Docker si usa Python 3.14.9)
- Docker Desktop (per l'avvio con Docker Compose)
- LM Studio sull'host (per le risposte reali)

Tutti i comandi si eseguono dalla cartella `Es.1/L4`.

## Preparazione (PowerShell)

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

`requirements.txt` contiene le dipendenze dell'applicazione, `requirements-dev.txt` aggiunge
quelle per i test.

## Avvio

```powershell
python -m assistente
```

Scrivi una domanda dopo `Tu>`. Per uscire: `esci`, `exit`, Ctrl+C oppure Ctrl+Z seguito da Invio
(Ctrl+D su Linux/macOS).

## Test

```powershell
python -m pytest
```

I test automatici non richiedono LM Studio: il modello è sostituito da uno stub.
