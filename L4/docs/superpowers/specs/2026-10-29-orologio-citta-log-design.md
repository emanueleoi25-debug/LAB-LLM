# Orologio per città e log dei messaggi al modello

Data: 2026-10-29
Stato: in revisione
Specifica di riferimento: `2026-10-26-assistente-langgraph-design.md` (resta valida per tutto ciò
che qui non è modificato; le sezioni citate come «§N» sono le sue).

## 1. Problemi osservati

1. **L'utente deve conoscere il fuso orario.** Alla domanda «ciao che ore sono a Miami?» il
   modello `google/gemma-4-e2b` ha chiamato `get_current_time {}`: lo strumento accetta solo un
   nome IANA (`America/New_York`) e lascia al modello la traduzione città → fuso, che il modello
   piccolo non ha fatto. Lo strumento è ricaduto sul fuso predefinito (`Europe/Rome`) e la
   risposta è stata «non ho accesso all'orario di Miami». Il comportamento rispettava §5, ma il
   progetto era sbagliato: dev'essere lo strumento a trovare il fuso della città.
2. **I log non mostrano il dialogo con il modello.** A schermo compaiono solo `strumento
   richiesto` e `risultato strumento`; non si vede che cosa riceve il modello e che cosa decide.

### Criteri di successo

- Con LM Studio e `google/gemma-4-e2b`, «Che ore sono a Miami?» produce una chiamata a
  `get_current_time` con una città, il risultato riporta `America/New_York` e la risposta è
  coerente con l'ora reale di Miami.
- Con `LOG_LEVEL=INFO` a schermo compaiono i messaggi inviati al modello e quelli ricevuti.
- La suite senza modello passa su Python 3.13 (venv) e 3.14 (container).
- Senza città lo strumento usa ancora `DEFAULT_TIMEZONE`, predefinito `Europe/Rome`.

### Fuori ambito

Geolocalizzazione via Internet, disambiguazione interattiva degli omonimi, paese come parametro
separato, persistenza dei log su file, altri strumenti.

## 2. Ricerca città → fuso (`assistente/cities.py`, nuovo)

- Dipendenza `geonamescache==3.0.2` in `requirements.txt` (licenza MIT, dati GeoNames inclusi
  nel pacchetto, nessun accesso alla rete). Richiede Python ≥ 3.10; la compatibilità con 3.13 e
  3.14 è verificata dalla suite su entrambe le versioni. Costo: circa 187 MB installati.
- Archivio: città con almeno 5.000 abitanti (`GeonamesCache(min_city_population=5000)`,
  69.472 città).
- `City`: `NamedTuple` con `name` (nome ufficiale), `country` (codice ISO del paese),
  `timezone` (nome IANA).
- `find_city(name: str) -> City | None`:
  - confronto su `name.strip().casefold()`, sia con il nome principale sia con i nomi
    alternativi (es. «Nuova York», «Pechino», «Monaco di Baviera»);
  - con più città dallo stesso nome vince la più popolosa («Paris» → Francia, «Miami» → Florida);
  - nome vuoto o sconosciuto → `None`.
- L'indice nome → città si costruisce alla prima ricerca (circa 0,6 s misurati) e resta in
  memoria per la sessione (`functools.lru_cache`).

## 3. Strumento orologio (sostituisce §5)

`get_current_time(city: str | None = None) -> str`

- Descrizione per il modello: «Restituisce la data e l'ora attuali in una città. Parametro city:
  il nome della città citata dall'utente, così come l'ha scritta (es. 'Miami', 'Nuova York').
  Se l'utente non nomina una città, omettilo e si usa il fuso predefinito.»
- Risoluzione di `city`, in quest'ordine:
  1. assente o vuoto → `DEFAULT_TIMEZONE`;
  2. nome IANA valido (`Asia/Tokyo`, `UTC`; maiuscole indifferenti, come oggi) → quel fuso;
  3. città trovata da `find_city` → il suo fuso;
  4. altrimenti → testo d'errore.
- Risultato in ISO 8601 con offset, seguito da che cosa è stato usato:
  - città: `2026-10-29T05:30:24-04:00 (Miami, US, fuso America/New_York)`
  - nome IANA: `2026-10-29T18:30:24+09:00 (fuso Asia/Tokyo)`
  - predefinito: `2026-10-29T10:30:24+01:00 (fuso predefinito Europe/Rome)`
  - errore: `Errore: città sconosciuta 'Xyzville'. Indica il nome di una città, ad esempio 'Roma'.`
- Nessuna eccezione verso il grafo; orologio iniettabile e fuso predefinito passati alla
  costruzione, come oggi.
- Prompt di sistema (`cli.py`): alla frase sull'uso dello strumento si aggiunge «Se l'utente
  chiede l'ora di una città, passa il nome della città nel parametro city.»

## 4. Log dei messaggi al modello (estende §9)

Solo il nodo `modello` di `graph.py` cambia; livello INFO, logger `assistente.graph`.

- Prima della chiamata: una riga per ciascun messaggio **nuovo** dall'ultima `AIMessage` della
  cronologia (alla prima domanda anche il prompt di sistema), non l'intera cronologia:
  - `→ modello [sistema] …`, `→ modello [utente] …`, `→ modello [strumento <nome>] …`
- Dopo la chiamata:
  - `← modello [chiamata] <nome> <argomenti>` per ogni `tool_call`;
  - `← modello [chiamata non valida] <nome> <argomenti o errore>` per ogni `invalid_tool_call`;
  - `← modello [risposta] <testo>` se il testo non è vuoto.
- Gli a capo nel testo diventano `\n`, così ogni messaggio occupa una riga.
- Restano invariate le righe `strumento richiesto`, `risultato strumento` e l'avviso del limite.
- Per nascondere questi log basta `LOG_LEVEL=WARNING`.

Esempio:

```
INFO assistente.graph: → modello [utente] ciao che ore sono a Miami?
INFO assistente.graph: ← modello [chiamata] get_current_time {'city': 'Miami'}
INFO assistente.graph: strumento richiesto: get_current_time {'city': 'Miami'}
INFO assistente.graph: risultato strumento: 2026-10-29T05:30:24-04:00 (Miami, US, fuso America/New_York)
INFO assistente.graph: → modello [strumento get_current_time] 2026-10-29T05:30:24-04:00 (Miami, US, fuso America/New_York)
INFO assistente.graph: ← modello [risposta] A Miami sono le 5:30 del mattino.
```

## 5. Test e verifiche

### Automatici (senza modello)

- `tests/test_cities.py` (nuovo): Miami → `America/New_York`; «Nuova York» e «pechino» tramite
  i nomi alternativi; omonimi → la più popolosa («Paris» → `FR`); spazi e maiuscole ignorati;
  città inesistente e nome vuoto → `None`. Usa l'archivio reale, fisso con la versione bloccata.
- `tests/test_tools.py`: città con istante fisso → ora e testo attesi; nome IANA accettato;
  `city` assente o vuota → fuso predefinito; città sconosciuta → testo d'errore; schema JSON con
  il solo parametro `city`.
- `tests/test_graph.py`: con `ScriptedModel` e `caplog`, righe `→ modello` / `← modello` per
  domanda, chiamata, risultato e risposta; `[sistema]` solo alla prima domanda; a capo come `\n`;
  `[chiamata non valida]`.
- `tests/test_cli.py`: il prompt di sistema cita il parametro `city`.

### Reali (attivazione esplicita)

- `test_real_model_uses_clock_tool` chiede l'ora a Miami e verifica che lo strumento sia
  chiamato con una città e che il risultato contenga `America/New_York`.
- Suite nel container (`docker compose --profile test run --rm --build test`).
- Checklist manuale in Docker: «Che ore sono a Miami?» (log e ora coerente), «Quale città ti ho
  chiesto prima?», nuova sessione senza memoria; «Che ore sono?» → fuso predefinito.

## 6. Documentazione e Git

- README: strumento con la città, esempio di log, diagnosi per «città sconosciuta» e per la
  chiamata senza città (ricaduta sul fuso predefinito).
- `L4/CLAUDE.md`: `cities.py` nella struttura del pacchetto.
- `docs/registro-test.md`: nuova sessione con gli esiti.
- `docs/registro-modifiche.md` (nuovo): una voce per modifica con data, che cosa non era giusto,
  causa, soluzione, commit e verifica. Voci: `1471fe2` (versione di `openai` diversa tra venv e
  container), `302f4a8` (chiamate allo strumento non valide che facevano perdere la sessione),
  strumento per città, log dei messaggi.
- Piano in `docs/superpowers/plans/` e aggiunto a `Es.1/plan.md`.
- Commit (Conventional Commits in italiano), ciascuno dopo la suite verde su 3.13 e 3.14:
  `docs(spec)`, `docs(piano)`, `feat(strumenti)` (§2–3 con test), `feat(grafo)` (§4 con test),
  `docs` (README, CLAUDE.md, registri).
