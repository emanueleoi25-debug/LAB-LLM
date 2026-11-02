# Registro delle modifiche

Correzioni e cambi di comportamento dell'assistente, dalla più recente. Ogni voce spiega che cosa
non era giusto, perché, come è stato risolto, quali alternative sono state scartate, in quale commit
e come è stato verificato. Gli esiti completi delle verifiche sono in
[`registro-test.md`](registro-test.md).

## 2026-11-02 — I log non mostravano il dialogo con il modello

**Che cosa non era giusto.** A schermo comparivano solo `strumento richiesto` e
`risultato strumento`. Non si vedeva che cosa riceveva il modello né che cosa decideva: per capire
perché a Miami arrivava `get_current_time {}` bisognava ricostruirlo a mano.

**Causa.** Il nodo `modello` di `graph.py` chiamava il modello senza registrare né i messaggi in
ingresso né la risposta.

**Soluzione.** In `call_model`, a livello INFO sul logger `assistente.graph`:
- prima della chiamata, una riga per ogni messaggio nuovo dall'ultima risposta del modello:
  `→ modello [sistema]`, `→ modello [utente]`, `→ modello [strumento <nome>]`;
- dopo la chiamata, `← modello [chiamata] <nome> <argomenti>`,
  `← modello [chiamata non valida] <nome> <errore o argomenti>` e, se c'è testo,
  `← modello [risposta] <testo>`;
- gli a capo diventano `\n`, così ogni messaggio occupa una riga. Le righe di log esistenti restano
  invariate.

**Ragionamento.**
- Si registrano solo i messaggi nuovi, non l'intera cronologia a ogni chiamata. Il prompt di
  sistema compare una volta sola e il log resta leggibile anche in conversazioni lunghe.
- Il testo viene da `message.text`, quindi anche le risposte a blocchi diventano testo semplice.
- Per una chiamata non valida si registra l'errore, se c'è, altrimenti gli argomenti: lo stesso
  criterio del messaggio d'errore che il nodo `strumenti` rimanda al modello.
- Il livello INFO segue la configurazione esistente: con `LOG_LEVEL=WARNING` queste righe
  spariscono. La persistenza dei log su file è fuori ambito per la specifica.

**Commit.** `5df730f` — `feat(grafo): registra i messaggi scambiati con il modello`.

**Verifica.**
- TDD: 5 test nuovi in `tests/test_graph.py`, falliti prima dell'implementazione e superati dopo
  (`test_model_exchange_is_logged`, `test_system_prompt_logged_only_on_first_question`,
  `test_newlines_are_escaped_in_logs`, `test_invalid_call_is_logged`,
  `test_block_content_is_logged_as_text`).
- Suite senza modello: 78 superati e 3 skipped su Python 3.13 e 3.14.
- Prova manuale e checklist in Docker: con «Che ore sono a Miami?» le righe `→ modello` /
  `← modello` compaiono nell'ordine dell'esempio della specifica (sessione del 2026-11-02 in
  `registro-test.md`).

## 2026-11-02 — L'ora di una città richiedeva al modello di conoscere il fuso orario

**Che cosa non era giusto.** Con `google/gemma-4-e2b`, alla domanda «Che ore sono a Miami?»
l'assistente rispondeva spesso con l'ora di Roma, oppure diceva di non conoscere l'orario di
Miami. Nella serie di prova Miami era giusta 1 volta su 5. Bari era giusta solo perché ha lo stesso
fuso di Roma. Kyoto, Pechino e Nuova York andavano bene.

**Causa.** Lo strumento accettava solo un nome IANA (`timezone: "America/New_York"`) e lasciava
al modello la traduzione città → fuso. Il modello piccolo spesso non la faceva: nelle altre 4
prove su Miami chiamava `get_current_time {}`, e lo strumento ricadeva sul fuso predefinito
`Europe/Rome`.

**Soluzione.**
- `cities.py` (nuovo): `find_city(name)` cerca la città in un archivio locale di `geonamescache`
  (città con almeno 5.000 abitanti). Usa anche i nomi alternativi («Nuova York», «Pechino»); tra
  omonimi sceglie la più popolosa; se il nome contiene una virgola («Miami, Florida») riprova con
  la parte prima della virgola.
- `tools.py`: lo strumento diventa `get_current_time(city)`. L'ordine di risoluzione è:
  1. nessuna città → fuso predefinito;
  2. nome IANA → quel fuso;
  3. città trovata → il suo fuso;
  4. altrimenti → `Errore: città sconosciuta '…'`.

  Il risultato dichiara che cosa è stato usato, per esempio
  `2026-11-02T03:52:14-05:00 (Miami, US, fuso America/New_York)`.
- `cli.py`: il prompt di sistema chiede di passare il nome della città nel parametro `city`.
- `requirements.txt`: aggiunto `geonamescache==3.0.2`.

**Ragionamento.**
- Il modello deve solo ripetere il nome della città che l'utente ha scritto, un compito che un
  modello piccolo svolge in modo affidabile. La traduzione città → fuso la fa il programma, in
  modo deterministico e verificabile con i test.
- `geonamescache` è stata preferita a una geolocalizzazione via Internet perché è offline e ha
  licenza MIT. Il progetto esclude i servizi cloud e i test non devono dipendere dalla rete. Il
  costo è di circa 187 MB installati.
- Restano fuori ambito, per scelta della specifica, la scelta interattiva tra omonimi e il paese
  come parametro separato: la regola «vince la più popolosa» copre i casi comuni («Paris» →
  Francia, «Miami» → Florida).
- Il nome IANA resta accettato, così le domande con un fuso esplicito continuano a funzionare.
- Un vecchio argomento `timezone` non provoca un errore: viene ignorato e si usa il fuso
  predefinito, che il risultato dichiara.

**Commit.** `8cddce3` — `feat(strumenti): trova il fuso orario dal nome della città`.

**Verifica.**
- TDD: i nuovi test sono falliti prima dell'implementazione (15 falliti e un errore di raccolta
  per `cities.py` mancante).
- Il 2026-11-02, sullo stato del commit: suite senza modello con 73 superati e 3 skipped sia su
  Python 3.13 (venv) sia su Python 3.14 (container `test`).
- Prove reali con LM Studio e `google/gemma-4-e2b`: 3 su 3. `test_real_model_uses_clock_tool` ora
  chiede l'ora a Miami e verifica `America/New_York` nel risultato.
- «Che ore sono a Miami?» in 5 sessioni nuove: 5 chiamate su 5 con `{'city': 'Miami'}`, risultato
  con fuso `America/New_York` e risposte coerenti (03:52–03:53, UTC−5). Prima della modifica era
  1 su 5.

## 2026-10-26 — Chiamate allo strumento non valide che facevano perdere la sessione

**Che cosa non era giusto.** Quando il modello chiedeva lo strumento con argomenti non
interpretabili (per esempio un JSON troncato), la sessione non poteva proseguire: la cronologia
restava con una chiamata senza risposta e anche le domande successive fallivano.

**Causa.**
- `langchain-openai` mette queste chiamate in `AIMessage.invalid_tool_calls`, non in `tool_calls`.
- Il grafo guardava solo `tool_calls`, quindi non rispondeva con una `ToolMessage` a una chiamata
  non valida.
- Una chiamata senza risposta in cronologia fa rifiutare la richiesta successiva.
- Se l'errore nasceva durante la conversione della risposta, l'eccezione non era un
  `openai.APIError` e la CLI non la intercettava.

**Soluzione.**
- `graph.py`: `_pending_tool_calls` restituisce sia `tool_calls` sia `invalid_tool_calls`.
  Il nodo `strumenti` risponde a ogni chiamata non valida con la `ToolMessage`
  `Errore: argomenti non validi per <nome>: <errore>`. Anche il nodo `limite` chiude queste
  chiamate.
- `cli.py`: `run_chat` intercetta ogni altra eccezione durante una domanda e stampa
  `Errore: risposta del modello non valida (…). Domanda scartata, riprova.`. Scarta la domanda,
  lascia invariata la cronologia e registra lo stack trace a livello DEBUG.

**Ragionamento.**
- Si chiude la chiamata con un messaggio d'errore invece di toglierla dalla cronologia. Così la
  cronologia resta fedele a ciò che il modello ha prodotto, e il modello legge l'errore e può
  riprovare con argomenti corretti. Il tentativo conta nel limite di passaggi (`MAX_TOOL_STEPS`),
  quindi non può ripetersi all'infinito.
- La CLI intercetta anche errori generici, come seconda rete di sicurezza. Alcuni errori nascono
  in `langchain-openai` prima che il grafo possa intervenire. Per questi si è scelto lo stesso
  comportamento già usato per gli errori di rete (domanda scartata, sessione intatta) invece di
  chiudere il programma.
- Questo ragionamento è ricostruito dal diff e dai commenti del codice: la discussione originale
  non è stata conservata.

**Commit.** `302f4a8` — `fix(grafo): gestisce chiamate allo strumento non valide senza perdere la
sessione`.

**Verifica.**
- Test aggiunti nel commit: `test_invalid_tool_call_gets_error_reply`,
  `test_limit_closes_invalid_tool_calls` (`tests/test_graph.py`) e
  `test_unexpected_model_error_discards_question_and_continues` (`tests/test_cli.py`).
- Sessione del 2026-10-29 in `registro-test.md`, sul commit `302f4a8`: 57 superati e 3 skipped su
  Python 3.13 e 3.14, prove reali con LM Studio 3 su 3, checklist in Docker 3 su 3.
- Il 2026-11-02 i tre test sono stati rieseguiti nel venv (Python 3.13): 3 superati.

## 2026-10-26 — Versione di `openai` diversa tra venv e container

**Che cosa non era giusto.** Il venv locale e l'immagine Docker installavano versioni diverse
del pacchetto `openai`, quindi le due suite di test non provavano lo stesso codice.

**Causa.** `openai` non era in `requirements.txt`. Arrivava come dipendenza di
`langchain-openai==1.7.2`, che accetta un intervallo di versioni (`openai>=2.45.0,<4.0.0`), quindi ogni installazione
prendeva la versione disponibile in quel momento. Il codice però usa `openai` direttamente:
`openai.OpenAI(...).models.list()` in `model.py` e `openai.APIError` in `cli.py`.

**Soluzione.** Aggiunto `openai==3.38.0` a `requirements.txt`.

**Ragionamento.**
- Il codice importa `openai` direttamente, quindi va trattato come dipendenza diretta con versione
  fissata, come chiede la regola sulle dipendenze del progetto.
- Un file di lock o strumenti come `pip-tools` avrebbero fissato tutte le dipendenze transitive, ma
  sarebbero stati uno strumento nuovo da concordare. Per allineare i due ambienti bastava una riga.
- Questo ragionamento è ricostruito dal diff e dalle regole del progetto: la discussione originale
  non è stata conservata.

**Commit.** `1471fe2` — `fix(deps): fissa openai per allineare il venv locale e il container`.

**Verifica.**
- Sessione del 2026-10-29 in `registro-test.md`: su Python 3.13 (venv) e 3.14 (container) l'esito
  di ogni singolo test è identico.
- Il 2026-11-02 la versione è stata controllata in entrambi gli ambienti: `openai` 3.38.0 nel venv
  e 3.38.0 nel container `test` (Python 3.14.9).
