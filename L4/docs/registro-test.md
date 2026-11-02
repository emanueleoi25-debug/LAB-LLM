# Registro dei test

Esiti delle verifiche eseguite sull'assistente. Ogni sessione indica data, commit, ambiente e
comandi; i test elencati per nome sono quelli raccolti da pytest.

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
