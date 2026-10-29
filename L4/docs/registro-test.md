# Registro dei test

Esiti delle verifiche eseguite sull'assistente. Ogni sessione indica data, commit, ambiente e
comandi; i test elencati per nome sono quelli raccolti da pytest.

## Sessione del 2026-10-29 — commit `302f4a8`

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

### Resta da provare

- La checklist da un terminale interattivo vero (`docker compose run --rm assistente`, senza `-T`).
