# Revisore: la risposta è coerente con la domanda?

Data: 2026-11-13, approvata dall'utente il 2026-11-13. Branch: `feat/revisore` (da `dev` = `155e464`). Step 2
della lezione 6 (`Es.1/LLM_Lez_6.pdf`, «Grafo con due nodi LLM»), secondo dei nove step della
roadmap in `CLAUDE.md`. Gli step successivi (riassunto, resource, …) non si anticipano.

## 1. Obiettivo

Dopo la risposta dell'agente, un secondo nodo LLM (`revisore`) controlla che la risposta sia
coerente con la domanda dell'utente: tutte le parti richieste, nessuna deviazione dal tema. Una
risposta incompleta o fuori tema torna all'agente con il motivo, finché non è coerente o si
raggiunge il limite di revisioni. Al limite si restituisce l'ultima risposta e lo si segnala nei
log. Il revisore usa lo stesso modello di LM Studio con un prompt di sistema proprio e un output
strutturato (coerente sì o no, e motivo).

### Scelte dell'utente (brainstorming del 2026-11-13)

- Cronologia (opzione B): durante il turno l'agente vede la bozza rifiutata e l'indicazione del
  revisore; a fine turno restano solo domanda, eventuali coppie strumento e risposta finale.
- Limite (opzione A): variabile d'ambiente `MAX_REVISIONI`, intero ≥ 1, predefinito 1. Il
  revisore giudica anche l'ultima bozza; se la rifiuta al limite, l'utente riceve comunque quella
  bozza e nel log compare un avviso.
- Che cosa vede il revisore (opzione B): conversazione recente (ultimi 4 messaggi di testo, come il
  router), domanda e risposta proposta. Non vede chiamate e risultati degli strumenti: giudica la
  coerenza, non la fedeltà ai risultati (vedi «Fuori ambito»).
- Approccio 1: nodo `revisore` separato e modulo `assistente/revisore.py` gemello di
  `router.py`; costruzione del contesto recente condivisa con il router. Scartati: revisione
  dentro il nodo `agente` (instradamento nascosto) e un «giudice strutturato» generico per router
  e revisore (astrazione prematura).
- Errori del server durante la revisione (`openai.OpenAIError`): la bozza viene approvata con un
  avviso, perché esiste già (diverso dal router, dove la domanda viene scartata).
- Dopo lo spike (§9): motivo vuoto accettato quando `coerente=true`, obbligatorio quando
  `coerente=false`; indicazione come `HumanMessage` (il `SystemMessage` funziona, ma provato una
  volta sola).
- CLI: mostra solo la risposta finale (approvata o lasciata dal limite), mai le bozze. È la
  «decisione da prendere» del PDF sullo streaming, per la CLI; per il browser si decide allo step 8.

### Criteri di successo

- Evidenze del PDF:
  - domanda in due parti con risposta parziale: rifiuto motivato e nuova risposta completa (test
    simulato e prova reale con prima bozza simulata, §7.2);
  - risposta coerente approvata al primo passaggio (test simulato e prova reale);
  - limite rispettato con un revisore simulato che rifiuta sempre (test simulato).
- Dopo il turno la cronologia non contiene bozze rifiutate né indicazioni del revisore.
- Le 11 prove reali esistenti, che ora passano anche dal revisore, restano verdi (nessun falso
  rifiuto che le faccia fallire).
- La suite senza modello passa su Python 3.13 (venv) e 3.14 (container).
- Router, strumenti, limite dei passaggi e rifiuto continuano a funzionare.

### Fuori ambito

Fedeltà della risposta ai risultati degli strumenti (possibile estensione, da provare con uno spike
a parte se l'utente lo chiede); revisione delle risposte fisse (`rifiuto`, `limite`); modello
diverso per il revisore; azzeramento di `tool_steps` a ogni nuovo tentativo; streaming e bozze
mostrate all'utente; riassunto della cronologia e gli altri step della lezione 6.

## 2. Il grafo

```
START → router ─┬─ fuori_ambito ─→ rifiuto → END
                └─ conversazione → agente

agente ─┬─ tool_call, tool_steps < max ─→ strumenti → agente
        ├─ tool_call, tool_steps >= max → limite → END
        └─ nessuna tool_call ───────────→ revisore

revisore ─┬─ approvata (coerente o risposta non utilizzabile) → END
          ├─ rifiutata, revisioni < MAX_REVISIONI ──────────→ agente
          └─ rifiutata, revisioni = MAX_REVISIONI ──────────→ END (avviso, resta l'ultima bozza)
```

- Senza `reviewer` il grafo resta quello di oggi (`agente` → END quando non ci sono chiamate),
  come senza `router` parte da `agente`: i test esistenti non cambiano.
- `tool_steps` non si azzera quando la risposta torna all'agente: `MAX_TOOL_STEPS` resta un limite
  per domanda. Se l'agente esaurisce i passaggi nel nuovo tentativo, si va a `limite` come oggi.
- `rifiuto` e `limite` producono risposte fisse e vanno a END senza revisione.

### 2.1 Stato (`AssistantState`)

Campi nuovi, tutti `NotRequired` (il grafo senza revisore non li usa):

| Campo | Tipo | Scritto da | Significato |
|---|---|---|---|
| `revisioni` | `int` | `revisore` | Rifiuti già fatti in questo turno; `ask()` lo inizializza a 0 |
| `scartati` | `list[str]` | `revisore` | Id delle bozze rifiutate e delle indicazioni, da togliere a fine turno; `ask()` lo inizializza vuoto |
| `esito_revisione` | `str` | `revisore` | `"approvata"`, `"rifiutata"` (torna all'agente) o `"limite"`; letto dall'instradamento |
| `motivo_revisione` | `str` | `revisore` | Motivo del revisore (o dell'inutilizzabilità della risposta) |

Nel brainstorming il campo dell'esito era un booleano `coerente`; diventa `esito_revisione` a tre
valori perché l'instradamento deve distinguere «rifiutata, si riprova» da «rifiutata al limite».
Il nodo legge `revisioni` e `scartati` con `state.get(…, 0)` e `state.get(…, [])`, così il grafo
funziona anche se chi lo invoca non li passa (test esistenti).

### 2.2 `build_graph`

```python
def build_graph(model, tools=(), max_tool_steps=3, *, router=None,
                reviewer: Reviewer | None = None, max_revisions: int = 1): ...
```

Nodi con il revisore: `router` (se presente), `rifiuto` (se presente router), `agente`,
`strumenti`, `limite`, `revisore`. La docstring del modulo riporta il grafo del §2.

### 2.3 Nodo `revisore`

1. Chiama `reviewer.review(state["messages"], scartati)`.
2. Revisione approvata (`coerente=True`, anche per risposta non utilizzabile o errore del server):
   `esito_revisione="approvata"`, pulizia (§2.4).
3. Rifiutata e `revisioni >= max_revisions`: `esito_revisione="limite"`, avviso nel log, pulizia;
   l'ultima bozza resta come risposta.
4. Rifiutata e `revisioni < max_revisions`: aggiunge l'indicazione (§3.4) come `HumanMessage` con
   id esplicito (`uuid4`), `revisioni + 1`, `scartati` += id della bozza (ultima `AIMessage`) e id
   dell'indicazione, `esito_revisione="rifiutata"`.

`route_after_reviewer`: `"rifiutata"` → `agente`, altrimenti END.

### 2.4 Pulizia della cronologia

Funzione comune `_discard(state) -> list[RemoveMessage]`: un `RemoveMessage` per ogni id in
`scartati`. La usano:

- `revisore` quando approva o raggiunge il limite;
- `limite`, perché anche nel nuovo tentativo l'agente può esaurire i passaggi con gli strumenti
  (in quel caso si tolgono bozze e indicazioni e restano `TOOL_SKIPPED` e `LIMIT_REPLY` come oggi).

Le chiamate agli strumenti e i loro risultati del tentativo rifiutato restano: sono coppie
complete. La bozza rifiutata è sempre un'`AIMessage` senza chiamate (il revisore interviene solo
su quelle), quindi toglierla non separa una chiamata dalla sua `ToolMessage`. Con `scartati` vuoto
non si produce nessun `RemoveMessage` e nessuna riga di log.

## 3. Il revisore (`assistente/revisore.py`)

### 3.1 Interfaccia

```python
COHERENT_UNUSABLE_REASON = "risposta del revisore non utilizzabile"
REVIEW_SCHEMA = {...}   # §3.5

@dataclass(frozen=True)
class Review:
    coerente: bool
    motivo: str
    errore: str | None   # None se la risposta è utilizzabile
    grezza: str          # contenuto ricevuto dal modello ("" per un errore del server)

class Reviewer:
    def __init__(self, model: ChatModel) -> None: ...
    def review(self, messages: list[BaseMessage], discarded: Collection[str] = ()) -> Review: ...
```

- Domanda: l'ultima `HumanMessage` il cui id non è in `discarded`.
- Risposta proposta: il testo dell'ultima `AIMessage`.
- Contesto: gli ultimi 4 messaggi di testo prima della domanda (utente e assistente), come il
  router.
- `openai.OpenAIError` (comprende `APIError` e `LengthFinishReasonError`) durante `invoke` →
  `Review(True, COHERENT_UNUSABLE_REASON, "errore del server: <eccezione>", "")`. Le altre
  eccezioni salgono come oggi.

### 3.2 Contesto condiviso (`assistente/contesto.py`)

Modulo nuovo e piccolo, ricavato da `router._user_message` senza cambiarne il comportamento:

- `flat(text)`: sostituisce `\r` e `\n` con spazi;
- `recent_conversation(messages, end, limit=4) -> str`: `"Conversazione recente:\n" + righe
  "Utente: …"/"Assistente: …"` dei messaggi di testo prima dell'indice `end`, oppure
  `"Conversazione recente: (nessuna)"`.

`router.py` lo usa per il suo messaggio; `tests/test_router.py` passa invariato.

### 3.3 Messaggi mandati al modello

- `SystemMessage(REVIEWER_PROMPT)`, testo provato nello spike (§9):

  > Sei il revisore dell'assistente del laboratorio. Non rispondi alla domanda dell'utente:
  > controlli solo se la risposta proposta è coerente con la domanda. Coerente significa che
  > risponde a tutte le parti richieste e non devia dal tema. Non verificare se i dati sono
  > corretti: l'assistente li ottiene da strumenti che tu non vedi. Una domanda che continua la
  > conversazione recente (per esempio «e a Tokyo?») va letta insieme a quella conversazione.
  > Rispondi solo con un oggetto JSON con due campi: coerente, true se la risposta è coerente e
  > false altrimenti, e motivo, una frase breve in italiano; se la risposta non è coerente, il
  > motivo dice che cosa manca o dove devia.

- `HumanMessage`:

  ```
  <recent_conversation(...)>

  Domanda dell'utente:
  <domanda su una riga>

  Risposta proposta:
  <risposta su una riga>
  ```

I messaggi del revisore non entrano nella cronologia.

### 3.4 Indicazione per l'agente (`REVIEW_HINT`, in `graph.py`)

```
Indicazione del revisore: la risposta non è coerente con la domanda dell'utente. Motivo: <motivo> Rispondi di nuovo alla domanda, in modo completo.
```

Testo provato nello spike (3/3 risposte complete).

### 3.5 Schema e lettura della risposta

```python
REVIEW_SCHEMA = {
    "type": "object",
    "properties": {"coerente": {"type": "boolean"}, "motivo": {"type": "string"}},
    "required": ["coerente", "motivo"],
    "additionalProperties": False,
}
```

Lettura validata (risposta non utilizzabile → `Review(True, COHERENT_UNUSABLE_REASON, <errore>,
<grezza>)`):

| Caso | Esito |
|---|---|
| Contenuto non testuale | `errore="contenuto non testuale"` |
| JSON non valido (anche testo attorno al JSON) | `errore="JSON non valido"` |
| Non è un oggetto | `errore="non è un oggetto JSON"` |
| `coerente` mancante o non booleano (anche `"true"` stringa, `1`) | `errore="coerente mancante o non booleano"` |
| `motivo` presente ma non stringa | `errore="motivo non testuale"` |
| `coerente=false` con `motivo` mancante, vuoto o di soli spazi | `errore="motivo mancante con risposta non coerente"` |
| `coerente=true`, `motivo` mancante o vuoto | utilizzabile, `motivo=""` |
| Campi in più | ignorati |

## 4. Modello e configurazione

### 4.1 Configurazione (`config.py`)

- `Settings.max_revisions: int = 1`.
- `MAX_REVISIONI` facoltativa, predefinita `1`; non intero o < 1 → `MAX_REVISIONI non valido:
  '<valore>' (serve un intero maggiore o uguale a 1)`, raccolto con gli altri problemi (codice 2).
- `.env.example`: riga commentata come `MAX_TOOL_STEPS`. `compose.yaml` non cambia (legge già
  `.env`).

### 4.2 Modello del revisore (`model.py`)

`create_reviewer_model(settings)`: stesso server e modello, `temperature=0`, nessuno strumento,
`response_format` `json_schema` con nome `revisione`, `strict: True` e `REVIEW_SCHEMA`. Stessa
forma di `create_router_model`.

### 4.3 Collegamento (`cli.py`)

- `create_graph` costruisce `Reviewer(create_reviewer_model(settings))` e passa
  `reviewer=…, max_revisions=settings.max_revisions`.
- `ask()` invoca il grafo con `revisioni=0` e `scartati=[]` oltre a `tool_steps=0`.
- `run_chat` non cambia: stampa solo la risposta finale.

### 4.4 Dipendenze e Docker

Nessuna dipendenza nuova. `Dockerfile` e `compose.yaml` invariati.

## 5. Log

Logger `assistente.graph` (nodi) e `assistente.revisore` (messaggi al revisore):

| Quando | Livello e testo |
|---|---|
| Revisione valida | `INFO revisore: coerente=sì motivo=<motivo>` oppure `coerente=no motivo=<motivo>` (su una riga) |
| Risposta non utilizzabile o errore del server | `WARNING revisore: risposta non utilizzabile (<errore>), risposta approvata: <grezza su una riga>` |
| Instradamento | `INFO revisore → END` oppure `INFO revisore → agente (revisione <n> di <max>)` |
| Limite | `WARNING revisore: limite di revisioni raggiunto (<max>), restituita l'ultima risposta` |
| Pulizia | `INFO revisore: tolti <n> messaggi dalla cronologia` (anche dal nodo `limite`) |
| Messaggi mandati al revisore | `DEBUG → revisore [<ruolo>] <testo su una riga>` |

L'indicazione compare da sola nel log dell'agente come `→ modello [utente] Indicazione del
revisore: …`: è l'evidenza del passaggio all'agente.

## 6. Errori

| Caso | Comportamento |
|---|---|
| Risposta del revisore non utilizzabile | Bozza approvata, avviso nel log |
| Errore del server durante la revisione (`openai.OpenAIError`) | Bozza approvata, avviso nel log con l'errore |
| Altre eccezioni nel revisore | Arrivano a `run_chat`, che scarta la domanda come oggi |
| Errore del server durante il nuovo tentativo dell'agente | Come oggi: `run_chat` scarta la domanda, la cronologia della sessione resta quella di prima del turno |
| `MAX_REVISIONI` non valida | `Configurazione non valida: …`, codice 2 |

## 7. Test e verifiche

### 7.1 Test automatici (senza modello e senza rete, scritti prima del codice)

`tests/test_contesto.py`: `recent_conversation` con al più 4 messaggi di testo, salta
`SystemMessage`, `ToolMessage` e `AIMessage` con sole chiamate, a capo sostituiti, «(nessuna)».
`tests/test_router.py` invariato.

`tests/test_revisore.py`:
- risposte valide: `coerente=true` con e senza motivo, `coerente=false` con motivo;
- ogni caso non utilizzabile della tabella del §3.5 → `coerente=True`, `errore` valorizzato,
  `grezza` conservata;
- `openai.APIError` e `LengthFinishReasonError` → approvata, `errore` con «errore del server»;
- un'altra eccezione sale;
- domanda = ultima `HumanMessage` non in `discarded`; risposta = ultima `AIMessage`; contesto
  prima della domanda; il `SystemMessage` è `REVIEWER_PROMPT`.

`tests/test_graph.py` (agente e revisore con due `ScriptedModel`, revisore con risposte JSON):
- coerente: approvata al primo passaggio, agente e revisore chiamati una volta, cronologia
  `[human, ai]`, log `revisore: coerente=sì` e `revisore → END`, nessuna riga «tolti»;
- risposta parziale: rifiuto, l'agente riceve bozza e indicazione (`REVIEW_HINT` con il motivo),
  seconda risposta approvata; cronologia finale `[human, ai finale]`; log con `revisore →
  agente (revisione 1 di 1)` e `tolti 2 messaggi`;
- revisore che rifiuta sempre, `max_revisions=1`: agente 2 volte, revisore 2 volte, avviso del
  limite, risposta finale = seconda bozza, prima bozza e indicazione tolte;
- come sopra con `max_revisions=2`: agente 3 volte, revisore 3 volte, `tolti 4 messaggi`;
- risposta del revisore non utilizzabile ed errore del server: approvata, avviso;
- con router: fuori ambito → revisore mai chiamato;
- `limite` raggiunto al primo tentativo → revisore mai chiamato;
- `limite` raggiunto nel nuovo tentativo dopo un rifiuto → bozza e indicazione tolte, restano
  `TOOL_SKIPPED` e `LIMIT_REPLY`;
- coppie strumento del tentativo rifiutato conservate nella cronologia finale;
- grafo senza `reviewer`: nodi e comportamento invariati; con `reviewer` c'è il nodo `revisore`;
- turno successivo con `ask()`: il router e l'agente non ricevono bozze né indicazioni.

`tests/test_config.py`: `MAX_REVISIONI` predefinita (1), valore valido, `0`, `x`.
`tests/test_model.py`: `create_reviewer_model` con `REVIEW_SCHEMA`, `temperature=0`, nessuno
strumento.
`tests/test_cli.py`: `create_graph` costruisce il grafo con il nodo `revisore`; `ask()` passa
`revisioni=0` e `scartati=[]`.

### 7.2 Prove reali (separate, attivate esplicitamente)

1. **Spike prima della spec**: fatto il 2026-11-13, esito al §9.
2. **Due prove nuove marcate `lmstudio`** in `tests/integration/test_lmstudio.py`:
   - «Che ore sono a Tokyo?» con il grafo completo → log `revisore: coerente=sì`, nessuna riga
     `revisore → agente`;
   - **prima bozza simulata**: un involucro del modello agente restituisce alla prima chiamata
     «A Tokyo sono le 01:05.» per «Che ore sono a Tokyo e quanto fa 15 per 4?», poi passa al
     modello vero; revisore vero. Atteso: `revisore: coerente=no`, `revisore → agente`, risposta
     finale con «60», cronologia senza bozza né indicazione. Nel README è detto esplicitamente che
     la prima bozza è simulata: la prova dimostra il rifiuto e la correzione con il modello vero,
     non che l'agente vero sbagli da solo.
3. **Le 11 prove reali esistenti** passano ora anche dal revisore: tempo atteso più lungo (circa
   35–45 s in più per ogni turno in ambito). Esito e tempo in `docs/registro-test.md`.
4. **Docker**: suite su 3.14; checklist con «Che ore sono a Tokyo e quanto fa 15 per 4?» →
   righe del revisore nei log.

## 8. Documentazione e commit

- README: grafo con il revisore, `MAX_REVISIONI`, righe di log del revisore, scelta della CLI
  (solo risposta finale), tempi, diagnosi (risposta del revisore non utilizzabile, rifiuti
  inattesi, limite raggiunto spesso), prova con prima bozza simulata.
- `CLAUDE.md`, «Struttura e comandi»: `revisore.py`, `contesto.py`, nodo `revisore`,
  `MAX_REVISIONI`.
- `.env.example`: `MAX_REVISIONI`.
- `tests/test-manuali.txt` (fuori da Git): domanda in due parti.
- `docs/registro-test.md`: spike (sessione 18), prove reali, suite.
- Commit piccoli, uno per incremento verificato, per esempio `refactor(router): contesto recente
  condiviso`, `feat(revisore): lettura della revisione`, `feat(grafo): nodo revisore e pulizia
  della cronologia`, `feat(config): MAX_REVISIONI`, `test(revisore): prove reali con LM Studio`,
  `docs: revisore nel README e nei registri`.
- Piano approvato copiato in `Es.1/plan.md`.

## 9. Esito dello spike (2026-11-13, prima della spec)

Script usa e getta nella scratchpad, `google/gemma-4-e4b` caricato in LM Studio (porta 1234),
prompt e indicazione del §3.3 e §3.4, schema del §3.5. Dettagli in `docs/registro-test.md`,
sessione 18.

| Prova | Esito | Tempo per chiamata |
|---|---|---|
| Giudizio, risposte parziali o fuori tema (P1 due parti, P2 due parti, P3 fuori tema; ×2) | 6/6 rifiutate, motivi precisi (per esempio «non risponde alla seconda parte della domanda, ovvero il calcolo di 15 per 4») | 38–47 s |
| Giudizio, risposte complete (C1 due parti, C2 catalogo, C3 seguito «e a Tokyo?», C4 «Che cosa ti ho chiesto prima?»; ×2) | 8/8 approvate | 33–40 s |
| Correzione, indicazione come `HumanMessage` (bozza «A Tokyo sono le 01:05.») | 3/3 complete: `get_current_time` e `calculate` richiamati, «15 per 4 fa 60» | 47–51 s (grafo dell'agente) |
| Correzione, indicazione come `SystemMessage` | 1/1 completa, nessun errore del template | 31 s |

Osservazioni:
- Token di uscita del revisore 317–445 per circa 30 visibili: ragionamento nascosto, come per il
  router. Un turno in ambito coerente costa circa 35–45 s in più; il caso peggiore con
  `MAX_REVISIONI=1` (router, bozza, revisione, nuova bozza, revisione) circa 3,5–4 minuti.
- Con `coerente=true` il motivo era vuoto in 6 approvazioni su 8: da qui la regola del §3.5.
- Lo schema JSON è stato rispettato in 14 risposte su 14.
