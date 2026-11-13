import json
import logging
from datetime import datetime, timezone

import httpx
import openai
import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from assistente.cli import ask, new_history
from assistente.dates import make_date_tools
from assistente.graph import LIMIT_REPLY, REFUSAL_REPLY, REVIEW_HINT, TOOL_SKIPPED, build_graph
from assistente.revisore import Reviewer
from assistente.router import Router
from assistente.tools import make_calculator_tool, make_clock_tool, make_converter_tool
from tests.fakes import ScriptedModel

NOW = datetime(2026, 10, 26, 16, 5, tzinfo=timezone.utc)
TOKYO = "2026-10-27T01:05:00+09:00 (Tokyo, JP, fuso Asia/Tokyo)"
clock = make_clock_tool("Europe/Rome", clock=lambda: NOW)


def call(name, args, id):
    return {"name": name, "args": args, "id": id, "type": "tool_call"}


def start(text="x"):
    return {"messages": [HumanMessage(text)], "tool_steps": 0}


def tokyo_scenario():
    return ScriptedModel([
        AIMessage("", tool_calls=[call("get_current_time", {"city": "Tokyo"}, "c1")]),
        AIMessage("Sono le 01:05"),
    ])


def test_reply_without_tool_calls_ends_after_one_model_call():
    model = ScriptedModel([AIMessage(content="Ciao!")])
    result = build_graph(model).invoke({"messages": [HumanMessage("Ciao")], "tool_steps": 0})
    assert len(model.calls) == 1
    assert [m.type for m in result["messages"]] == ["human", "ai"]
    assert result["messages"][-1].content == "Ciao!"


def test_model_receives_all_messages():
    model = ScriptedModel([AIMessage(content="ok")])
    build_graph(model).invoke({"messages": [SystemMessage("s"), HumanMessage("d")], "tool_steps": 0})
    assert [m.type for m in model.calls[0]] == ["system", "human"]


def test_graph_has_model_node():
    assert "agente" in build_graph(ScriptedModel([])).get_graph().nodes


def test_graph_has_tool_and_limit_nodes():
    nodes = build_graph(ScriptedModel([]), [clock]).get_graph().nodes
    assert {"agente", "strumenti", "limite"} <= set(nodes)


def test_tool_call_runs_tool_and_returns_result_to_model():
    model = tokyo_scenario()
    result = build_graph(model, [clock]).invoke(start("ora a Tokyo?"))
    sent = model.calls[1][-1]
    assert isinstance(sent, ToolMessage) and sent.tool_call_id == "c1" and sent.content == TOKYO
    assert sent.name == "get_current_time"
    assert result["messages"][-1].content == "Sono le 01:05" and result["tool_steps"] == 1


def test_parallel_tool_calls_count_as_one_step():
    model = ScriptedModel([
        AIMessage("", tool_calls=[
            call("get_current_time", {"city": "Tokyo"}, "c1"),
            call("get_current_time", {}, "c2"),
        ]),
        AIMessage("fatto"),
    ])
    result = build_graph(model, [clock]).invoke(start())
    tools = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert [m.tool_call_id for m in tools] == ["c1", "c2"]
    assert result["tool_steps"] == 1


def always_tool(n):
    return ScriptedModel([AIMessage("", tool_calls=[call("get_current_time", {}, f"c{i}")]) for i in range(n)])


def test_limit_stops_the_loop():
    model = always_tool(3)
    result = build_graph(model, [clock], max_tool_steps=2).invoke(start())
    tools = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(model.calls) == 3
    assert [m.content for m in tools].count(TOOL_SKIPPED) == 1 and len(tools) == 3
    assert result["messages"][-1].content == LIMIT_REPLY.format(max_tool_steps=2)
    asked = {c["id"] for m in result["messages"] if isinstance(m, AIMessage) for c in m.tool_calls}
    assert asked == {m.tool_call_id for m in tools}


def test_limit_is_logged_as_warning(caplog):
    caplog.set_level(logging.INFO, logger="assistente.graph")
    build_graph(always_tool(3), [clock], max_tool_steps=2).invoke(start())
    warnings = [r for r in caplog.records if r.name == "assistente.graph" and r.levelno == logging.WARNING]
    assert len(warnings) == 1


def single_call_result(name, args, tools):
    model = ScriptedModel([AIMessage("", tool_calls=[call(name, args, "c1")]), AIMessage("ok")])
    result = build_graph(model, tools).invoke(start())
    return next(m for m in result["messages"] if isinstance(m, ToolMessage)).content


def test_unknown_tool_returns_error():
    assert single_call_result("meteo", {}, [clock]) == "Errore: strumento sconosciuto 'meteo'."


def test_converter_call_returns_real_result():
    args = {"value": 10, "from_unit": "miglia", "to_unit": "km"}
    result = single_call_result("convert_units", args, [clock, make_converter_tool()])
    assert result == "10 mi = 16.09 km (lunghezza)"


def test_calculator_call_returns_real_result():
    args = {"expression": "1234 * 5678"}
    result = single_call_result("calculate", args, [clock, make_calculator_tool()])
    assert result == "1234 * 5678 = 7006652"


def test_tool_exception_returns_error():
    @tool
    def boom() -> str:
        """Strumento che fallisce sempre."""
        raise RuntimeError("rotto")

    content = single_call_result("boom", {}, [boom])
    assert content.startswith("Errore durante l'esecuzione di boom") and "rotto" in content


def test_malformed_tool_args_return_error():
    content = single_call_result("get_current_time", {"city": ["Tokyo"]}, [clock])
    assert content.startswith("Errore durante l'esecuzione di get_current_time")


def test_tool_calls_are_logged(caplog):
    caplog.set_level(logging.INFO, logger="assistente.graph")
    build_graph(tokyo_scenario(), [clock]).invoke(start())
    assert "strumento richiesto: get_current_time {'city': 'Tokyo'}" in caplog.text
    assert f"risultato strumento: {TOKYO}" in caplog.text


def test_history_after_tool_turn_is_valid_for_next_turn():
    model = ScriptedModel([
        AIMessage("", tool_calls=[call("get_current_time", {"city": "Tokyo"}, "c1")]),
        AIMessage("Sono le 01:05"),
        AIMessage("Prego"),
    ])
    graph = build_graph(model, [clock])
    history, _ = ask(graph, new_history(), "ora a Tokyo?")
    ask(graph, history, "grazie")
    assert [m.type for m in model.calls[2]] == ["system", "human", "ai", "tool", "ai", "human"]


def invalid_call(id):
    return {"name": "get_current_time", "args": "{bad", "id": id, "error": "JSON non valido", "type": "invalid_tool_call"}


def test_invalid_tool_call_gets_error_reply():
    model = ScriptedModel([AIMessage("", invalid_tool_calls=[invalid_call("c1")]), AIMessage("riprovo")])
    result = build_graph(model, [clock]).invoke(start())
    tools = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert [m.tool_call_id for m in tools] == ["c1"]
    assert tools[0].content.startswith("Errore: argomenti non validi per get_current_time")
    assert result["messages"][-1].content == "riprovo" and result["tool_steps"] == 1


def test_limit_closes_invalid_tool_calls():
    model = ScriptedModel([AIMessage("", invalid_tool_calls=[invalid_call(f"c{i}")]) for i in range(2)])
    result = build_graph(model, [clock], max_tool_steps=1).invoke(start())
    tools = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert [m.tool_call_id for m in tools] == ["c0", "c1"]
    assert tools[-1].content == TOOL_SKIPPED


def model_logs(caplog):
    return [r.getMessage() for r in caplog.records if r.getMessage()[:9] in ("→ modello", "← modello")]


def test_model_exchange_is_logged(caplog):
    caplog.set_level(logging.INFO, logger="assistente.graph")
    build_graph(tokyo_scenario(), [clock]).invoke(start("ora a Tokyo?"))
    assert "→ modello [utente] ora a Tokyo?" in caplog.text
    assert "← modello [chiamata] get_current_time {'city': 'Tokyo'}" in caplog.text
    assert f"→ modello [strumento get_current_time] {TOKYO}" in caplog.text
    assert "← modello [risposta] Sono le 01:05" in caplog.text


def test_system_prompt_logged_only_on_first_question(caplog):
    caplog.set_level(logging.INFO, logger="assistente.graph")
    graph = build_graph(ScriptedModel([AIMessage("ciao"), AIMessage("prego")]))
    history, _ = ask(graph, new_history(), "ciao")
    assert caplog.text.count("→ modello [sistema]") == 1
    caplog.clear()
    ask(graph, history, "grazie")
    assert [m for m in model_logs(caplog) if m.startswith("→")] == ["→ modello [utente] grazie"]


def test_newlines_are_escaped_in_logs(caplog):
    caplog.set_level(logging.INFO, logger="assistente.graph")
    build_graph(ScriptedModel([AIMessage("riga1\nriga2")])).invoke(start())
    assert "← modello [risposta] riga1\\nriga2" in model_logs(caplog)


def test_invalid_call_is_logged(caplog):
    caplog.set_level(logging.INFO, logger="assistente.graph")
    model = ScriptedModel([AIMessage("", invalid_tool_calls=[invalid_call("c1")]), AIMessage("riprovo")])
    build_graph(model, [clock]).invoke(start())
    assert any(m.startswith("← modello [chiamata non valida] get_current_time") for m in model_logs(caplog))


def test_block_content_is_logged_as_text(caplog):
    caplog.set_level(logging.INFO, logger="assistente.graph")
    build_graph(ScriptedModel([AIMessage(content=[{"type": "text", "text": "ciao"}])])).invoke(start())
    assert "← modello [risposta] ciao" in model_logs(caplog)


def test_date_tool_call_returns_service_text():
    body = {
        "data": "2027-06-02",
        "giorno": "mercoledì",
        "festivita": "Festa della Repubblica",
        "fine_settimana": False,
        "lavorativo": False,
    }
    date_tools = make_date_tools(
        "http://servizio.test",
        "Europe/Rome",
        clock=lambda: NOW,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body)),
    )
    model = ScriptedModel([
        AIMessage("", tool_calls=[call("date_info", {"date": "2027-06-02"}, "c1")]),
        AIMessage("È festivo."),
    ])
    result = build_graph(model, date_tools).invoke(start("il 2 giugno è festivo?"))
    sent = model.calls[1][-1]
    assert isinstance(sent, ToolMessage) and sent.tool_call_id == "c1" and sent.name == "date_info"
    assert sent.content == "2027-06-02 (mercoledì): festività, Festa della Repubblica; non lavorativo."
    assert result["messages"][-1].content == "È festivo."


def router_says(*categorie):
    replies = [AIMessage(json.dumps({"categoria": c, "motivo": f"motivo {c}"})) for c in categorie]
    return Router(ScriptedModel(replies), "ambito")


def test_graph_nodes_with_router():
    nodes = set(build_graph(ScriptedModel([]), [clock], router=router_says()).get_graph().nodes)
    assert {"router", "agente", "strumenti", "limite", "rifiuto"} <= nodes


def test_in_scope_question_reaches_agent(caplog):
    caplog.set_level(logging.INFO)
    agent = ScriptedModel([AIMessage("Ciao!")])
    result = build_graph(agent, router=router_says("conversazione")).invoke(start("Ciao"))
    assert len(agent.calls) == 1 and result["messages"][-1].content == "Ciao!"
    assert (result["categoria"], result["motivo"]) == ("conversazione", "motivo conversazione")
    assert "router: categoria=conversazione motivo=motivo conversazione" in caplog.text
    assert "router → agente" in caplog.text


def test_out_of_scope_question_is_refused_without_agent(caplog):
    caplog.set_level(logging.INFO)
    agent = ScriptedModel([])
    result = build_graph(agent, router=router_says("fuori_ambito")).invoke(start("ricetta?"))
    assert agent.calls == []
    assert [m.type for m in result["messages"]] == ["human", "ai"]
    assert result["messages"][-1].content == REFUSAL_REPLY
    assert "router → rifiuto" in caplog.text
    assert "rifiuto: domanda fuori ambito, agente non eseguito" in caplog.text
    assert "→ modello" not in caplog.text


def test_unusable_router_reply_falls_back_to_agent(caplog):
    caplog.set_level(logging.INFO)
    agent = ScriptedModel([AIMessage("ok")])
    router = Router(ScriptedModel([AIMessage("boh\nnon so")]), "ambito")
    result = build_graph(agent, router=router).invoke(start())
    assert len(agent.calls) == 1 and result["categoria"] == "conversazione"
    warning = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warning[0].getMessage() == (
        "router: risposta non utilizzabile (JSON non valido), la domanda passa all'agente: boh\\nnon so"
    )
    assert "router → agente" in caplog.text


def test_router_messages_stay_out_of_history():
    agent = ScriptedModel([AIMessage("ok")])
    result = build_graph(agent, router=router_says("conversazione")).invoke(start("d"))
    assert [m.type for m in agent.calls[0]] == ["human"]
    assert [m.type for m in result["messages"]] == ["human", "ai"]


def test_tool_cycle_works_after_router():
    model = tokyo_scenario()
    result = build_graph(model, [clock], router=router_says("conversazione")).invoke(start("ora a Tokyo?"))
    assert result["messages"][-1].content == "Sono le 01:05"


def test_limit_works_after_router():
    loop = AIMessage("", tool_calls=[call("get_current_time", {}, "c1")])
    model = ScriptedModel([loop, AIMessage("", tool_calls=[call("get_current_time", {}, "c2")])])
    result = build_graph(model, [clock], max_tool_steps=1, router=router_says("conversazione")).invoke(start())
    assert result["messages"][-1].content == LIMIT_REPLY.format(max_tool_steps=1)


def test_refusal_then_in_scope_question():
    agent = ScriptedModel([AIMessage("Sono le 01:05")])
    graph = build_graph(agent, router=router_says("fuori_ambito", "conversazione"))
    history, first = ask(graph, new_history(), "ricetta?")
    history, second = ask(graph, history, "Che ore sono a Tokyo?")
    assert (first, second) == (REFUSAL_REPLY, "Sono le 01:05")
    assert [m.type for m in agent.calls[0]] == ["system", "human", "ai", "human"]
    assert agent.calls[0][2].content == REFUSAL_REPLY


OK = '{"coerente": true, "motivo": ""}'
NO = '{"coerente": false, "motivo": "manca il calcolo."}'
HINT = REVIEW_HINT.format(motivo="manca il calcolo.")


def reviewer_says(*replies):
    model = ScriptedModel([AIMessage(r) for r in replies])
    return Reviewer(model), model


def warnings(caplog):
    return [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]


def test_graph_nodes_with_reviewer():
    nodes = set(build_graph(ScriptedModel([]), [clock], reviewer=reviewer_says()[0]).get_graph().nodes)
    assert {"agente", "strumenti", "limite", "revisore"} <= nodes


def test_graph_without_reviewer_has_no_reviewer_node():
    assert "revisore" not in build_graph(ScriptedModel([]), [clock]).get_graph().nodes


def test_coherent_answer_is_approved_first_time(caplog):
    caplog.set_level(logging.INFO)
    agent = ScriptedModel([AIMessage("risposta")])
    reviewer, review_model = reviewer_says(OK)
    result = build_graph(agent, reviewer=reviewer).invoke(start())
    assert len(agent.calls) == 1 and len(review_model.calls) == 1
    assert [m.type for m in result["messages"]] == ["human", "ai"]
    assert result["esito_revisione"] == "approvata"
    assert "revisore: coerente=sì motivo=" in caplog.text and "revisore → END" in caplog.text
    assert "tolti" not in caplog.text


def test_partial_answer_is_rejected_then_completed(caplog):
    caplog.set_level(logging.INFO)
    partial, complete = "A Tokyo sono le 01:05.", "A Tokyo sono le 01:05 e 15 per 4 fa 60."
    agent = ScriptedModel([AIMessage(partial), AIMessage(complete)])
    reviewer, review_model = reviewer_says(NO, OK)
    result = build_graph(agent, reviewer=reviewer).invoke(start())
    retry = agent.calls[1]
    assert [m.type for m in retry[-2:]] == ["ai", "human"]
    assert (retry[-2].content, retry[-1].content) == (partial, HINT)
    assert [m.type for m in result["messages"]] == ["human", "ai"]
    assert result["messages"][-1].content == complete and result["revisioni"] == 1
    assert "revisore: coerente=no motivo=manca il calcolo." in caplog.text
    assert "revisore → agente (revisione 1 di 1)" in caplog.text
    assert "revisore: tolti 2 messaggi dalla cronologia" in caplog.text
    second_review = review_model.calls[1][1].content
    assert "Domanda dell'utente:\nx\n" in second_review and second_review.endswith(complete)


@pytest.mark.parametrize("max_revisions, chiamate, tolti", [(1, 2, 2), (2, 3, 4)])
def test_reviewer_always_rejecting_respects_limit(caplog, max_revisions, chiamate, tolti):
    caplog.set_level(logging.INFO)
    agent = ScriptedModel([AIMessage(f"b{i}") for i in range(1, chiamate + 1)])
    reviewer, review_model = reviewer_says(*[NO] * chiamate)
    result = build_graph(agent, reviewer=reviewer, max_revisions=max_revisions).invoke(start())
    assert len(agent.calls) == chiamate and len(review_model.calls) == chiamate
    assert [m.type for m in result["messages"]] == ["human", "ai"]
    assert result["messages"][-1].content == f"b{chiamate}"
    assert result["esito_revisione"] == "limite"
    assert (
        f"revisore: limite di revisioni raggiunto ({max_revisions}), restituita l'ultima risposta"
        in warnings(caplog)
    )
    assert f"revisore: tolti {tolti} messaggi dalla cronologia" in caplog.text


def test_unusable_reviewer_reply_approves_answer(caplog):
    caplog.set_level(logging.INFO)
    agent = ScriptedModel([AIMessage("risposta")])
    result = build_graph(agent, reviewer=reviewer_says("boh")[0]).invoke(start())
    assert result["messages"][-1].content == "risposta" and result["esito_revisione"] == "approvata"
    assert "revisore: risposta non utilizzabile (JSON non valido), risposta approvata: boh" in warnings(caplog)


def test_reviewer_server_error_approves_answer(caplog):
    caplog.set_level(logging.INFO)
    agent = ScriptedModel([AIMessage("risposta")])
    down = openai.APIConnectionError(request=httpx.Request("POST", "http://x"))
    result = build_graph(agent, reviewer=Reviewer(ScriptedModel([down]))).invoke(start())
    assert result["messages"][-1].content == "risposta" and result["esito_revisione"] == "approvata"
    assert any("errore del server" in w for w in warnings(caplog))


def test_refusal_skips_reviewer():
    review_model = ScriptedModel([])
    graph = build_graph(ScriptedModel([]), router=router_says("fuori_ambito"), reviewer=Reviewer(review_model))
    result = graph.invoke(start("ricetta?"))
    assert review_model.calls == [] and result["messages"][-1].content == REFUSAL_REPLY


def test_limit_skips_reviewer():
    review_model = ScriptedModel([])
    graph = build_graph(always_tool(2), [clock], max_tool_steps=1, reviewer=Reviewer(review_model))
    result = graph.invoke(start())
    assert review_model.calls == []
    assert result["messages"][-1].content == LIMIT_REPLY.format(max_tool_steps=1)


def test_limit_after_rejection_cleans_history(caplog):
    caplog.set_level(logging.INFO)
    agent = ScriptedModel([
        AIMessage("bozza"),
        AIMessage("", tool_calls=[call("get_current_time", {}, "c1")]),
        AIMessage("", tool_calls=[call("get_current_time", {}, "c2")]),
    ])
    graph = build_graph(agent, [clock], max_tool_steps=1, reviewer=reviewer_says(NO)[0])
    messages = graph.invoke(start())["messages"]
    assert not any(m.content == "bozza" or m.text.startswith("Indicazione del revisore") for m in messages)
    skipped, reply = messages[-2], messages[-1]
    assert isinstance(skipped, ToolMessage) and skipped.tool_call_id == "c2" and skipped.content == TOOL_SKIPPED
    assert reply.content == LIMIT_REPLY.format(max_tool_steps=1)
    assert "revisore: tolti 2 messaggi dalla cronologia" in caplog.text


def test_tool_pairs_of_rejected_attempt_are_kept():
    agent = ScriptedModel([
        AIMessage("", tool_calls=[call("get_current_time", {"city": "Tokyo"}, "c1")]),
        AIMessage("bozza"),
        AIMessage("completa"),
    ])
    result = build_graph(agent, [clock], reviewer=reviewer_says(NO, OK)[0]).invoke(start())
    assert [m.type for m in result["messages"]] == ["human", "ai", "tool", "ai"]
    assert result["messages"][-1].content == "completa"


def test_next_turn_sees_no_drafts():
    router_model = ScriptedModel([
        AIMessage(json.dumps({"categoria": "conversazione", "motivo": "m"})) for _ in range(2)
    ])
    agent = ScriptedModel([AIMessage("bozza"), AIMessage("completa"), AIMessage("seconda")])
    graph = build_graph(agent, router=Router(router_model, "ambito"), reviewer=reviewer_says(NO, OK, OK)[0])
    history, _ = ask(graph, new_history(), "prima domanda")
    ask(graph, history, "seconda domanda")
    for text in (router_model.calls[1][1].content, " ".join(m.text for m in agent.calls[-1])):
        assert "bozza" not in text and "Indicazione del revisore" not in text


def test_draft_with_reused_id_keeps_final_answer():
    agent = ScriptedModel([AIMessage("bozza", id="dup"), AIMessage("completa", id="dup")])
    result = build_graph(agent, reviewer=reviewer_says(NO, OK)[0]).invoke(start())
    assert [m.type for m in agent.calls[1][-2:]] == ["ai", "human"]
    assert (agent.calls[1][-2].content, agent.calls[1][-1].content) == ("bozza", HINT)
    assert [m.type for m in result["messages"]] == ["human", "ai"]
    assert result["messages"][-1].content == "completa"
