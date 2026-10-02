import asyncio
import json

import pytest

from conftest import FakeJudge, make_policy
from verimem.memory import Memory
from verimem.verifier import Verifier

pytest.importorskip("mcp")

from verimem.mcp_server import build_server

SRC = "Maria told us she moved from Rome to Milan in 2021 for a job at a bank."


def call(server, tool, **args):
    result = asyncio.run(server.call_tool(tool, args))
    if hasattr(result, "content"):  # mcp 2.x: a CallToolResult
        content = result.content
    else:  # mcp 1.x: content, or (content, structured)
        content = result[0] if isinstance(result, tuple) else result
    return json.loads(content[0].text) if content else None


def memory() -> Memory:
    return Memory(verifier=Verifier(judge=FakeJudge(), policy=make_policy()))


def test_tools_listed_without_review_by_default():
    names = {t.name for t in asyncio.run(build_server(memory()).list_tools())}
    assert {"remember", "recall", "ask", "check", "review_queue", "forget", "stats"} <= names
    assert "review" not in names
    names = {t.name for t in asyncio.run(build_server(memory(), allow_review=True).list_tools())}
    assert "review" in names


def test_remember_and_recall_through_mcp():
    server = build_server(memory())
    out = call(server, "remember", claim="Maria moved to Milan in 2021.", source=SRC,
               source_author="user")
    assert out["status"] == "verified" and out["served_as_fact"] is True
    bad = call(server, "remember", claim="Maria is a financial analyst.", source=SRC,
               source_author="user")
    assert bad["status"] == "quarantined" and bad["served_as_fact"] is False
    web = call(server, "remember", claim="Maria moved to Milan.", source=SRC,
               source_author="web")
    assert web["status"] == "unverified"
    hits = call(server, "recall", query="Maria Milan")
    assert [h["text"] for h in (hits if isinstance(hits, list) else [hits])] == [
        "Maria moved to Milan in 2021."]


def test_remember_must_be_told_who_wrote_the_source():
    # A default author would make web text the agent forgot to label count as the user's.
    tools = {t.name: t for t in asyncio.run(build_server(memory()).list_tools())}
    schema = tools["remember"].inputSchema
    assert "source_author" in schema["required"]
    assert set(schema["properties"]["source_author"]["enum"]) == {
        "user", "document", "system", "agent", "tool", "web"}


def test_check_does_not_store():
    m = memory()
    server = build_server(m)
    v = call(server, "check", claim="Maria moved to Milan in 2021.", source=SRC)
    assert v["label"] == "supported"
    assert m.stats()["facts"] == {}
