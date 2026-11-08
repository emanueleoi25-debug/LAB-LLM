# Catalogo locale

Data: 2026-11-08, approvata dall'utente il 2026-11-08. Branch: `feat/catalogo-locale` (da `dev` = `3800b10`). Quarto strumento
della roadmap in `CLAUDE.md`, secondo servizio FastAPI. Ricalca la struttura di
`2026-11-05-giorni-scadenze-design.md` (servizio separato, client sottili nell'agente, testi d'errore
che chiedono di non rispondere a mente, §10.1).

## 1. Obiettivo

Il modello può cercare attrezzatura e materiale nell'inventario del laboratorio e leggere la scheda
di un articolo: se c'è, dove si trova, quanti pezzi ci sono, in che stato è. La logica sta in un
servizio FastAPI separato, `servizio_catalogo`, che legge l'inventario da un file JSON locale;
l'agente lo raggiunge via HTTP con due strumenti locali, client sottili che convertono la risposta
JSON in un testo per il modello.

L'inventario è inventato: il modello non può conoscerne posizioni e quantità, quindi una risposta
corretta dimostra che ha chiamato lo strumento.

### Criteri di successo

- Con LM Studio, `google/gemma-4-e2b` e i servizi giorni e catalogo avviati, in almeno 8 tentativi
  su 10 per ciascuna domanda (serie del §7):
  1. «Dove trovo il multimetro?» → `search_catalog` e risposta con «Armadio A, ripiano 1»;
  2. «Quanti Arduino Uno ci sono?» → `search_catalog` e risposta con 12;
  3. «Fammi vedere la scheda di LAB-002» → `get_catalog_item` con `LAB-002` e risposta che cita la
     prenotazione con il tecnico di laboratorio;
  4. «Avete una stampante 3D?» → `search_catalog` e risposta che dice che non c'è, senza articoli,
     posizioni o quantità inventati.
- Con il servizio catalogo spento la chat continua e lo strumento restituisce il testo «non
  raggiungibile» del §2.4; l'esito delle risposte del modello viene misurato e riportato (§7).
- La suite senza modello passa su Python 3.13 (venv) e 3.14 (container).
- Orologio, convertitore, calcolatrice e strumenti delle date continuano a funzionare: i loro test
  passano senza modifiche.

### Fuori ambito

Modifica dell'inventario via API (prestiti, carico e scarico), persistenza di modifiche, ricerca
nella descrizione o nelle note, tolleranza ai refusi, paginazione oltre i 10 risultati, strumento
per elencare le categorie, autenticazione, controllo del servizio all'avvio dell'agente,
rifattorizzazione del client delle date (`assistente/dates.py`).

## 2. Gli strumenti visti dal modello

Due strumenti in `assistente/catalog.py`.

| Strumento | Parametri | Endpoint |
|---|---|---|
| `search_catalog` | `query: str`, `category: str \| None = None` | `GET /cerca?q=…&categoria=…` |
| `get_catalog_item` | `code: str` | `GET /articolo?codice=…` |

Il codice dell'articolo viaggia come parametro di query, non nel percorso: niente problemi di
codifica con caratteri come `/` o spazi.

### 2.1 Descrizioni esatte

- `search_catalog`: «Cerca attrezzatura e materiale nell'inventario del laboratorio e restituisce
  codice, nome, posizione, quantità e stato degli articoli trovati. Parametri: query, 1-3 parole
  chiave in italiano (es. 'multimetro', 'cavo usb'); category, facoltativo, una categoria
  dell'inventario. Usalo per sapere se un articolo c'è, dove si trova e quanti pezzi ci sono: non
  rispondere a mente.»
- `get_catalog_item`: «Restituisce la scheda completa di un articolo dell'inventario (descrizione,
  posizione, quantità, stato, note) dato il suo codice, es. 'LAB-012'. Se non conosci il codice usa
  prima search_catalog.»

### 2.2 Frase nel prompt di sistema

Aggiunta in coda a `SYSTEM_PROMPT` (`cli.py`), senza modificare le frasi esistenti:

> «Per sapere se un articolo del laboratorio c'è, dove si trova, quanti pezzi ci sono o in che stato
> è usa search_catalog e, per la scheda completa, get_catalog_item; non inventare articoli,
> posizioni o quantità. Se il servizio catalogo non è raggiungibile o la sua risposta non è valida,
> di' all'utente che l'inventario non è consultabile.»

La seconda frase applica da subito la lezione dello strumento 3 (§10.1.1: testo dello strumento più
regola nel prompt).

### 2.3 Testi di successo

Ricerca (al massimo 10 righe, nell'ordine del servizio):

```
Trovati 2 articoli per «oscilloscopio»:
- LAB-002 Oscilloscopio a 2 canali: Armadio A, ripiano 2; 2 pezzi; disponibile
- LAB-024 Sonde per oscilloscopio: Armadio A, ripiano 2; 4 pezzi; disponibile
```

- Con un solo risultato: «Trovato 1 articolo per «…»:».
- Con la categoria: «Trovati 2 articoli per «…» nella categoria Misura:» (nome della categoria come
  nel file).
- Se il totale supera le righe mostrate, riga finale: «Altri N articoli non mostrati: restringi la
  ricerca.» (`N` = totale − 10; «Altro 1 articolo non mostrato: restringi la ricerca.» se N = 1).
- Quantità: «1 pezzo», altrimenti «N pezzi» (anche «0 pezzi»).
- Fra «» c'è la query come restituita dal servizio (ripulita dagli spazi iniziali e finali).

Nessun risultato (risposta 200 con lista vuota, non è un errore):

```
Nessun articolo trovato per «stampante 3d»: dillo all'utente e non inventare articoli.
```

Con la categoria: «Nessun articolo trovato per «…» nella categoria Misura: dillo all'utente e non
inventare articoli.»

Scheda:

```
LAB-002 Oscilloscopio a 2 canali (Misura)
Posizione: Armadio A, ripiano 2
Quantità: 2 pezzi
Stato: disponibile
Descrizione: Oscilloscopio digitale da 100 MHz con due canali.
Note: Prenotare con il tecnico di laboratorio.
```

La riga «Note» è omessa se le note sono vuote.

### 2.4 Testi d'errore dello strumento

Iniziano tutti con `Errore: `. Lo strumento non solleva mai eccezioni verso il grafo.

| Caso | Risposta del servizio | Testo |
|---|---|---|
| Query senza parole utili | 400 | «Errore: la ricerca non contiene parole utili (servono parole di almeno 3 lettere).» |
| Categoria inesistente | 400 | «Errore: categoria 'X' inesistente. Categorie valide: Misura, Alimentazione, Saldatura, Microcontrollori, Componenti, Cavi e connettori, Utensili, Sicurezza.» |
| Parametro mancante o non valido | 400 | «Errore: parametro 'q' mancante o non valido.» |
| Codice inesistente | 404 | «Errore: nessun articolo con codice 'X'. Usa search_catalog per trovare il codice.» |
| Servizio irraggiungibile | — | «Errore: servizio catalogo non raggiungibile a {base_url}. {CATALOG_FAILURE_HINT}» |
| Risposta non valida con codice HTTP | altro codice, JSON non valido o campi mancanti | «Errore: risposta non valida dal servizio catalogo (HTTP {codice}). {CATALOG_FAILURE_HINT}» |
| Errore httpx non di trasporto | — | «Errore: risposta non valida dal servizio catalogo. {CATALOG_FAILURE_HINT}» |

- Per 400 con `detail` testuale il testo è «Errore: » + `detail`. Il 404 con `detail` testuale è un
  errore dell'utente solo per `get_catalog_item`: lo strumento aggiunge « Usa search_catalog per
  trovare il codice.» (il servizio non conosce i nomi degli strumenti dell'agente); per
  `search_catalog` un 404 è una risposta non valida.
- `CATALOG_FAILURE_HINT` = «Non è possibile consultare l'inventario: dillo all'utente e non
  rispondere a mente.» È una costante propria di `catalog.py`: la `SERVICE_FAILURE_HINT` delle date
  parla di «calcolare» e non si adatta.

## 3. Il servizio

Pacchetto `servizio_catalogo/`, indipendente da `assistente/`.

### 3.1 File `servizio_catalogo/inventario.json`

Una lista JSON di oggetti, uno per articolo, con esattamente questi campi:

| Campo | Tipo | Regola |
|---|---|---|
| `codice` | str | `LAB-` seguito da 3 cifre (`^LAB-\d{3}$`), unico |
| `nome` | str | non vuoto |
| `categoria` | str | non vuota |
| `parole_chiave` | list[str] | stringhe non vuote; la lista può essere vuota |
| `descrizione` | str | non vuota |
| `posizione` | str | non vuota |
| `quantita` | int | ≥ 0; un booleano non è valido |
| `stato` | str | `disponibile`, `in manutenzione` o `esaurito` |
| `note` | str | può essere vuota |

Regola di coerenza: `stato` è `esaurito` se e solo se `quantita` è 0. Il file deve contenere almeno
un articolo. Campi mancanti o in più, tipi sbagliati o regole violate fanno fallire il caricamento
con un messaggio che indica l'articolo (codice o posizione nella lista) e il campo: il servizio non
parte. Le categorie valide sono quelle presenti nel file, nell'ordine della prima apparizione.

### 3.2 Contenuto

32 articoli, 4 per ciascuna delle 8 categorie. «—» = lista o note vuote.

| Codice | Nome | Categoria | Parole chiave | Descrizione | Posizione | Q.tà | Stato | Note |
|---|---|---|---|---|---|---|---|---|
| LAB-001 | Multimetro digitale | Misura | tester | Misura tensione, corrente e resistenza con scala automatica. | Armadio A, ripiano 1 | 6 | disponibile | — |
| LAB-002 | Oscilloscopio a 2 canali | Misura | scope | Oscilloscopio digitale da 100 MHz con due canali. | Armadio A, ripiano 2 | 2 | disponibile | Prenotare con il tecnico di laboratorio. |
| LAB-003 | Pinza amperometrica | Misura | — | Misura la corrente alternata senza interrompere il circuito. | Armadio A, ripiano 1 | 1 | in manutenzione | Display da sostituire. |
| LAB-004 | Analizzatore di stati logici | Misura | logic analyzer | Analizzatore USB a 8 canali per segnali digitali. | Armadio A, ripiano 3 | 1 | disponibile | — |
| LAB-005 | Alimentatore da banco 0-30 V | Alimentazione | alimentatore | Alimentatore regolabile da 0 a 30 V e da 0 a 5 A. | Armadio B, ripiano 1 | 4 | disponibile | — |
| LAB-006 | Batterie AA ricaricabili | Alimentazione | pile, stilo | Batterie NiMH da 2000 mAh. | Armadio B, ripiano 2 | 24 | disponibile | Rimettere in carica dopo l'uso. |
| LAB-007 | Caricabatterie AA/AAA | Alimentazione | caricatore | Carica fino a quattro batterie AA o AAA. | Armadio B, ripiano 2 | 3 | disponibile | — |
| LAB-008 | Power bank USB | Alimentazione | batteria esterna | Batteria esterna da 10000 mAh con uscita USB-C. | Armadio B, ripiano 2 | 5 | disponibile | — |
| LAB-009 | Stazione saldante | Saldatura | saldatore | Stazione con temperatura regolabile da 200 a 450 °C. | Banco 2 | 3 | disponibile | Spegnere a fine lavoro. |
| LAB-010 | Filo di stagno 0,8 mm | Saldatura | stagno | Bobina da 100 g di lega senza piombo. | Armadio C, ripiano 1 | 5 | disponibile | — |
| LAB-011 | Pompetta dissaldante | Saldatura | dissaldatore | Pompa a molla per rimuovere lo stagno. | Armadio C, ripiano 1 | 4 | disponibile | — |
| LAB-012 | Aspiratore fumi di saldatura | Saldatura | — | Aspiratore da banco con filtro a carboni attivi. | Banco 2 | 1 | in manutenzione | Filtro in sostituzione. |
| LAB-013 | Arduino Uno | Microcontrollori | — | Scheda con ATmega328P per prototipi. | Cassettiera D, cassetto 1 | 12 | disponibile | — |
| LAB-014 | Raspberry Pi 5 | Microcontrollori | — | Computer a scheda singola con 8 GB di RAM. | Cassettiera D, cassetto 2 | 4 | disponibile | Solo per i progetti d'esame. |
| LAB-015 | ESP32 DevKit | Microcontrollori | wifi, bluetooth | Scheda con Wi-Fi e Bluetooth integrati. | Cassettiera D, cassetto 1 | 8 | disponibile | — |
| LAB-016 | Raspberry Pi Pico | Microcontrollori | — | Microcontrollore RP2040 a basso costo. | Cassettiera D, cassetto 2 | 0 | esaurito | Riordino richiesto. |
| LAB-017 | Kit resistenze assortite | Componenti | resistori | 600 resistenze da 10 Ω a 1 MΩ. | Cassettiera E, cassetto 1 | 10 | disponibile | — |
| LAB-018 | Kit condensatori assortiti | Componenti | — | Condensatori ceramici ed elettrolitici. | Cassettiera E, cassetto 1 | 6 | disponibile | — |
| LAB-019 | LED 5 mm assortiti | Componenti | diodi luminosi | LED rossi, verdi, gialli e blu. | Cassettiera E, cassetto 2 | 200 | disponibile | — |
| LAB-020 | Breadboard 830 punti | Componenti | basetta sperimentale | Basetta senza saldature per montaggi di prova. | Cassettiera E, cassetto 3 | 15 | disponibile | — |
| LAB-021 | Cavi jumper maschio-maschio | Cavi e connettori | ponticelli | Confezione da 40 cavetti per breadboard. | Armadio B, ripiano 3 | 20 | disponibile | — |
| LAB-022 | Cavo USB-C | Cavi e connettori | — | Cavo USB-C da 1 m per dati e ricarica. | Armadio B, ripiano 3 | 10 | disponibile | — |
| LAB-023 | Cavo HDMI | Cavi e connettori | — | Cavo HDMI da 2 m. | Armadio B, ripiano 3 | 0 | esaurito | — |
| LAB-024 | Sonde per oscilloscopio | Cavi e connettori | puntali | Sonde 1x/10x da 100 MHz. | Armadio A, ripiano 2 | 4 | disponibile | — |
| LAB-025 | Set di cacciaviti di precisione | Utensili | giraviti | 24 punte intercambiabili con impugnatura. | Armadio C, ripiano 2 | 5 | disponibile | — |
| LAB-026 | Pinza spelafili | Utensili | spellafili | Spela fili da 0,2 a 6 mm². | Armadio C, ripiano 2 | 4 | disponibile | — |
| LAB-027 | Tronchesino | Utensili | tronchese | Tronchese a taglio laterale per reofori. | Armadio C, ripiano 2 | 6 | disponibile | — |
| LAB-028 | Pistola per colla a caldo | Utensili | colla | Pistola per stick da 11 mm. | Armadio C, ripiano 2 | 2 | disponibile | Usare sul tappetino di silicone. |
| LAB-029 | Occhiali protettivi | Sicurezza | — | Occhiali in policarbonato con protezione laterale. | Armadio sicurezza | 15 | disponibile | — |
| LAB-030 | Braccialetto antistatico | Sicurezza | esd | Braccialetto con cavo di messa a terra. | Armadio sicurezza | 8 | disponibile | — |
| LAB-031 | Estintore a CO2 | Sicurezza | — | Estintore da 2 kg per apparecchi elettrici. | Ingresso | 2 | disponibile | Controllo semestrale a cura della manutenzione. |
| LAB-032 | Cassetta di pronto soccorso | Sicurezza | primo soccorso | Cassetta di medicazione per luoghi di lavoro. | Ingresso | 1 | disponibile | — |

Nel JSON le parole chiave sono liste (`"pile, stilo"` → `["pile", "stilo"]`). Nessuna stampante 3D,
di proposito (criterio 4).

### 3.3 Ricerca

1. **Normalizzazione** di un testo: minuscole; forma Unicode NFD e rimozione dei segni diacritici
   (categoria `Mn`), quindi «è» → «e»; ogni carattere diverso da `a-z` e `0-9` diventa uno spazio;
   suddivisione sugli spazi.
2. **Parole della query**: le parole normalizzate con almeno 3 caratteri che non sono parole vuote.
   Parole vuote (confrontate dopo la normalizzazione): `che chi con cui dal dai dei del della delle
   dello degli dove per tra fra una uno gli sul nel quale quali quanti quante quanto avete sono`.
   Se non resta nessuna parola: errore 400 (§2.4). La lista è fissa nel codice.
3. **Radice** di una parola: si tolgono le vocali finali (`a e i o u`) finché la parola è più lunga
   di 3 caratteri. «resistenze» e «resistenza» → `resistenz`; «oscilloscopio» e «oscilloscopi» →
   `oscilloscop`; «cavo» e «cavi» → `cav`; «led» resta `led`.
4. **Testo di un articolo**: le radici di tutte le parole normalizzate di nome, categoria e parole
   chiave (senza filtro su lunghezza e parole vuote). Descrizione e note non partecipano.
5. **Punteggio**: numero di radici distinte della query presenti fra le radici dell'articolo
   (uguaglianza esatta). Sono risultati gli articoli con punteggio > 0, ordinati per punteggio
   decrescente e, a parità, per codice crescente.
6. **Categoria** (facoltativa): confronto fra testi normalizzati e ricomposti (parole unite da uno
   spazio), quindi «cavi e connettori», «MISURA» e « Misura » vanno bene. Se non corrisponde a
   nessuna categoria: errore 400 con l'elenco delle categorie valide. Il filtro si applica prima del
   punteggio.
7. **Limite**: il servizio restituisce i primi 10 risultati e il `totale` di tutti i risultati.

### 3.4 Dettaglio

Il codice ricevuto viene ripulito dagli spazi iniziali e finali e portato in maiuscolo; poi deve
coincidere con un codice del file. Nessun'altra interpretazione: `LAB-12` e `12` sono codici
inesistenti (404, con il codice ripulito nel messaggio).

### 3.5 Endpoint

| Endpoint | Risposta 200 |
|---|---|
| `GET /cerca?q=…&categoria=…` | `{"query": str, "categoria": str \| null, "totale": int, "articoli": [{"codice", "nome", "posizione", "quantita", "stato"}]}` |
| `GET /articolo?codice=…` | `{"codice", "nome", "categoria", "parole_chiave", "descrizione", "posizione", "quantita", "stato", "note"}` |
| `GET /salute` | `{"stato": "ok", "articoli": 32}` |

- `query` è la query ripulita dagli spazi iniziali e finali; `categoria` è il nome della categoria
  come nel file (o `null` se non richiesta).
- `detail` dei 400 e del 404 (testi senza «Errore: »):
  - «la ricerca non contiene parole utili (servono parole di almeno 3 lettere).»
  - «categoria 'X' inesistente. Categorie valide: A, B, ….» (`X` come ricevuta, ripulita dagli
    spazi);
  - «parametro 'NOME' mancante o non valido.» (errori di validazione FastAPI, come in
    `servizio_giorni`);
  - «nessun articolo con codice 'X'.» (404).

## 4. Struttura del codice

| File | Contenuto |
|---|---|
| `servizio_catalogo/__init__.py` | vuoto |
| `servizio_catalogo/inventario.py` | `Item` (`dataclass(frozen=True)`), `CatalogError`, `InventoryError`, `load_items(path=None)`, `categories(items)`, `normalize(text)`, `stem(word)`, `query_stems(query)`, `search(items, query, category=None) -> SearchResult`, `find(items, code) -> Item \| None`. Nessuna dipendenza da FastAPI. |
| `servizio_catalogo/app.py` | `ITEMS = inventario.load_items()` all'import; gestori di `CatalogError` (400) e `RequestValidationError` (400); endpoint del §3.5. |
| `servizio_catalogo/inventario.json` | il contenuto del §3.2 |
| `assistente/catalog.py` | descrizioni, `CATALOG_FAILURE_HINT`, funzioni di formattazione, `make_catalog_tools(base_url, client=None)` |
| `assistente/config.py` | `CATALOGO_BASE_URL` obbligatoria, campo `Settings.catalogo_base_url` (predefinito `http://localhost:8001`, solo per i test che costruiscono `Settings` a mano) |
| `assistente/cli.py` | frase del §2.2, `make_tools` con i due nuovi strumenti (11 in tutto) |

- `InventoryError` = file non valido (il servizio non parte); `CatalogError` = dati dell'utente non
  validi (400). In `Item` le parole chiave sono una tupla (l'oggetto resta immutabile).
- `make_catalog_tools(base_url, client=None)`: se `client` è `None` crea
  `httpx.Client(base_url=base_url, timeout=5.0)`. I test passano un `httpx.Client` con
  `MockTransport` oppure il `TestClient` di FastAPI sull'app vera (test di contratto, §7).
  `base_url` serve anche al testo «non raggiungibile».
- Il `_call` di `catalog.py` ha la stessa struttura di quello di `dates.py` (trasporto, JSON,
  dizionario, codici, formattazione protetta da `KeyError`/`TypeError`/`ValueError`), con due
  differenze: 400 **e** 404 con `detail` testuale sono errori dell'utente, e non c'è il parametro
  `oggi`. `dates.py` non si tocca.

## 5. Configurazione, dipendenze e Docker

- Nessuna dipendenza nuova (fastapi, uvicorn, httpx già fissate; il resto è libreria standard).
- `.env.example`: `CATALOGO_BASE_URL=http://127.0.0.1:8001` con un commento sull'avvio del
  servizio. Il `.env` locale dell'utente va aggiornato allo stesso modo (lo segnala il resoconto).
- Avvio locale, in un altro terminale: `python -m uvicorn servizio_catalogo.app:app --port 8001`.
- `compose.yaml`: servizio `catalogo` (stessa immagine, `target: app`, comando uvicorn su
  `0.0.0.0:8001`, porta `127.0.0.1:8001:8001`); il servizio `assistente` riceve
  `CATALOGO_BASE_URL: http://catalogo:8001` e `depends_on: [giorni, catalogo]`.
- `Dockerfile`: `COPY servizio_catalogo/ servizio_catalogo/` negli stage `test` e `app`.

## 6. Errori e limiti

- Il servizio non legge mai il file dopo l'avvio: modificare `inventario.json` richiede il riavvio.
- Una query lunga non viene troncata: conta solo il punteggio.
- Parole chiave e nomi brevi (meno di 3 caratteri, per esempio «Pi») partecipano al testo
  dell'articolo ma non possono essere cercati da soli.
- Parole vuote nella query come «uno» vengono scartate anche quando sono parte di un nome
  («Arduino Uno» cerca solo `arduin`): accettato, perché il nome resta trovato.

## 7. Test e verifiche

### Test automatici (senza modello e senza rete, scritti prima del codice)

- `tests/test_inventario.py`
  - normalizzazione (accenti, maiuscole, punteggiatura, cifre); radici (esempi del §3.3);
    parole vuote e parole corte scartate; query di sole parole vuote → `CatalogError`;
  - punteggio e ordine (parità risolta per codice), limite 10 con `totale` corretto (inventario di
    prova con più di 10 risultati), filtro per categoria normalizzata, categoria inesistente con
    l'elenco nell'ordine del file;
  - `find`: spazi e minuscole, `LAB-12` → `None`;
  - validazione, un caso per regola: codice malformato o duplicato, campo mancante o in più, tipo
    sbagliato, quantità negativa o booleana, stato fuori elenco, `esaurito` con quantità > 0 e
    quantità 0 non `esaurito`, parola chiave vuota, lista vuota;
  - il file vero: 32 articoli, 8 categorie da 4 nell'ordine del §2.4, nessun articolo con «stampa»
    nel nome, LAB-002 con la nota del §3.2.
- `tests/test_servizio_catalogo.py` (`TestClient`): forma delle tre risposte 200, `q` mancante →
  400 con «parametro 'q' …», query senza parole utili → 400, categoria inesistente → 400, codice
  inesistente → 404 con il codice ripulito.
- `tests/test_catalog.py`
  - con `MockTransport`: testi di successo (plurale e singolare di articoli e pezzi, categoria,
    riga «Altri N…» e «Altro 1…», riga «Note» omessa), nessun risultato con e senza categoria, 400
    e 404 → `Errore: …` (404 con il suggerimento), servizio irraggiungibile, JSON non valido, JSON
    non oggetto, 500, campi mancanti → testo con `CATALOG_FAILURE_HINT`, mai un'eccezione;
    parametri inviati (`categoria` assente se `category` è `None`);
  - test di contratto con il `TestClient` dell'app vera: «multimetro» → riga di LAB-001; scheda di
    LAB-002; codice inesistente; categoria inesistente.
- `tests/test_config.py`: `CATALOGO_BASE_URL` mancante → errore, valore letto in `Settings`.
- `tests/test_cli.py`: `make_tools` restituisce 11 strumenti con `search_catalog` e
  `get_catalog_item`; `SYSTEM_PROMPT` contiene la frase del §2.2.

### Prove reali (separate, attivate esplicitamente)

- `tests/integration/test_lmstudio.py`: `test_real_model_uses_catalog` («Dove trovo il
  multimetro?» → chiamata a `search_catalog`, risposta con «Armadio A»). Richiede i servizi giorni
  e catalogo avviati.
- Serie con `google/gemma-4-e2b`, 10 tentativi per ciascuna domanda del §1, nuova cronologia a ogni
  tentativo, in uno script usa e getta che registra strumenti chiamati, argomenti e risposta.
- Servizio catalogo spento: 10 tentativi di «Dove trovo il multimetro?»; si contano le risposte che
  danno una posizione inventata. Nessuna soglia vincolante: l'esito è riportato e, se le posizioni
  inventate sono frequenti, si decide con l'utente (come §10.1 dello strumento 3).
- Checklist Docker: «Dove trovo il multimetro?», «esci» con `docker compose run --rm -T --build
  assistente`, più le voci esistenti nella verifica completa prima del push.

## 8. Documentazione e commit

- README: configurazione (`CATALOGO_BASE_URL`), avvio del servizio locale e in Docker, test,
  diagnosi (servizio non raggiungibile, porta 8001 occupata), solo comandi verificati.
- `CLAUDE.md`: struttura (`servizio_catalogo/`, `catalog.py`), avvio del servizio, porta 8001;
  modifica proposta all'utente prima di farla.
- `tests/test-manuali.txt` (escluso da Git): voci del catalogo.
- `docs/registro-test.md`: esiti delle prove; `docs/registro-modifiche.md` per eventuali correzioni.
- Piano approvato copiato in `Es.1/plan.md` (commit `docs:`).
- Commit in Conventional Commits in italiano (`feat(catalogo): …`, `test(catalogo): …`,
  `build: …`, `docs: …`); merge in `dev` con l'ok dell'utente, push solo su richiesta.
