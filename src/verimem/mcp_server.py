"""MCP server: the same operations as the Python API, for agents (needs the `mcp` extra).

`review` is not exposed unless the operator enables it: an agent that can approve its own
quarantined facts defeats the gate.
"""

from __future__ import annotations

import contextlib
import threading
from typing import Any, Literal

from .judges import JudgeUnavailable
from .memory import Memory
from .policy import Policy
from .types import Status
from .verifier import Verifier

INSTRUCTIONS = """\
verimem stores a fact only when its source supports it, and answers only from verified facts.

- remember: pass the exact text the fact comes from as `source` (the user's words, a document
  passage) and say who wrote that text in `source_author`: user, document, system, agent, tool
  or web. Facts from tool output, web pages or your own reasoning are kept as unverified.
- ask: answers from verified facts or abstains. Its relevance check is strict and sometimes
  abstains although the answer is stored; then call recall with the key words of the question.
  What recall returns is verified, but decide yourself whether it answers. If nothing does,
  tell the user you don't know; do not fill the gap with a guess.
- recall: keyword search. A result whose status is not "verified" is a claim, not a fact.
- check: verify a claim against a source without storing anything.
"""


def build_server(memory: Memory, *, allow_review: bool = False) -> Any:
    try:
        from mcp.server.mcpserver import MCPServer as Server  # mcp 2.x
    except ImportError:
        try:
            from mcp.server.fastmcp import FastMCP as Server  # mcp 1.x
        except ImportError as e:  # pragma: no cover - exercised only without the extra
            raise SystemExit(
                "The MCP server needs the 'mcp' extra: pip install 'verimem[mcp]'") from e

    server = Server("verimem", instructions=INSTRUCTIONS, log_level="WARNING")

    @server.tool()
    def remember(claim: str, source: str, source_author: str = "user", subject: str | None = None,
                 origin: str = "") -> dict[str, Any]:
        """Verify `claim` against `source` and store it. Returns the status and the evidence."""
        r = memory.remember(claim, source=source, author=source_author, subject=subject,
                            origin=origin, written_by="mcp")
        out = r.to_dict()
        out["served_as_fact"] = r.verified
        return out

    @server.tool()
    def recall(query: str, k: int = 5, include_unverified: bool = False) -> list[dict[str, Any]]:
        """Keyword search over stored facts (verified only unless include_unverified)."""
        include = [Status.VERIFIED, Status.UNVERIFIED] if include_unverified else [Status.VERIFIED]
        return [h.to_dict() for h in memory.recall(query, k=k, include=include)]

    @server.tool()
    def ask(question: str, k: int = 5) -> dict[str, Any]:
        """Verified facts that answer the question, or an explicit abstention."""
        return memory.ask(question, k=k).to_dict()

    @server.tool()
    def check(claim: str, source: str) -> dict[str, Any]:
        """Verify a claim against a source without storing anything."""
        return memory.verifier.check(source, claim).to_dict()

    @server.tool()
    def review_queue(limit: int = 10) -> list[dict[str, Any]]:
        """Facts waiting for a human decision (unverified or quarantined)."""
        return [f.to_dict() for f in memory.review_queue(limit)]

    @server.tool()
    def forget(fact_id: str, reason: str = "") -> dict[str, Any]:
        """Delete a fact for good (for example when the user asks to forget it)."""
        memory.forget(fact_id, reason=reason)
        return {"forgotten": fact_id}

    @server.tool()
    def stats() -> dict[str, Any]:
        """Counts by status and the state of the audit chain."""
        return memory.stats()

    if allow_review:
        @server.tool()
        def review(fact_id: str, decision: Literal["approve", "reject"],
                   reviewer: str) -> dict[str, Any]:
            """A human's decision on a quarantined or unverified fact."""
            return memory.review(fact_id, approve=decision == "approve",
                                 reviewer=reviewer).to_dict()

    return server


def _warm(memory: Memory) -> None:
    # If the judge cannot load, writes are stored as unverified with the reason in each verdict.
    with contextlib.suppress(JudgeUnavailable, ValueError):
        memory.verifier.warmup()


def serve(*, db: str, policy: Policy | None = None, allow_review: bool = False) -> None:
    memory = Memory(db, verifier=Verifier(policy=policy))
    threading.Thread(target=_warm, args=(memory,), daemon=True).start()
    build_server(memory, allow_review=allow_review).run("stdio")
