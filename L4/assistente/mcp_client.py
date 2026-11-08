"""Client MCP generico: strumenti dichiarati da un server MCP, offerti al grafo come BaseTool.

Una sessione per chiamata: ogni strumento esegue `asyncio.run(...)`, che avvia il server (per
stdio, un sottoprocesso), apre la sessione, chiama lo strumento e chiude tutto. L'asincronia
dell'SDK `mcp` resta qui dentro: verso il grafo gli strumenti sono sincroni e non sollevano
eccezioni (ogni problema diventa un testo che inizia con `Errore: `), tranne KeyboardInterrupt.
"""

import asyncio
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from mcp import Client, StdioServerParameters
from mcp.server.mcpserver import MCPServer

# Testo che l'SDK antepone ai messaggi dei ToolError sollevati dal server.
TOOL_ERROR_PREFIX = "Error executing tool {name}: "
INTERNAL_ERROR = "errore interno del server"


class MCPStartupError(Exception):
    """Il server non ha fornito l'elenco degli strumenti; il messaggio è il motivo."""


def _leaf(exc: BaseException) -> BaseException:
    """Prima eccezione foglia di un eventuale gruppo (anyio raggruppa gli errori dei task)."""
    while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        exc = exc.exceptions[0]
    return exc


def _reason(exc: BaseException, timeout: float) -> str:
    exc = _leaf(exc)
    if isinstance(exc, TimeoutError):
        return f"nessuna risposta entro {timeout:g} s"
    lines = str(exc).strip().splitlines()
    return lines[0] if lines else type(exc).__name__


async def _session(server: Any, timeout: float, action):
    async with asyncio.timeout(timeout):
        async with Client(server) as client:
            return await action(client)


def load_mcp_tools(
    server: StdioServerParameters | MCPServer,
    failure_hint: str,
    label: str = "server MCP",
    timeout: float = 10.0,
) -> list[BaseTool]:
    """Legge `list_tools` e crea uno strumento sincrono per ciascuno.

    `server` è ciò che accetta `mcp.Client`: parametri stdio oppure, nei test, un `MCPServer`
    collegato in-process. `label` e `failure_hint` compongono il testo dei guasti.
    """
    try:
        declared = asyncio.run(_session(server, timeout, lambda c: c.list_tools())).tools
    except Exception as exc:
        raise MCPStartupError(_reason(exc, timeout)) from exc

    def failure(reason: str) -> str:
        return f"Errore: {label} non disponibile ({reason}). {failure_hint}"

    def make(name: str):
        prefix = TOOL_ERROR_PREFIX.format(name=name)

        def run(**arguments: Any) -> str:
            try:
                result = asyncio.run(
                    _session(server, timeout, lambda c: c.call_tool(name, arguments))
                )
            except Exception as exc:
                return failure(_reason(exc, timeout))
            text = "\n".join(b.text for b in result.content if hasattr(b, "text"))
            if not result.is_error:
                return text if text else failure(INTERNAL_ERROR)
            if text.startswith(prefix):
                return f"Errore: {text[len(prefix):]}"
            return failure(INTERNAL_ERROR)

        return run

    return [
        StructuredTool.from_function(
            func=make(t.name), name=t.name, description=t.description or "", args_schema=t.input_schema
        )
        for t in declared
    ]
