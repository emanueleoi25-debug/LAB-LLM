# Registro delle modifiche

Correzioni e cambi di comportamento dell'assistente, dalla più recente. Ogni voce spiega che cosa
non era giusto, perché, come è stato risolto, quali alternative sono state scartate, in quale commit
e come è stato verificato. Gli esiti completi delle verifiche sono in
[`registro-test.md`](registro-test.md).

## 2026-11-08 — Un id enorme mandava in crash il server delle note

**Che cosa non era giusto.** `delete_note` con un id come `10**30` faceva comparire il traceback
del server nel terminale della chat e il modello leggeva `Errore: server delle note non disponibile
(errore interno del server). …`, come se il server fosse guasto, mentre l'id semplicemente non
esiste.

**Causa.** L'SDK accetta interi di qualsiasi grandezza; `sqlite3` invece li rifiuta oltre i 64 bit
con segno con `OverflowError`. Il server intercettava solo `sqlite3.Error` e `OSError`, quindi l'SDK
trattava l'eccezione come un crash (messaggio generico, traceback su stderr).

**Soluzione (spec §9.1).** In `delete_note`, un id fuori da `-(2**63)`…`2**63 - 1` dà lo stesso
testo di un id inesistente, senza interrogare l'archivio (costanti `SQLITE_MIN_INT` e
`SQLITE_MAX_INT` in `servizio_note/server.py`).

**Ragionamento.** Trovato dalla revisione finale (minore; l'utente ha chiesto di correggerlo). Un id
che SQLite non può memorizzare non può esistere nell'archivio: «nessuna nota» è la risposta vera.
Scartato intercettare `OverflowError` intorno a `archivio.delete`: il controllo esplicito dice
perché e non nasconde altri errori.

**Commit.** `a3f90e0` — `fix(note): un id fuori dagli interi di SQLite è un id inesistente`.

**Verifica.** `test_delete_note_huge_id_is_unknown` (id `10**30`, `-(10**30)`, `2**63`), prima
fallito e poi superato; suite 527 passed, 8 skipped su 3.13.14; via stdio vero nessuna riga su
stderr.

## 2026-11-08 — Un 404 di un altro servizio sembrava un codice inesistente

**Che cosa non era giusto.** Con `CATALOGO_BASE_URL` che punta a un altro servizio FastAPI (il caso
più probabile: la porta 8000 del servizio giorni), `get_catalog_item` restituiva `Errore: Not Found
Usa search_catalog per trovare il codice.`: il modello poteva dire all'utente che l'articolo non
esiste, cioè un'affermazione falsa sull'inventario. `search_catalog` sullo stesso indirizzo dava
invece, correttamente, «risposta non valida (HTTP 404)».

**Causa.** `_call` trattava come errore dell'utente qualsiasi 404 con un `detail` testuale, e
FastAPI risponde `{"detail": "Not Found"}` a ogni percorso sconosciuto.

**Soluzione (spec §9.1).** Il 404 è un codice inesistente solo se `detail` inizia con
`nessun articolo con codice ` (costante `NOT_FOUND_PREFIX` in `assistente/catalog.py`, il testo del
servizio catalogo); ogni altro 404 diventa `Errore: risposta non valida dal servizio catalogo
(HTTP 404). Non è possibile consultare l'inventario: …`.

**Ragionamento.** Trovato dalla revisione finale del branch (unico problema «importante»).
Riconoscere il testo del servizio è la verifica più piccola che distingue i due casi; la riga di
Diagnosi del README su «risposta non valida» citava già un `CATALOGO_BASE_URL` sbagliato.

**Commit.** `7123f77` — `fix(catalogo): un 404 estraneo non è un codice inesistente`.

**Verifica.** Caso nuovo in `test_invalid_responses`, prima fallito e poi superato;
`test_user_errors` e `test_contract_unknown_code` invariati e verdi; suite 482 passed, 7 skipped
su 3.13.14 e 3.14.9.

## 2026-11-08 — Con il servizio giorni spento il modello rispondeva a mente

**Che cosa non era giusto.** Con il servizio giorni spento, alla domanda «Quanti giorni mancano a
Natale?» lo strumento restituiva `Errore: servizio giorni non raggiungibile a …`, ma il modello
rispondeva comunque con un numero di giorni: 8 risposte su 8 («47 giorni»). Il numero non veniva
dallo strumento e l'utente non aveva modo di accorgersene dalla risposta.

**Causa.** Il testo d'errore diceva solo che il servizio non rispondeva, e un modello piccolo
(`google/gemma-4-e2b`) lo trattava come un'informazione da aggirare: calcolava la data a mente
oppure con `calculate`.

**Soluzione (spec §10.1 e §10.1.1).**
- I testi dei guasti del servizio («non raggiungibile», «risposta non valida», con o senza codice
  HTTP) finiscono con `Non è possibile calcolare il risultato: dillo all'utente e non calcolarlo a
  mente.` (costante `SERVICE_FAILURE_HINT` in `assistente/dates.py`). Gli errori di validazione
  (risposta 400) non cambiano.
- In coda al prompt di sistema: «Se uno strumento risponde che il servizio giorni non è
  raggiungibile o che la sua risposta non è valida, di' all'utente che il calcolo non è disponibile
  e non dare risultati calcolati a mente o con altri strumenti.»

**Ragionamento.**
- Prima si è provato solo il testo d'errore, per non allungare il prompt: 0 su 5. La coda arrivava
  al modello (era nel messaggio dello strumento), ma veniva ignorata.
- La regola nel prompt, provata come spike senza toccare il codice, ha dato 7 su 10. Il criterio
  era 8 su 10: l'utente ha scelto di adottarla e accettare il risultato misurato.
- «o con altri strumenti» copre il caso in cui il modello aveva ripiegato su `calculate`.
- Scartata per ora: una risposta fissa decisa dal grafo quando uno strumento delle date restituisce
  un guasto (garantita, ma aggiunge un instradamento al grafo).

**Commit.** `664608e` — `fix(strumenti): i guasti del servizio giorni chiedono di non rispondere a
mente`.

**Verifica.** Testi attesi aggiornati in `test_unreachable`, `test_unexpected_response`,
`test_http_error_becomes_invalid_response` e test nuovo
`test_system_prompt_ends_with_service_failure_rule`, prima falliti e poi superati; suite 384
passed su 3.13 e 3.14; serie a servizio spento 7 su 10 senza numero; esecuzione reale con la chat
che continua.

## 2026-11-08 — Due secondi di attesa in più verso LM Studio (localhost)

**Che cosa non era giusto.** Con `LMSTUDIO_BASE_URL=http://localhost:1234/v1` ogni nuova
connessione a LM Studio costava circa 2 secondi in più: 2,04 s contro 0,01 s con `127.0.0.1`.

**Causa.** Come per il servizio giorni (2026-11-06), su Windows `localhost` si risolve prima in
`::1`, ma LM Studio ascolta solo su `127.0.0.1`: il tentativo rifiutato su `::1` costa circa 2
secondi prima di passare a IPv4.

**Soluzione (spec §10.2).** `LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1` in `.env.example`, nel
README (con la spiegazione) e nel `.env` locale. Codice e Docker (`host.docker.internal`) non
cambiano.

**Ragionamento.** Il client OpenAI riusa la connessione, quindi il ritardo pesa soprattutto
all'avvio (controllo del modello e prima domanda) e dopo le pause; cambiare l'indirizzo d'esempio
costa nulla. Scartato: far ascoltare LM Studio anche su IPv6 (impostazione dell'utente, non del
progetto).

**Commit.** `b677693` — `fix(config): indirizzo 127.0.0.1 per LM Studio`.

**Verifica.** Tempi misurati con httpx (3 richieste per indirizzo); prove reali con LM Studio 6
passed con il nuovo indirizzo; `Invoke-RestMethod http://127.0.0.1:1234/v1/models` elenca il
modello.

## 2026-11-08 — I log del container erano in UTC

**Che cosa non era giusto.** In Docker i timestamp dei log erano in UTC (un'ora indietro rispetto
a Roma), mentre nella venv locale sono nell'ora di Roma: confrontare i log era scomodo.

**Causa.** Il container non aveva `TZ`, quindi `logging` usava l'ora UTC del sistema.

**Soluzione (spec §10.2).** `TZ: Europe/Rome` nell'`environment` del servizio `assistente` in
`compose.yaml`. L'immagine `python:3.14.9-slim` contiene già i dati dei fusi
(`/usr/share/zoneinfo/Europe/Rome`).

**Ragionamento.** Valore fisso e non letto da `DEFAULT_TIMEZONE`: l'orologio usa già
`DEFAULT_TIMEZONE` e non dipende da `TZ`, che qui serve solo all'ora dei log. I servizi `giorni` e
`test` non cambiano.

**Commit.** `20797c6` — `build: fuso Europe/Rome per i log del container`.

**Verifica.** Suite 384 passed nel container `test`; «Che ore sono?» in Docker: timestamp dei log
17:03:04 tra le ore dell'host 17:02:54 e 17:03:11, risultato dello strumento ancora con `fuso
predefinito Europe/Rome`.

## 2026-11-03 — La calcolatrice trasformava il rumore dei float in un errore

**Che cosa non era giusto.** La revisione finale della calcolatrice ha trovato espressioni
corrette con un esito sbagliato:
- `0.1 + 0.2 - 0.3`, `1.1 - 1 - 0.1` e `3 * 0.1 - 0.3` → `Errore: il risultato è troppo piccolo…`;
- `100 * 1.1 - 110` → `0.000000000000014210854715202`.

Il risultato atteso è `0`. Sono conti realistici, per esempio con i prezzi.

**Causa.** In float `0.1 + 0.2` vale `0.30000000000000004`. Le cifre di rumore oltre la 15ª
sopravvivono alla sottrazione successiva. La regola 10 della specifica («troppo piccolo, anche se
intermedio») trasformava questo residuo in un errore. Il codice seguiva la specifica alla lettera:
il difetto era nella specifica.

**Soluzione (spec §7.2).** Dopo ogni `+` e `-` con almeno un operando non intero, il risultato si
arrotonda a 15 cifre significative dell'operando più grande:
`round(risultato, 14 - Decimal(m).adjusted())`.

**Ragionamento.**
- Le cifre oltre la 15ª dell'operando più grande non sono significative in un float, quindi
  toglierle elimina solo il rumore.
- Con due interi non si arrotonda: entro 1e15 la loro somma in float è esatta, e un arrotondamento
  a 15 cifre guasterebbe `1000000000000000 - 1`.
- L'esponente si prende da `Decimal`: `math.log10(999999999999999.5)` vale 15.0 per
  arrotondamento, e `999999999999999.5 - 0.5` sarebbe diventato 1e15.
- Scartate: togliere il controllo sugli intermedi (non elimina il rumore) e passare a `Decimal`
  per tutto il calcolo (cambia le regole di `%` e della potenza già concordate).

**Commit.** `f982b5a` — `fix(strumenti): la calcolatrice arrotonda il rumore dei float dopo somme e
sottrazioni`.

**Verifica.** `test_addition_noise_is_rounded` (7 casi) e due casi in `test_calculate_format`,
prima falliti e poi superati; suite 261 passed su 3.13 e 3.14; in Docker «Quanto fa 0.1 + 0.2 -
0.3?» → `0.1 + 0.2 - 0.3 = 0`.

## 2026-11-03 — Il modello leggeva «per» come divisione

**Che cosa non era giusto.** Con `google/gemma-4-e2b`, «Quanto fa 3,5 per 2?» produceva
`calculate("3.5 / 2")` in 5 tentativi su 5, e la risposta era 1,75 invece di 7.

**Causa.** «Per» è ambiguo: «3,5 per 2» è una moltiplicazione, «km per ora» una divisione. Il
modello piccolo sceglieva la seconda lettura. Lo strumento calcolava correttamente ciò che
riceveva, quindi l'errore nasceva nella traduzione della domanda.

**Soluzione (spec §7.1).** La descrizione dello strumento aggiunge: «Parole: 'per' e 'x' indicano
la moltiplicazione (3,5 per 2 → 3.5 * 2), 'diviso' la divisione.»

**Ragionamento.**
- La descrizione è il testo che il modello legge mentre scrive l'argomento. Lo stesso tipo di
  indicazione aveva già funzionato per la virgola decimale (7 su 7).
- Scartati: la stessa frase nel prompt di sistema (meno diretta, e il prompt parla già di tre
  strumenti) e un modello più grande (cambia il modello del progetto).

**Commit.** `14458b6` — `feat(strumenti): la descrizione della calcolatrice spiega «per» e
«diviso»`.

**Verifica.** `test_calculator_description_is_exact` aggiornato prima del codice. Prova reale:
«3,5 per 2» → `3.5 * 2` in 5 su 5 (6 su 6 con la serie completa); i controlli «diviso»,
«moltiplicato», «2 + 2», miglia → km e l'ora di Miami sono invariati. Nella stessa prova è
emerso che «7 diviso 0» riceve quasi sempre una risposta a mente, con la descrizione vecchia come
con la nuova: è registrato come punto da chiarire nel piano della calcolatrice.

## 2026-11-03 — Zeri iniziali, spaziature e simboli raddoppiati nella calcolatrice

**Che cosa non era giusto.** Problemi minori trovati dalla revisione finale:
- `05 + 3` → «espressione non valida», mentre `00.5 + 1` era accettato;
- una tabulazione o uno spazio non separabile → `carattere non ammesso` con un carattere
  invisibile nel messaggio;
- `6::4` → `1` (divisione intera) e `6*·4` → `1296` (potenza): due simboli alternativi di
  seguito si fondevano in un altro operatore.

**Causa.** Il parser di Python rifiuta gli interi con zeri iniziali; il controllo dei caratteri
ammetteva solo lo spazio normale; i simboli alternativi venivano sostituiti senza separatori.

**Soluzione (spec §7.3-7.5).**
- Gli zeri iniziali della parte intera si tolgono prima dell'analisi (`05` → `5`); quelli dopo il
  punto restano.
- Ogni carattere di spaziatura vale come spazio.
- Un carattere non stampabile nel messaggio d'errore si scrive come codice (`'U+200B'`).
- Ogni simbolo alternativo si sostituisce circondato da spazi, così `6::4` diventa `6 /  / 4` e
  dà «espressione non valida». `//` e `**` scritti in ASCII sono invariati.

**Commit.** `8c20ace` — `fix(strumenti): zeri iniziali, spaziature e simboli raddoppiati nella
calcolatrice`.

**Verifica.** `test_leading_zeros_and_whitespace`, `test_doubled_symbols_and_nbsp_are_syntax_errors`,
`test_invisible_character_is_shown_as_code_point` e `test_leading_zeros_keep_received_expression`,
prima falliti e poi superati; suite 261 passed su 3.13 e 3.14.

## 2026-11-02 — Il nome alternativo di una città più grande copriva il nome di un'altra città

**Che cosa non era giusto.** La revisione finale ha trovato città note risolte nel posto
sbagliato, con il fuso sbagliato:
- «Zaragoza» → Tijuana (Messico), 9 ore di differenza;
- «Islamabad» → Chattogram (Bangladesh);
- «Cancun» senza accento → Changchun (Cina).

Tra le città con almeno 200.000 abitanti, 110 cercate con il loro nome ufficiale risultavano
un'altra città.

**Causa.** `find_city` metteva nomi ufficiali e nomi alternativi in un unico indice, e a parità di
nome vinceva la città più popolosa. Una città grande con molti nomi alternativi copriva così il
nome ufficiale di una città più piccola. Era un caso diverso da quello degli omonimi descritto
nella specifica.

**Soluzione.**
- `cities.py` tiene due indici: nomi ufficiali, anche senza accenti, e nomi alternativi.
- Il nome ufficiale prevale, salvo che la città trovata con il nome alternativo sia almeno 10
  volte più popolosa (`ALTERNATE_NAME_FACTOR`).
- Tra città con lo stesso nome nello stesso indice vince ancora la più popolosa.

**Ragionamento.**
- Dare sempre la precedenza al nome ufficiale non basta. La revisione ha simulato questa regola:
  rompe i nomi italiani, il caso principale dello strumento («Roma» → Roma in Lesotho, «Mexico» →
  Mexico nelle Filippine).
- La soglia separa bene i due casi: Rome è circa 100 volte più popolosa di Roma (Lesotho), mentre
  Tijuana è solo circa 2 volte Zaragoza.
- Senza accenti viene indicizzato solo il nome ufficiale, così «Cancun» trova Cancún senza
  aggiungere altre coincidenze tra i nomi alternativi.
- Restano casi limite. Con la stessa misura sulle città ≥ 200.000 abitanti, 8 sono ancora
  risolte in un'altra città e 5 hanno un fuso diverso (per esempio «Abadan» → Ibadan, «St.
  Petersburg» → San Pietroburgo in Russia). Il risultato dello strumento dichiara sempre quale
  città ha usato.

**Commit.** `220f277` — `fix(strumenti): il nome principale di una città prevale sui nomi
alternativi di altre`.

**Verifica.**
- TDD: `test_main_name_beats_alternate_name_of_bigger_city` (Zaragoza, Islamabad, Cancun) fallito
  prima della correzione e superato dopo. `test_much_bigger_city_wins_with_alternate_name` (Roma,
  Mexico) è verde prima e dopo.
- Suite senza modello: 83 superati e 3 skipped su Python 3.13 e 3.14.
- Prove reali, checklist e serie di città: sessione del 2026-11-02 (commit `220f277`) in
  `registro-test.md`.

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
  omonimi sceglie la più popolosa (regola poi precisata in `220f277`, voce sopra); se il nome contiene una virgola («Miami, Florida») riprova con
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
