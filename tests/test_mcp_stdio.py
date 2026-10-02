"""The MCP server as a client sees it: a real `verimem mcp` process over stdio."""

import asyncio
import json
import sys

import pytest

pytest.importorskip("mcp")

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def session_run(db: str) -> tuple[list[str], dict]:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "verimem.cli", "mcp", "--db", db, "--judge", "lexical"])
    async with stdio_client(params) as (read, write), ClientSession(read, write) as s:
        await s.initialize()
        tools = sorted(t.name for t in (await s.list_tools()).tools)
        out = await s.call_tool("remember", {"claim": "Maria moved to Milan.",
                                             "source": "Maria moved from Rome to Milan.",
                                             "source_author": "user"})
        return tools, json.loads(out.content[0].text)


def test_the_server_starts_lists_its_tools_and_stores(tmp_path):
    tools, stored = asyncio.run(session_run(str(tmp_path / "m.db")))
    assert tools == ["ask", "check", "forget", "recall", "remember", "review_queue", "stats"]
    # The lexical judge can never verify: the fact is kept, but not served as a fact.
    assert stored["status"] == "unverified" and stored["served_as_fact"] is False
