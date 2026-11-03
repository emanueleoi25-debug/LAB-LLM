# Registro dei test

Esiti delle verifiche eseguite sull'assistente. Ogni sessione indica data, commit, ambiente e
comandi; i test elencati per nome sono quelli raccolti da pytest.

## Sessione del 2026-11-03 — commit `11c6039`

Convertitore di unità (`feat/convertitore-unita`): codice in `de7422c` e `7f1d819`, prova reale in
`11c6039`. Modello `google/gemma-4-e2b` in LM Studio sull'host.

### Riepilogo

| Verifica | Ambiente | Comando | Superati | Non superati | Skipped |
|---|---|---|---|---|---|
| Suite senza modello | venv locale, Python 3.13.14 | `python -m pytest` | 140 | 0 | 4 |
| Suite senza modello | container `test`, Python 3.14.9 | `docker compose --profile test run --rm --build test` | 140 | 0 | 4 |
| Prove reali con LM Studio | venv locale | `$env:RUN_LMSTUDIO_TESTS = "1"; python -m pytest -m lmstudio -v` | 4 | 0 | 0 |
| Conversione in Docker | container `assistente` + LM Studio sull'host | `"Quanti chilometri sono 10 miglia?", "esci" \| docker compose run --rm -T --build assistente` | 1 | 0 | 0 |
| Serie a mano | venv locale, `"<domanda>" \| python -m assistente`, `LOG_LEVEL=INFO`, una sessione per domanda | 6 domande | 4 con lo strumento | 2 senza strumento | 0 |

Le suite su 3.13 e su 3.14 sono passate anche su `7f1d819` (140 passed, 3 skipped). Rieseguite su
`11c6039`, la nuova prova reale risulta skipped: 4 skipped.

Test nuovi, superati su 3.13 e 3.14:
- `tests/test_units.py`: `test_find_unit` (18 casi), `test_unknown_unit_is_none` (3),
  `test_names_are_unique`, `test_categories_in_order`, `test_one_base_unit_per_category`,
  `test_reference_conversions` (8);
- `tests/test_tools.py`: `test_convert_units` (12 casi), `test_unknown_unit_lists_allowed_units`,
  `test_incompatible_units` (2), `test_below_absolute_zero`, `test_non_finite_value` (3),
  `test_result_too_large`, `test_converter_tool_accepts_numeric_string`,
  `test_converter_tool_schema`;
- `tests/test_graph.py`: `test_converter_call_returns_real_result`;
- `tests/test_cli.py`: `test_tools_include_clock_and_converter`,
  `test_system_prompt_mentions_converter`;
- prova reale: `test_real_model_uses_converter` (superata con LM Studio).

### Serie a mano

Tra le 10:15 e le 10:25 ora di Roma, ogni domanda in una sessione nuova.

| Domanda | Argomenti dello strumento | Risultato dello strumento | Risposta | Esito |
|---|---|---|---|---|
| Quanti chilometri sono 10 miglia? | `{'from_unit': 'miglia', 'to_unit': 'chilometri', 'value': 10}` | `10 mi = 16.09 km (lunghezza)` | «10 miglia sono circa 16.09 chilometri.» | superato |
| Quanti gradi Fahrenheit sono 30 gradi Celsius? | `{'from_unit': 'Celsius', 'to_unit': 'Fahrenheit', 'value': 30}` | `30 °C = 86.00 °F (temperatura)` | «30 gradi Celsius sono 86.00 gradi Fahrenheit.» | superato |
| Quanti kg sono 150 libbre? | `{'from_unit': 'libbre', 'to_unit': 'kg', 'value': 150}` | `150 lb = 68.04 kg (massa)` | «150 libbre equivalgono a 68.04 kg.» | superato |
| Quanti km/h sono 20 nodi? | `{'from_unit': 'nodi', 'to_unit': 'km/h', 'value': 20}` | `20 kn = 37.04 km/h (velocità)` | «20 nodi equivalgono a circa 37.04 km/h.» | superato |
| Quante ore ci sono in 3 settimane? | nessuna chiamata | — | «Ci sono 504 ore in 3 settimane.» (corretto, ma calcolato a mente) | non superato |
| Quanti kg sono 5 km? | nessuna chiamata | — | «Non è possibile convertire chilometri (misura di lunghezza) in chilogrammi (misura di massa)…» | non superato |

**Le due domande senza strumento sono state ripetute 3 volte ciascuna**, con lo stesso esito (4 su 4
senza chiamata). Le risposte sono sempre state corrette e nessuna ha inventato una conversione tra
km e kg. Il criterio della specifica chiede però il testo d'errore dello strumento, e quello non è
arrivato.

**Stesse domande riformulate**, 2 volte ciascuna:

| Domanda | Argomenti | Risultato dello strumento | Risposta | Esito |
|---|---|---|---|---|
| Converti 3 settimane in ore | `{'from_unit': 'settimane', 'to_unit': 'ore', 'value': 3}` | `3 wk = 504.00 h (tempo)` | «3 settimane equivalgono a 504 ore.» | 2 su 2 |
| Converti 5 km in kg | `{'from_unit': 'km', 'to_unit': 'kg', 'value': 5}` | `Errore: unità incompatibili: 'km' è una lunghezza, 'kg' è una massa.` | «Non è possibile convertire chilometri (lunghezza) in chilogrammi (massa)…» | 2 su 2 |

### Conversione in Docker

`{'from_unit': 'miglia', 'to_unit': 'chilometro', 'value': 10}` → `10 mi = 16.09 km (lunghezza)`;
risposta «10 miglia sono circa 16.09 chilometri.», poi `esci` e «Arrivederci.». I log del container
riportano l'ora in UTC.

## Sessione del 2026-11-02 — commit `220f277`

Verifica da capo dopo la correzione della ricerca delle città emersa nella revisione finale.

### Riepilogo

| Verifica | Ambiente | Comando | Superati | Non superati | Skipped |
|---|---|---|---|---|---|
| Suite senza modello | venv locale, Python 3.13.14 | `python -m pytest` | 83 | 0 | 3 |
| Suite senza modello | container `test`, Python 3.14.9 | `docker compose --profile test run --rm --build test` | 83 | 0 | 3 |
| Prove reali con LM Studio | venv locale, modello `google/gemma-4-e2b` | `$env:RUN_LMSTUDIO_TESTS = "1"; python -m pytest -m lmstudio -v` | 3 | 0 | 0 |
| Checklist manuale in Docker | container `assistente` + LM Studio sull'host | `docker compose run --rm -T --build assistente` | 4 | 0 | 0 |
| Serie di città | venv locale, `python -m assistente`, una sessione per domanda | «Che ore sono a <città>?» | 20 | 0 | 0 |

Test nuovi, superati su 3.13 e 3.14:
- `test_main_name_beats_alternate_name_of_bigger_city[Zaragoza]`, `[Islamabad]`, `[Cancun]`;
- `test_much_bigger_city_wins_with_alternate_name[Roma]`, `[Mexico]`.

### Checklist manuale in Docker

| Passo | Osservato | Esito |
|---|---|---|
| «Che ore sono a Miami?» | `{'city': 'Miami'}` → `2026-11-02T04:19:35-05:00 (Miami, US, fuso America/New_York)` | superato |
| «Quale città ti ho chiesto prima?» | «Mi hai chiesto l'ora a Miami.» | superato |
| nuovo avvio, stessa domanda | «Non mi hai chiesto una città prima in questa conversazione.» | superato |
| «Che ore sono?» | `{}` → `2026-11-02T10:20:25+01:00 (fuso predefinito Europe/Rome)` | superato |

### Serie di città

Tra le 10:20 e le 10:39 ora di Roma, ogni domanda in una sessione nuova. Le 17 città della
sessione su `5df730f` hanno dato gli stessi argomenti e gli stessi fusi (Miami 5 su 5 con
`{'city': 'Miami'}`). Città aggiunte per la correzione:

| Città | Argomenti dello strumento | Risultato | Esito |
|---|---|---|---|
| Saragozza | `{'city': 'Saragozza'}` | `Zaragoza, ES, fuso Europe/Madrid` | superato |
| Islamabad | `{'city': 'Islamabad'}` | `Islamabad, PK, fuso Asia/Karachi` | superato |
| Roma | `{'city': 'Roma'}` | `Rome, IT, fuso Europe/Rome` | superato |

**San Francisco, primo tentativo: errore di LM Studio.** La domanda è rimasta senza risposta per
12 minuti, poi l'applicazione ha mostrato `Errore: il modello non ha risposto (Error code: 400).
Domanda scartata, riprova.` e si è chiusa regolarmente.
- Nel log del server (`~/.lmstudio/server-logs`) il prompt è stato elaborato alle 10:24:15; alle
  10:36:15 compare `[ERROR][google/gemma-4-e2b] Error: Channel Error` e il task viene annullato.
- È quindi un errore interno di LM Studio. La domanda successiva ha funzionato normalmente.
- Ripetuta in una sessione nuova alle 10:39: `{'city': 'San Francisco'}` →
  `2026-11-02T01:39:42-08:00 (San Francisco, US, fuso America/Los_Angeles)`, superato.

### Resta da provare

- La checklist da un terminale interattivo vero (`docker compose run --rm assistente`, senza `-T`).

## Sessione del 2026-11-02 — commit `5df730f`

Stato dopo l'orologio per città (`8cddce3`) e i log dei messaggi al modello (`5df730f`).

### Riepilogo

| Verifica | Ambiente | Comando | Superati | Non superati | Skipped |
|---|---|---|---|---|---|
| Suite senza modello | venv locale, Python 3.13.14 | `python -m pytest -v` | 78 | 0 | 3 |
| Suite senza modello | container `test`, Python 3.14.9 | `docker compose --profile test run --rm --build test` | 78 | 0 | 3 |
| Prove reali con LM Studio | venv locale, modello `google/gemma-4-e2b` | `$env:RUN_LMSTUDIO_TESTS = "1"; python -m pytest -m lmstudio -v` | 3 | 0 | 0 |
| Checklist manuale in Docker | container `assistente` + LM Studio sull'host | `docker compose run --rm -T --build assistente` | 4 | 0 | 0 |
| Serie di città | venv locale, `python -m assistente`, una sessione per domanda | «Che ore sono a <città>?» | 17 | 0 | 0 |

I 3 skipped delle suite senza modello sono le prove reali, superate nell'esecuzione dedicata.
Su 3.13 e 3.14 l'esito di ogni singolo test è identico (confronto delle due esecuzioni con `-v`).

### Suite senza modello (3.13 e 3.14)

Per file: `test_cities.py` 13, `test_cli.py` 19, `test_config.py` 10, `test_graph.py` 20,
`test_model.py` 5, `test_tools.py` 11, tutti superati; `integration/test_lmstudio.py` 3 skipped.
I test già presenti nella sessione del 2026-10-29 sono tutti superati. Test nuovi o modificati:

| File | Test | Esito |
|---|---|---|
| `test_cities.py` | `test_find_city[Miami]`, `[Nuova York]`, `[pechino]`, `[Città del Messico]`, `[Citta del Messico]`, `[  KYOTO ]` | superati |
| `test_cities.py` | `test_homonyms_pick_most_populous` | superato |
| `test_cities.py` | `test_country_after_comma_is_ignored[Miami, Florida]`, `[Miami, USA]` | superati |
| `test_cities.py` | `test_unknown_or_empty_city[Xyzville]`, `[]`, `[   ]`, `[,]` | superati |
| `test_tools.py` | `test_time_in_city` | superato |
| `test_tools.py` | `test_iana_name_is_accepted[Asia/Tokyo]`, `[ asia/tokyo ]` | superati |
| `test_tools.py` | `test_missing_city_uses_default[None]`, `[]`, `[   ]` | superati |
| `test_tools.py` | `test_unknown_city_returns_error_text[Xyzville]`, `[../etc/passwd]` | superati |
| `test_tools.py` | `test_tool_uses_injected_clock`, `test_old_timezone_argument_falls_back_to_default`, `test_tool_schema` | superati |
| `test_graph.py` | `test_model_exchange_is_logged` | superato |
| `test_graph.py` | `test_system_prompt_logged_only_on_first_question` | superato |
| `test_graph.py` | `test_newlines_are_escaped_in_logs` | superato |
| `test_graph.py` | `test_invalid_call_is_logged` | superato |
| `test_graph.py` | `test_block_content_is_logged_as_text` | superato |
| `test_cli.py` | `test_system_prompt_mentions_city_parameter` | superato |

I vecchi test sul parametro `timezone` di `test_tools.py` sono stati sostituiti da quelli sopra.

### Prove reali con LM Studio

| Test | Esito |
|---|---|
| `test_real_model_answers` | superato |
| `test_real_model_remembers_previous_turn` | superato |
| `test_real_model_uses_clock_tool` (ora chiede Miami e verifica `America/New_York`) | superato |

### Checklist manuale in Docker

Domande inviate da stdin, due sessioni, alle 10:09 ora di Roma (04:09 a Miami).

| Passo | Atteso | Osservato | Esito |
|---|---|---|---|
| «Che ore sono a Miami?» | chiamata con la città, fuso `America/New_York`, righe `→`/`←` nei log | `← modello [chiamata] get_current_time {'city': 'Miami'}` → `2026-11-02T04:09:01-05:00 (Miami, US, fuso America/New_York)`; «sono le 04:09» | superato |
| «Quale città ti ho chiesto prima?» | la risposta cita Miami | «Mi hai chiesto le ore a Miami.» | superato |
| `esci`, nuovo avvio, stessa domanda | il modello non lo sa | «Non mi hai chiesto prima alcuna città.» | superato |
| «Che ore sono?» | fuso predefinito | `get_current_time {}` → `2026-11-02T10:09:45+01:00 (fuso predefinito Europe/Rome)`; «le ore 10:09:45» | superato |

### Serie di città

Ogni domanda in una sessione nuova, tra le 10:02 e le 10:07 ora di Roma. Ore controllate con
`zoneinfo` di Python.

| Città | Argomenti dello strumento | Fuso nel risultato | Risposta coerente |
|---|---|---|---|
| Miami (5 volte) | `{'city': 'Miami'}` ×5 | `America/New_York` (−05:00) | sì ×5 (04:02–04:03) |
| Bari | `{'city': 'Bari'}` | `Europe/Rome` | sì |
| Kyoto | `{'city': 'Kyoto'}` | `Asia/Tokyo` | sì |
| Pechino | `{'city': 'Pechino'}` | `Asia/Shanghai` (Beijing) | sì |
| Nuova York | `{'city': 'Nuova York'}` | `America/New_York` (New York City) | sì |
| Monaco di Baviera | `{'city': 'Monaco di Baviera'}` | `Europe/Berlin` (Munich) | sì |
| San Francisco | `{'city': 'San Francisco'}` | `America/Los_Angeles` | sì |
| Buenos Aires | `{'city': 'Buenos Aires'}` | `America/Argentina/Buenos_Aires` | sì |
| Mumbai | `{'city': 'Mumbai'}` | `Asia/Kolkata` (+05:30) | sì |
| Dubai | `{'city': 'Dubai'}` | `Asia/Dubai` | sì |
| Sydney | `{'city': 'Sydney'}` | `Australia/Sydney` (+11:00) | sì |
| Città del Messico | `{'city': 'Città del Messico'}` | `America/Mexico_City` | sì |
| Chioggia | `{'city': 'Chioggia'}` | `Europe/Rome` | sì |

Confronto con la sessione di base: Miami passa da 1 risposta giusta su 5 a 5 su 5; Bari ora ha
la città negli argomenti invece di `{}`.

### Resta da provare

- La checklist da un terminale interattivo vero (`docker compose run --rm assistente`, senza `-T`).

## Sessione del 2026-10-29 — commit `302f4a8` (sessione di base, prima dell'orologio per città)

### Riepilogo

| Verifica | Ambiente | Comando | Superati | Non superati | Skipped |
|---|---|---|---|---|---|
| Suite senza modello | venv locale, Python 3.13.14 | `python -m pytest -v` | 57 | 0 | 3 |
| Suite senza modello | container `test`, Python 3.14.9 | `docker compose --profile test run --rm --build test` | 57 | 0 | 3 |
| Prove reali con LM Studio | venv locale, modello `google/gemma-4-e2b` | `$env:RUN_LMSTUDIO_TESTS = "1"; python -m pytest -m lmstudio -v` | 3 | 0 | 0 |
| Checklist manuale in Docker | container `assistente` + LM Studio sull'host | `docker compose run --rm assistente` | 3 | 0 | 0 |

I 3 skipped delle suite senza modello sono le prove reali di `tests/integration/test_lmstudio.py`,
disattivate senza `RUN_LMSTUDIO_TESTS=1` e superate nell'esecuzione dedicata della riga 3.
Su 3.13 e 3.14 l'esito di ogni singolo test è identico.

### Suite senza modello (3.13 e 3.14)

`tests/test_cli.py` — 18 superati

| Test | Esito |
|---|---|
| `test_exit_words_end_loop[esci]` | superato |
| `test_exit_words_end_loop[exit]` | superato |
| `test_exit_words_end_loop[  Esci ]` | superato |
| `test_exit_words_end_loop[EXIT]` | superato |
| `test_eof_and_ctrl_c_end_loop[EOFError]` | superato |
| `test_eof_and_ctrl_c_end_loop[KeyboardInterrupt]` | superato |
| `test_blank_lines_are_ignored` | superato |
| `test_reply_is_printed` | superato |
| `test_history_is_kept_between_turns` | superato |
| `test_empty_reply_prints_placeholder` | superato |
| `test_ctrl_c_while_waiting_exits_cleanly` | superato |
| `test_model_error_discards_question_and_continues` | superato |
| `test_main_fails_with_missing_config` | superato |
| `test_http_client_loggers_are_quiet[httpx]` | superato |
| `test_http_client_loggers_are_quiet[httpx2]` | superato |
| `test_http_client_loggers_are_quiet[httpcore]` | superato |
| `test_http_client_loggers_are_quiet[openai]` | superato |
| `test_unexpected_model_error_discards_question_and_continues` | superato |

`tests/test_config.py` — 10 superati

| Test | Esito |
|---|---|
| `test_missing_required_variables_are_named` | superato |
| `test_blank_value_counts_as_missing` | superato |
| `test_values_are_read_and_stripped` | superato |
| `test_log_level_is_normalized_and_validated` | superato |
| `test_environment_wins_over_dotenv` | superato |
| `test_tool_defaults` | superato |
| `test_invalid_max_tool_steps[0]` | superato |
| `test_invalid_max_tool_steps[-1]` | superato |
| `test_invalid_max_tool_steps[tre]` | superato |
| `test_default_timezone_is_validated_and_canonical` | superato |

`tests/test_graph.py` — 15 superati

| Test | Esito |
|---|---|
| `test_reply_without_tool_calls_ends_after_one_model_call` | superato |
| `test_model_receives_all_messages` | superato |
| `test_graph_has_model_node` | superato |
| `test_graph_has_tool_and_limit_nodes` | superato |
| `test_tool_call_runs_tool_and_returns_result_to_model` | superato |
| `test_parallel_tool_calls_count_as_one_step` | superato |
| `test_limit_stops_the_loop` | superato |
| `test_limit_is_logged_as_warning` | superato |
| `test_unknown_tool_returns_error` | superato |
| `test_tool_exception_returns_error` | superato |
| `test_malformed_tool_args_return_error` | superato |
| `test_tool_calls_are_logged` | superato |
| `test_history_after_tool_turn_is_valid_for_next_turn` | superato |
| `test_invalid_tool_call_gets_error_reply` | superato |
| `test_limit_closes_invalid_tool_calls` | superato |

`tests/test_model.py` — 5 superati

| Test | Esito |
|---|---|
| `test_check_model_accepts_listed_model` | superato |
| `test_check_model_lists_available_models` | superato |
| `test_check_model_reports_unreachable_server` | superato |
| `test_create_chat_model_uses_settings` | superato |
| `test_create_chat_model_binds_clock_tool` | superato |

`tests/test_tools.py` — 9 superati

| Test | Esito |
|---|---|
| `test_time_in_requested_zone` | superato |
| `test_missing_zone_uses_default[None]` | superato |
| `test_missing_zone_uses_default[]` | superato |
| `test_missing_zone_uses_default[   ]` | superato |
| `test_zone_name_is_case_and_space_insensitive` | superato |
| `test_unknown_zone_returns_error_text[Marte/Base]` | superato |
| `test_unknown_zone_returns_error_text[../etc/passwd]` | superato |
| `test_tool_uses_injected_clock` | superato |
| `test_tool_schema` | superato |

`tests/integration/test_lmstudio.py` — 3 skipped (motivo: `prova reale: imposta RUN_LMSTUDIO_TESTS=1`)

### Prove reali con LM Studio

| Test | Esito |
|---|---|
| `test_real_model_answers` | superato |
| `test_real_model_remembers_previous_turn` | superato |
| `test_real_model_uses_clock_tool` | superato |

### Checklist manuale in Docker

Domande inviate da stdin (`docker compose run --rm -T assistente`) alle 10:15 ora di Roma.

| Passo | Atteso | Osservato | Esito |
|---|---|---|---|
| «Che ore sono a Tokyo?» | riga `strumento richiesto: get_current_time …` su stderr, ora coerente | `get_current_time {'timezone': 'Asia/Tokyo'}` → `2026-10-29T18:15:19+09:00`; risposta «le ore 18:15» | superato |
| «Quale città ti ho chiesto prima?» | la risposta cita Tokyo | «Mi hai chiesto le ore a Tokyo.» | superato |
| `esci`, nuovo avvio, stessa domanda | il modello non lo sa | «Non mi hai chiesto alcuna città prima in questa conversazione.» | superato |

### Serie di città (prima della modifica)

Strumento con il solo parametro `timezone` (nome IANA), una sessione per domanda.

| Città | Esito |
|---|---|
| Miami (5 volte) | 1 risposta giusta su 5; nelle altre 4 il modello ha chiamato `get_current_time {}` e lo strumento ha usato `Europe/Rome` |
| Bari | chiamata `{}`; risposta giusta solo perché Bari ha lo stesso fuso di Roma |
| Kyoto, Pechino, Nuova York | fuso corretto |

Questo esito ha motivato l'orologio per città (vedi `registro-modifiche.md`).

### Resta da provare

- La checklist da un terminale interattivo vero (`docker compose run --rm assistente`, senza `-T`).
