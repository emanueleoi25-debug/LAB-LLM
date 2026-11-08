import asyncio
import sys
import time

import pytest
from mcp import Client, StdioServerParameters
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from assistente.mcp_client import MCPStartupError, load_mcp_tools

HINT = "Coda di prova."

fake = MCPServer("finto", log_level="WARNING")


@fake.tool(description="Ripete il testo.")
def echo(text: str) -> str:
    return text


@fake.tool(description="Fallisce in modo previsto.")
def fail() -> str:
    raise ToolError("andato storto")


@fake.tool(description="Fallisce in modo imprevisto.")
def crash() -> str:
    raise RuntimeError("segreto")


@fake.tool(description="Non risponde in tempo.")
async def slow() -> str:
    await asyncio.sleep(5)
    return "tardi"


def tools_of(**kwargs):
    return {t.name: t for t in load_mcp_tools(fake, HINT, **kwargs)}


def test_tools_mirror_server():
    async def run():
        async with Client(fake) as client:
            return (await client.list_tools()).tools

    declared = {t.name: t for t in asyncio.run(run())}
    tools = tools_of()
    assert list(tools) == list(declared) == ["echo", "fail", "crash", "slow"]
    for name, tool in tools.items():
        assert tool.description == declared[name].description
        assert tool.args_schema == declared[name].input_schema
    assert tools["echo"].args_schema["required"] == ["text"]


def test_text_result():
    assert tools_of()["echo"].invoke({"text": "ciao è"}) == "ciao è"


def test_tool_error_prefix_removed():
    assert tools_of()["fail"].invoke({}) == "Errore: andato storto"


def test_crash_is_failure():
    text = tools_of()["crash"].invoke({})
    assert text == "Errore: server MCP non disponibile (errore interno del server). Coda di prova."
    assert "segreto" not in text


def test_timeout_during_call():
    start = time.monotonic()
    text = tools_of(timeout=0.5)["slow"].invoke({})
    assert text == "Errore: server MCP non disponibile (nessuna risposta entro 0.5 s). Coda di prova."
    assert time.monotonic() - start < 3


def test_label_in_failure_text():
    text = tools_of(label="server delle note")["crash"].invoke({})
    assert text.startswith("Errore: server delle note non disponibile (")


def test_startup_server_exits():
    params = StdioServerParameters(command=sys.executable, args=["-c", "import sys; sys.exit(3)"])
    with pytest.raises(MCPStartupError):
        load_mcp_tools(params, HINT)


def test_startup_server_hangs():
    params = StdioServerParameters(command=sys.executable, args=["-c", "import time; time.sleep(30)"])
    start = time.monotonic()
    with pytest.raises(MCPStartupError, match=r"^nessuna risposta entro 1 s$"):
        load_mcp_tools(params, HINT, timeout=1)
    assert time.monotonic() - start < 10


def test_startup_missing_command():
    params = StdioServerParameters(command="comando-che-non-esiste")
    with pytest.raises(MCPStartupError) as info:
        load_mcp_tools(params, HINT)
    message = str(info.value)
    assert message.strip()
    assert "TaskGroup" not in message
