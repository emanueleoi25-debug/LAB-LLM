# Giorni e scadenze

Data: 2026-11-05. Branch: `feat/giorni-scadenze` (da `dev` = `0f93c09`). Terzo strumento della
roadmap in `CLAUDE.md`, primo servizio FastAPI. Estende le specifiche precedenti, in particolare
`2026-11-03-calcolatrice-sicura-design.md` (§8: frasi che chiedono di chiamare lo strumento anche
nei casi «impossibili»).

## 1. Obiettivo

Il modello può contare i giorni tra due date, aggiungere giorni di calendario o lavorativi a una
data e chiedere informazioni su una data (giorno della settimana, festività, lavorativo). La logica
sta in un servizio FastAPI separato, `servizio_giorni`, che legge le festività nazionali italiane da
un file locale; l'agente lo raggiunge via HTTP con quattro strumenti locali, client sottili che
convertono la risposta JSON in un testo per il modello.

### Criteri di successo

- Con LM Studio, `google/gemma-4-e2b` e il servizio avviato:
  - «Quanti giorni mancano a Natale?» → `days_between` con fine `12-25` (o la data completa
    corretta) e risposta con i giorni restituiti dal servizio;
  - «Che data sarà tra 30 giorni?» → `add_days` con `days` 30;
  - «Qual è la scadenza a 10 giorni lavorativi da oggi?» → `add_business_days` con `days` 10;
  - «Il 2 giugno 2027 è festivo?» → `date_info` con `2027-06-02` e risposta che cita la Festa
    della Repubblica;
  ciascuna in almeno 8 tentativi su 10 nella serie del §7.
- «Che giorno della settimana sarà il 30 febbraio?» produce il testo d'errore dello strumento, non
  una data inventata.
- Con il servizio spento la chat continua e lo strumento restituisce l'errore «non raggiungibile».
- La suite senza modello passa su Python 3.13 (venv) e 3.14 (container).
- Orologio, convertitore e calcolatrice continuano a funzionare come prima.

### Fuori ambito

Festività locali o di altri Paesi, ponti, orari e fusi nelle date (solo giorni interi), date in
linguaggio naturale nel servizio («domani», «lunedì prossimo»: le converte il modello), anni fuori
dai limiti del §3, calcolo di Pasqua nel codice del servizio, persistenza, autenticazione, controllo
del servizio all'avvio dell'agente, endpoint diversi da quelli del §3.

## 2. Gli strumenti visti dal modello

Quattro strumenti in `assistente/dates.py`. I parametri di data accettano `AAAA-MM-GG` oppure
`MM-GG` (§3.1); quelli facoltativi, se omessi, valgono oggi. «Oggi» è la data corrente nel fuso
predefinito (`DEFAULT_TIMEZONE`, di norma `Europe/Rome`), calcolata dallo strumento con un istante
controllabile nei test (come `utc_now` dell'orologio) e passata sempre al servizio nel parametro
`oggi`: il servizio non legge mai il proprio orologio.

| Strumento | Parametri | Endpoint |
|---|---|---|
| `days_between` | `end: str`, `start: str \| None = None` | `GET /giorni-tra` |
| `add_days` | `days: int`, `start: str \| None = None` | `GET /aggiungi-giorni` |
| `add_business_days` | `days: int`, `start: str \| None = None` | `GET /aggiungi-lavorativi` |
| `date_info` | `date: str \| None = None` | `GET /info-data` |

Descrizioni esatte:

- `days_between`: «Conta i giorni tra due date: giorni di calendario e giorni lavorativi in Italia
  (esclusi sabati, domeniche e festività nazionali). Parametri: end, la data di arrivo; start, la
  data di partenza (omettilo per partire da oggi). Date come AAAA-MM-GG; se l'utente non dice
  l'anno passa MM-GG (es. '12-25' per Natale) e si usa la prossima occorrenza. Se una data non è
  valida restituisce un errore che spiega il motivo: chiamalo comunque, non rispondere a mente.»
- `add_days`: «Calcola la data che si ottiene aggiungendo (o togliendo, con un numero negativo)
  giorni di calendario a una data. Parametri: days, il numero di giorni (es. 30, oppure -10 per
  '10 giorni fa'); start, la data di partenza come AAAA-MM-GG o MM-GG (omettilo per partire da
  oggi). Se i dati non sono validi restituisce un errore che spiega il motivo: chiamalo comunque,
  non rispondere a mente.»
- `add_business_days`: «Calcola una scadenza in giorni lavorativi in Italia (esclusi sabati,
  domeniche e festività nazionali): restituisce il giorno lavorativo che cade dopo days giorni
  lavorativi, senza contare la data di partenza. Parametri: days, il numero di giorni lavorativi
  (negativo per andare indietro); start, la data di partenza come AAAA-MM-GG o MM-GG (omettilo per
  partire da oggi). Se i dati non sono validi restituisce un errore che spiega il motivo: chiamalo
  comunque, non rispondere a mente.»
- `date_info`: «Dice che giorno della settimana è una data, se è una festività nazionale italiana
  (con il nome), se cade nel fine settimana e se è lavorativa. Parametro: date, come AAAA-MM-GG o
  MM-GG (omettilo per oggi). Se la data non è valida restituisce un errore che spiega il motivo:
  chiamalo comunque, non rispondere a mente.»

Frase esatta aggiunta in coda al prompt di sistema (preceduta da uno spazio): «Per contare giorni
tra date, calcolare scadenze in giorni di calendario o lavorativi e sapere se una data è festiva o
lavorativa usa gli strumenti days_between, add_days, add_business_days e date_info; se l'utente non
dice l'anno passa la data come MM-GG.»

### Testi di successo

Date come `AAAA-MM-GG (giorno)`, con il giorno della settimana in minuscolo (`lunedì` … `domenica`).
«giorno/giorni» al singolare solo quando il valore assoluto è 1.

- `days_between`:
  `Dal 2026-11-05 (giovedì) al 2026-12-25 (venerdì): 50 giorni di calendario, 34 giorni lavorativi (esclusa la partenza, inclusa la data di arrivo).`
  Con la data di arrivo precedente i numeri sono negativi (`-3 giorni di calendario, -2 giorni
  lavorativi …`). Se i giorni lavorativi non sono disponibili (§3.3):
  `Dal 2019-01-01 (martedì) al 2019-12-31 (martedì): 364 giorni di calendario; giorni lavorativi non disponibili fuori dagli anni 2020-2040.`
- `add_days`: `2026-11-05 (giovedì) + 30 giorni = 2026-12-05 (sabato)`; con days negativo
  `2026-11-05 (giovedì) - 10 giorni = 2026-10-26 (lunedì)`.
- `add_business_days`:
  `2026-11-27 (venerdì) + 10 giorni lavorativi = 2026-12-14 (lunedì); festività saltate: 2026-12-08 Immacolata Concezione.`
  Senza festività in mezzo: `…; nessuna festività saltata.` Più festività separate da `, `. I
  fine settimana non si elencano.
- `date_info`:
  - festività: `2027-06-02 (mercoledì): festività, Festa della Repubblica; non lavorativo.`
  - festività nel fine settimana: `2026-10-04 (domenica): festività, San Francesco d'Assisi; fine settimana; non lavorativo.`
  - fine settimana: `2026-11-07 (sabato): fine settimana; non lavorativo.`
  - lavorativo: `2026-11-05 (giovedì): giorno lavorativo.`
  - fuori dagli anni del file: `2019-06-02 (domenica): festività non disponibili fuori dagli anni 2020-2040.`

### Testi d'errore dello strumento

Ogni errore inizia con `Errore: `. Se il servizio risponde 400, il testo è `Errore: ` seguito dal
campo `detail` (§4). Inoltre:

- servizio non raggiungibile (connessione rifiutata, nome non risolto o tempo scaduto, timeout
  5 secondi): `Errore: servizio giorni non raggiungibile a <GIORNI_BASE_URL>.`
- qualsiasi altra risposta (codice diverso da 200 e 400, JSON non valido):
  `Errore: risposta non valida dal servizio giorni (HTTP <codice>).`

Lo strumento non solleva mai eccezioni verso il grafo.

## 3. Il servizio

Pacchetto `servizio_giorni/`, indipendente da `assistente/` (non lo importa). Avvio:
`python -m uvicorn servizio_giorni.app:app --port 8000` (in Docker `--host 0.0.0.0`).

### 3.1 Date

- Formati: `AAAA-MM-GG` (anno di 4 cifre) oppure `MM-GG`. Il parametro `oggi` solo `AAAA-MM-GG`.
- `MM-GG` vale la prossima occorrenza a partire da un riferimento, riferimento incluso: oggi per
  `inizio`, `data` e per `/info-data`; la data di partenza già risolta per `fine`. `02-29` vale il
  prossimo 29 febbraio esistente.
- Anni ammessi: 1900-2100, per le date ricevute, risolte e per i risultati.
- Festività e giorni lavorativi: solo per date negli anni del file (2020-2040).

### 3.2 Festività: `servizio_giorni/festivita.json`

```json
{
  "anni": [2020, 2040],
  "fisse": [{"giorno": "01-01", "nome": "Capodanno", "dal": 2020}, "..."],
  "mobili": {"2020": [{"data": "2020-04-12", "nome": "Pasqua"},
                      {"data": "2020-04-13", "nome": "Lunedì dell'Angelo"}], "...": []}
}
```

- Fisse (`dal` 2020 salvo indicazione): 01-01 Capodanno, 01-06 Epifania, 04-25 Festa della
  Liberazione, 05-01 Festa del Lavoro, 06-02 Festa della Repubblica, 08-15 Ferragosto, 10-04 San
  Francesco d'Assisi (`dal` 2026: legge 8 ottobre 2025 n. 151, in vigore dal 1° gennaio 2026),
  11-01 Ognissanti, 12-08 Immacolata Concezione, 12-25 Natale, 12-26 Santo Stefano.
- Mobili: Pasqua e Lunedì dell'Angelo per ogni anno 2020-2040, date scritte nel file (nessun
  calcolo nel servizio).
- Caricamento all'avvio con validazione: anni coerenti, ogni anno con le due mobili, date valide e
  nell'anno giusto, giorni `MM-GG` validi. Se il file non è valido il servizio non parte
  (eccezione con il motivo).
- Giorno lavorativo: dal lunedì al venerdì e non festività. Una festività di sabato o domenica non
  si recupera.

### 3.3 Endpoint

Tutti `GET`, risposta JSON. `oggi` è obbligatorio dove indicato.

| Endpoint | Parametri | Risposta 200 |
|---|---|---|
| `/giorni-tra` | `oggi`, `fine`, `inizio` (facoltativo, vale oggi) | `inizio`, `fine` (risolte), `giorno_inizio`, `giorno_fine`, `giorni`, `lavorativi` (intero o `null`) |
| `/aggiungi-giorni` | `oggi`, `giorni`, `data` (facoltativo) | `data`, `giorno_data`, `giorni`, `risultato`, `giorno_risultato` |
| `/aggiungi-lavorativi` | `oggi`, `giorni`, `data` (facoltativo) | `data`, `giorno_data`, `giorni`, `risultato`, `giorno_risultato`, `festivita_saltate` (lista di `{data, nome}`) |
| `/info-data` | `oggi`, `data` (facoltativo) | `data`, `giorno`, `festivita` (nome o `null`), `fine_settimana`, `lavorativo` (booleano o `null`) |
| `/salute` | — | `{"stato": "ok", "anni_festivita": [2020, 2040]}` |

Regole:

- `giorni` di `/giorni-tra`: `fine − inizio` in giorni, con segno.
- `lavorativi`: se `fine ≥ inizio`, giorni lavorativi `d` con `inizio < d ≤ fine`; altrimenti meno
  il numero di quelli con `fine < d ≤ inizio`. `null` se una delle due date è fuori dagli anni del
  file.
- `/aggiungi-giorni`: `giorni` intero tra -36500 e 36500.
- `/aggiungi-lavorativi`: `giorni` intero diverso da 0, tra -366 e 366; il risultato è l'N-esimo
  giorno lavorativo dopo `data` (prima, se negativo), `data` esclusa. Data di partenza e risultato
  devono stare negli anni del file. `festivita_saltate`: le festività che cadono in giorni dal
  lunedì al venerdì tra la partenza (esclusa) e il risultato, in ordine di data.
- `/info-data` fuori dagli anni del file: `festivita` e `lavorativo` `null`, `fine_settimana`
  calcolato.
- `giorno_*`: nome italiano del giorno della settimana, minuscolo.

## 4. Errori e limiti del servizio

Risposta 400 con `{"detail": "<testo>"}`; il testo non inizia con `Errore:` (lo aggiunge lo
strumento). Controlli nell'ordine dei parametri `oggi`, data di partenza, `fine`, `giorni`, poi
risultato:

- data non valida (formato o giorno inesistente): `data non valida '<valore>'. Usa AAAA-MM-GG o MM-GG.`
  (per `oggi`: `data non valida '<valore>'. Usa AAAA-MM-GG.`)
- anno fuori limiti (data ricevuta, risolta o risultato): `anno <anno> fuori intervallo: ammessi 1900-2100.`
- `giorni` di `/aggiungi-giorni` fuori limiti: `il numero di giorni deve essere compreso tra -36500 e 36500.`
- `giorni` di `/aggiungi-lavorativi` uguale a 0 o fuori limiti:
  `il numero di giorni lavorativi deve essere diverso da 0 e compreso tra -366 e 366.`
- giorni lavorativi fuori dagli anni del file (`/aggiungi-lavorativi`):
  `giorni lavorativi e festività disponibili solo per gli anni 2020-2040.`

Gli errori di validazione di FastAPI (parametro mancante o `giorni` non intero, 422) diventano 400
con `parametro '<nome>' mancante o non valido.` Nessun 500 per input dell'utente.

## 5. Struttura del codice

- `servizio_giorni/__init__.py`, `servizio_giorni/calendario.py`: caricamento e validazione delle
  festività (`load_holidays(path) -> Holidays`), `parse_date(text, reference) -> date`,
  `days_between`, `add_days`, `add_business_days`, `date_info`; solleva `DateError(message)` con i
  testi del §4. Nessuna dipendenza da FastAPI.
- `servizio_giorni/app.py`: app FastAPI, cinque endpoint, `DateError` → 400, 422 → 400; festività
  caricate una volta all'import.
- `servizio_giorni/festivita.json`: dati del §3.2.
- `assistente/dates.py`: `today(default_timezone, now) -> date`, client `httpx`, formattazione dei
  testi del §2, `make_date_tools(base_url, default_timezone, now_fn=utc_now) -> list[BaseTool]`
  (i quattro strumenti). Importa `utc_now` da `tools.py`.
- `assistente/config.py`: `Settings.giorni_base_url`, da `GIORNI_BASE_URL`, obbligatoria
  (`GIORNI_BASE_URL mancante`, raccolto con gli altri errori).
- `assistente/cli.py`: `make_tools` aggiunge i quattro strumenti dopo la calcolatrice; frase in
  coda al prompt (§2).
- `graph.py`, `model.py`, `units.py`, `arithmetic.py`, `cities.py` invariati.

## 6. Configurazione, dipendenze e Docker

- `requirements.txt`: `fastapi==0.159.1` (rilasciata il 2026-10-21), `uvicorn==0.54.0`
  (2026-09-25), `httpx==0.28.1` (2024-12-06, già installata come dipendenza di langchain-core:
  ora dichiarata perché la usiamo direttamente). 0.162.0 di fastapi esclusa perché uscita da meno
  di due settimane.
- `.env.example`: `GIORNI_BASE_URL=http://localhost:8000` con commento.
- `compose.yaml`: servizio `giorni` (build `app`, comando
  `python -m uvicorn servizio_giorni.app:app --host 0.0.0.0 --port 8000`, porta pubblicata solo
  su `127.0.0.1:8000`); `assistente` con `depends_on: [giorni]` e `GIORNI_BASE_URL:
  http://giorni:8000`.
- `Dockerfile`: gli stage `test` e `app` copiano anche `servizio_giorni/`.
- Avvio locale (PowerShell, due terminali con il venv attivo): `python -m uvicorn
  servizio_giorni.app:app --port 8000` e `python -m assistente`.

## 7. Test e verifiche

### Test automatici (senza modello e senza rete, scritti prima del codice)

- `tests/test_calendario.py`:
  - festività: file reale valido; Pasqua del file uguale a quella calcolata con l'algoritmo
    gregoriano anonimo (Meeus/Jones/Butcher, solo nel test) per 2020-2040, Lunedì dell'Angelo il
    giorno dopo; 4 ottobre lavorativo nel 2025 (sabato: non lavorativo ma non festività) e
    festività nel 2026 e 2027; file non valido (anno mancante, data fuori anno) → eccezione;
  - `parse_date`: `AAAA-MM-GG`, `MM-GG` oggi incluso e anno dopo, `02-29`, `2026-02-30`, `2026-2-3`,
    testo vuoto, anni 1899 e 2101;
  - `days_between`: esempio del §2 (50, 34), stessa data (0, 0), ordine inverso (negativi), fuori
    file (`lavorativi` `None`);
  - `add_days`: ±, limiti ±36500 e oltre, risultato oltre il 2100;
  - `add_business_days`: esempio del §2 con l'Immacolata, partenza di sabato, negativo, 0, ±366 e
    oltre, risultato oltre il 2040;
  - `date_info`: i cinque casi del §2.
- `tests/test_servizio.py` (`fastapi.testclient.TestClient`): ogni endpoint con un caso di
  successo, un 400 dal §4 e un 422 riportato a 400; `/salute`.
- `tests/test_dates.py` (`httpx.MockTransport`, istante controllato): parametri inviati (compreso
  `oggi` nel fuso predefinito, anche a cavallo della mezzanotte UTC), testi esatti del §2,
  singolare/plurale, 400 → `Errore: <detail>`, 500 → risposta non valida, connessione rifiutata e
  timeout → non raggiungibile; schema dei quattro strumenti (nomi, descrizioni esatte, parametri
  obbligatori).
- `tests/test_config.py`: `GIORNI_BASE_URL` mancante.
- `tests/test_cli.py`, `tests/test_graph.py`: `make_tools` con 7 strumenti in ordine; prompt che
  termina con la frase del §2; con `ScriptedModel` una chiamata a `date_info` arriva allo
  strumento e il `ToolMessage` contiene il testo prodotto (trasporto finto).

### Prove reali (separate, attivate esplicitamente)

- LM Studio, con il servizio avviato: nuovo test in `tests/integration/test_lmstudio.py`
  («Il 2 giugno 2027 è festivo?»: `ToolMessage` di `date_info` con `Festa della Repubblica`).
- Serie a mano, solo `google/gemma-4-e2b`, una sessione nuova per tentativo: 10 tentativi su
  ciascuna delle quattro domande del §1 e su «30 febbraio»; 2 tentativi per controllo («Che ore
  sono a Miami?», «Quanto fa 1234 * 5678?», «Converti 10 miglia in km», «Quanto fa 7 diviso 0?»,
  «Ciao, come stai?»). Criterio: almeno 8 su 10 con lo strumento atteso e argomenti corretti;
  controlli invariati. Chiamate scritte come testo = insuccesso; errori di LM Studio contati a
  parte. Un esito negativo si riporta, non si corregge senza accordo.
- Servizio spento: una domanda sulle date dà l'errore «non raggiungibile» e la chat continua.
- Docker: suite 3.14 (`docker compose --profile test run --rm --build test`), checklist con
  `docker compose run --rm assistente` (che avvia anche `giorni`), compresa una domanda sulle date.

## 8. Documentazione e commit

- README: servizio e quattro strumenti, avvio in due terminali e in Docker, file delle festività,
  esempi, diagnosi (servizio non raggiungibile, data non valida, anni fuori file), solo comandi
  verificati.
- `CLAUDE.md` (da discutere prima della modifica): `servizio_giorni/` e `dates.py` nella struttura,
  comando di avvio del servizio, `GIORNI_BASE_URL`.
- `docs/registro-test.md`: esiti delle verifiche.
- Commit su `feat/giorni-scadenze`: `docs:` per questa specifica, poi `feat(servizio):` per
  calendario e app con i test, `feat(strumenti):` per gli strumenti e la registrazione,
  `build:` per dipendenze e Docker, `docs:` per README e registri. A feature verificata si chiede
  l'ok prima del merge in `dev`; push solo su richiesta.
