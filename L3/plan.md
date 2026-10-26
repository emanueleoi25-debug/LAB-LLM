# Piani dell'esercitazione: Lezione 3, estensioni del client

Raccolta dei piani proposti e approvati, seguendo il metodo della presentazione `LLM_Lez_3.pdf` (slide 19-22 e 25-29): Ask, Plan, Execute, Verifica, Commit, con un'estensione per commit. Ogni commit si fa solo con l'autorizzazione dell'utente, che approva anche il messaggio (regola in `CLAUDE.md`).

Repository: https://github.com/emanueleoi25-debug/es.1-paolo.git (branch `main`).

| Piano | Commit | Stato |
|---|---|---|
| 1. Estensione 1: input da terminale, più correzione delle risposte vuote | `328943f` feat(client): legge la domanda da terminale, `60aa7f7` fix(client): disattiva il ragionamento del modello | completato, push fatto |
| 2. Estensione 2: streaming | `302201d` feat(client): mostra la risposta in streaming | completato, push fatto |
| 3. Estensione 3: cronologia in memoria | `2d5414d` feat(client): conserva la cronologia della sessione | completato, push fatto |

---

## Piano 1: completare l'estensione 1 (input da terminale) e risolvere le risposte vuote

### Contesto
Slide 25, 26 e 29.

- Commit di base `c643892` (`chore: stato iniziale con lo scheletro del client`) già pubblicato su `origin/main`.
- `client.py` contiene già, non committata, l'estensione 1: ciclo `while True` con `input("Tu> ")`, uscita con `esci`, Ctrl+C o EOF, righe vuote ignorate, payload ricostruito a ogni giro, stessi `except`.
- In più `client.py` contiene una modifica fatta dall'utente: `max_tokens` portato da 180 a 512. È un cambiamento diverso dall'estensione 1.
- `.env` ora è corretto (`LM_BASE_URL = "http://127.0.0.1:1234/v1"`, `LM_MODEL = "google/gemma-4-e2b"`, caricato in LM Studio).

**Problema aperto**: il client stampa righe vuote. Con 180 token la diagnosi ha mostrato `content: ''`, `finish_reason: length`, `reasoning_tokens: 177`, con il testo nel campo `reasoning_content`. Quindi il server, così come è configurato, fa ragionare il modello anche se nell'interfaccia di LM Studio non si vede un'opzione "thinking". Con 512 token il risultato non è ancora stato misurato.

### Passi

#### 0. Salvare il piano nel progetto
Copiare questo piano in `plan.md` nella radice del progetto. Resta non tracciato: non entra nei commit delle estensioni.

#### 1. Diagnosi con 512 token (sola lettura, nessuna modifica)
Eseguire lo script di diagnosi presente nello scratchpad (`max_tokens` 512), con l'interprete `.\.venv\Scripts\python.exe` e dalla radice del progetto. Il risultato decide il passo 2:
- **A**: `content` pieno e `finish_reason: stop`. Allora 512 basta, si passa al passo 3.
- **B**: `content` vuoto con `finish_reason: length`. Il ragionamento consuma anche 512 token, si passa al passo 2.
- **C**: `content` vuoto con `finish_reason: stop`. Il testo finisce tutto in `reasoning_content`: problema di template o parser di LM Studio, si passa al passo 2.

#### 2. Solo per i casi B e C: togliere il ragionamento senza cambiare il codice
In LM Studio, sul modello caricato: impostazioni del modello, poi la scheda dei parametri e del template. Cercare un'opzione per il ragionamento ("Thinking", "Reasoning", "Separate reasoning_content"). Se non c'è, caricare un modello che non ragiona, oppure quello del corso (`qwen3.5-4b`, 4 bit, slide 13), e aggiornare `LM_MODEL` in `.env`. Ripetere il passo 1 finché `content` non contiene la risposta.

#### 3. Verifica manuale dell'estensione 1 (la esegue l'utente nel terminale di VS Code)
`.\.venv\Scripts\python.exe client.py`
- Due domande diverse ricevono risposte pertinenti e non vuote.
- Una riga vuota non fa partire nessuna chiamata. `esci` chiude senza errori.
- Ctrl+C chiude senza traceback.
- Con il server fermo in LM Studio compare "Connessione fallita…". Dopo il riavvio del server la domanda successiva ottiene risposta.

#### 4. Commit separati (prima `git diff`, poi `git add`, poi `git diff --staged`)
Il diff di ogni commit deve contenere una sola modifica (slide 29).
1. Riportare temporaneamente `max_tokens` a 180 in `client.py`, eseguire `git add client.py` e poi `git diff --staged`: deve contenere **solo** il ciclo di input.
2. Rimettere il valore del working tree. Lo staging non cambia, come spiega la slide 3.
3. `git commit` con il messaggio `feat(client): legge la domanda da terminale`.
4. Commit separato `fix` per la correzione delle risposte vuote.
5. `git push` su `origin/main`, con conferma dell'utente prima di eseguirlo.

### Esito
- Diagnosi: con 512 token la domanda breve riceveva risposta (caso A), ma quella tecnica no (caso B: 595 token di ragionamento). Il parametro `"reasoning_effort": "none"` porta il ragionamento a 0 token. L'utente ha scelto un commit fix separato e di tenere `max_tokens` a 512.
- Commit: `328943f` feat(client): legge la domanda da terminale, `60aa7f7` fix(client): disattiva il ragionamento del modello. Push fatto.
- Prove superate: due domande, riga vuota, `esci`, Ctrl+C e server fermo (prove dell'utente), riavvio.

---

## Piano 2: estensione 2, la risposta arriva in streaming

### Ask
- In `client.py` c'erano il ciclo `input()` dell'estensione 1, il payload con `max_tokens` 512 e `reasoning_effort` `"none"`, `"stream": False`, tre `except` e la stampa in blocco di `choices[0].message.content`.
- Formato reale dello streaming di LM Studio, verificato sul server:
  - `HTTP 200` con `Content-Type: text/event-stream`;
  - ogni frammento arriva su una riga `data: {...}` con il testo in `choices[0].delta.content`, e tra un evento e l'altro c'è una riga vuota;
  - il penultimo evento ha `delta: {}` e `finish_reason: "stop"`, l'ultima riga è `data: [DONE]`;
  - `requests` interpreta la risposta come ISO-8859-1, quindi ogni riga va decodificata esplicitamente in UTF-8.

### Plan: modifico solo `client.py`
1. `import json`, dalla libreria standard. Nessuna nuova dipendenza.
2. Nuova funzione `invia(messages)` prima del ciclo, che contiene la chiamata in streaming della slide 27:
   - `"stream": True` nel payload, mantenendo `max_tokens` e `reasoning_effort`;
   - `requests.post(..., stream=True, timeout=(5, 120))` dentro un `with`, poi `raise_for_status()`;
   - per ogni riga: `decode("utf-8")`, salta le righe che non iniziano con `data: `, si ferma a `[DONE]`, stampa con `print(..., end="", flush=True)` e accumula il frammento in `testo`;
   - alla fine un `print()` per andare a capo e `return testo`, cioè il testo completo che servirà nell'estensione 3.
3. Nel ciclo: costruire `messages` (system + user) e chiamare `invia(messages)` dentro il `try`, con gli stessi tre messaggi di errore. Il ramo `HTTPError` usa `errore.response`.

**Fuori perimetro:** cronologia (estensione 3), Ctrl+C durante una risposta, caduta del server a metà di uno streaming (`ChunkedEncodingError`).

### Prove (slide 27 e 29)
- Il testo compare a frammenti e finisce con un a capo.
- Le lettere accentate sono corrette.
- Con il server fermo il messaggio "Connessione fallita…" è invariato.
- Restano valide le prove dell'estensione 1.

### Commit
`feat(client): mostra la risposta in streaming`, solo dopo le prove e con l'autorizzazione dell'utente.

### Esito
- Prove superate: 145 letture separate di stdout in circa 10,5 s, quindi il testo arriva a frammenti; accenti corretti; server non raggiungibile gestito; prove dell'estensione 1 ancora valide.
- Commit `302201d` feat(client): mostra la risposta in streaming. Push fatto.

---

## Piano 3: estensione 3, cronologia che vive finché il client è aperto

### Ask
- Già presenti: il ciclo `input()` (estensione 1) e `invia(messages)`, che manda tutta la lista ricevuta, stampa in streaming e restituisce il testo completo (estensione 2).
- Mancante: `messages` veniva ricreata a ogni giro con solo system + user, quindi il modello non ricordava niente. La risposta restituita da `invia()` veniva scartata.

### Plan: modifico solo `client.py`, nel ciclo principale. `invia()` non cambia.
1. Creare `messages` una volta sola prima del `while`, con il solo messaggio system: `messages = [{"role": "system", "content": SYSTEM}]`.
2. A ogni domanda: `messages.append({"role": "user", "content": domanda})`.
3. `risposta = invia(messages)`, che manda la lista intera.
4. Se la chiamata va a buon fine: `messages.append({"role": "assistant", "content": risposta})`.
5. In ognuno dei tre `except`: `messages.pop()  # la domanda non ha avuto risposta`. I messaggi di errore restano identici.
6. Nessun file e nessun database: la lista vive solo nella memoria del processo.

**Fuori perimetro:** salvataggio su file; limite ai turni o ai token. Ogni turno allunga la richiesta, quindi aumentano token e tempo e prima o poi si raggiunge il limite di contesto (slide 28): lo si segnala, ma non lo si gestisce. Errori a metà dello streaming.

### Prove (slide 28)
- «Mi chiamo Luca», poi «Come mi chiamo?»: la risposta usa il nome.
- Dopo il riavvio di `client.py` il nome non è più noto.
- Una richiesta fallita non lascia una domanda senza risposta nella lista. Claude la verifica con uno script nello scratchpad che fa fallire la prima chiamata e controlla `messages`. L'utente la verifica con il server fermato: «Mi chiamo Marco» fallisce, il server viene riavviato, «Come mi chiamo?» non deve rispondere Marco.
- Restano valide le prove delle estensioni 1 e 2.

### Commit
`feat(client): conserva la cronologia della sessione`, solo dopo le prove e con l'autorizzazione dell'utente.

### Esito
- Implementato: `messages` creata prima del ciclo, `append` di user e assistant (quest'ultimo nel ramo `else`), `pop()` nei tre `except`. Diff di 9 righe aggiunte e 5 tolte, solo `client.py`.
- Prove di Claude superate: «Ti chiami Luca.»; dopo il riavvio «Non mi hai detto come ti chiami…»; con la richiesta fallita `messages` finale = system, user, assistant, senza «Marco»; server non raggiungibile ed EOF gestiti.
- Commit `2d5414d` feat(client): conserva la cronologia della sessione, autorizzato dall'utente. Push fatto.
