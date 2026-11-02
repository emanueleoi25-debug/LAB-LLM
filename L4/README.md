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
| `DEFAULT_TIMEZONE` | no | `Europe/Rome` | fuso dell'orologio quando il modello non indica una città (nome IANA) |
| `MAX_TOOL_STEPS` | no | `3` | giri modello→strumenti consentiti per ogni domanda (intero ≥ 1) |
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

## Strumento orologio, log e limite di passaggi

Il modello può chiedere lo strumento `get_current_time(city)`. `city` è il nome della città come
l'ha scritto l'utente (es. `Miami`, `Nuova York`, `Pechino`); il programma ne trova il fuso in un
archivio locale (`geonamescache`, città con almeno 5.000 abitanti, nessun accesso alla rete).
Maiuscole e spazi sono indifferenti, tra omonimi vince la città più popolosa e una parte dopo la
virgola viene ignorata se serve (`Miami, Florida`). È accettato anche un nome IANA (`Asia/Tokyo`).

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

## Docker Compose

L'immagine usa Python 3.14.9; LM Studio resta sull'host e il container lo raggiunge tramite
`host.docker.internal` (Compose sostituisce `LMSTUDIO_BASE_URL` del `.env`). Serve il file `.env`
(vedi Configurazione).

```powershell
docker compose build
docker compose run --rm assistente
```

`run` (non `up`) collega il terminale alla chat. L'immagine dell'applicazione contiene solo il
pacchetto `assistente` e le dipendenze: niente `.env`, test o `pytest`.

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

I test automatici non richiedono LM Studio: il modello è sostituito da uno stub. Le prove reali
risultano `skipped`.

### Prove reali con LM Studio

Con LM Studio attivo e `.env` configurato:

```powershell
$env:RUN_LMSTUDIO_TESTS = "1"; python -m pytest -m lmstudio -v; Remove-Item Env:RUN_LMSTUDIO_TESTS
```

## Verifica completa

1. Test automatici su 3.13 e 3.14: `python -m pytest` e
   `docker compose --profile test run --rm --build test` (tutti passed, le prove reali skipped).
2. Prove reali con LM Studio (comando sopra): risposta, memoria della sessione, uso dell'orologio.
3. In Docker, `docker compose run --rm assistente`:
   - «Che ore sono a Miami?» → su stderr compaiono `← modello [chiamata] get_current_time
     {'city': 'Miami'}` e un risultato con `America/New_York`; la risposta è coerente con l'ora
     reale di Miami;
   - «Quale città ti ho chiesto prima?» → la risposta cita Miami;
   - `esci`, nuovo avvio e di nuovo «Quale città ti ho chiesto prima?» → il modello non lo sa;
   - «Che ore sono?» → risultato con `fuso predefinito Europe/Rome`.

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
| `Errore: il modello non ha risposto…` durante la chat | LM Studio fermato o modello scaricato dalla memoria | ricarica il modello e ripeti la domanda: la cronologia è intatta |
| nessuna riga `strumento richiesto` nei log | `LOG_LEVEL` sopra `INFO`, oppure il modello ha risposto senza usare lo strumento | imposta `LOG_LEVEL=INFO`; riformula chiedendo l'ora attuale |
| `strumento richiesto: get_current_time {}` seguito da `fuso predefinito` per una domanda su una città | il modello non ha passato la città allo strumento | riformula citando esplicitamente la città, es. «Che ore sono a Miami?» |
| `risultato strumento: Errore: città sconosciuta '…'` | la città non è nell'archivio (meno di 5.000 abitanti o nome non riconosciuto) | usa il nome di una città vicina più grande, oppure un nome IANA come `America/New_York` |
| `← modello [chiamata non valida] …` e `Errore: argomenti non validi…` | il modello ha prodotto argomenti non interpretabili | nessuna azione: il modello riceve l'errore e può riprovare entro `MAX_TOOL_STEPS` giri; se si ripete, riformula la domanda |

Nel container i log riportano l'ora in UTC; le risposte dell'orologio usano invece il fuso richiesto.
