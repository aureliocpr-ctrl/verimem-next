"""Tamper-evident audit log: every event is chained to the previous one by a SHA-256 hash.

Payloads carry hashes and metadata, never raw text, so the chain survives `forget`
intact and can be exported without leaking memory contents (DESIGN.md §3, invariant 7).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from .store import Store

GENESIS = "0" * 64


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _link(prev: str, seq: int, ts: str, kind: str, fact_id: str | None, payload: str) -> str:
    material = f"{prev}|{seq}|{ts}|{kind}|{fact_id or ''}|{payload}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ChainCheck:
    ok: bool
    events: int
    first_bad: int | None = None
    reason: str = ""


class AuditLog:
    def __init__(self, store: Store) -> None:
        self.store = store

    def append(self, c: sqlite3.Connection, *, ts: str, kind: str, fact_id: str | None,
               payload: dict[str, Any]) -> str:
        """Append an event inside the caller's transaction and return its hash."""
        last = c.execute("SELECT seq, hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        seq, prev = (last["seq"] + 1, last["hash"]) if last else (1, GENESIS)
        body = _canonical(payload)
        h = _link(prev, seq, ts, kind, fact_id, body)
        c.execute("INSERT INTO events(seq, ts, kind, fact_id, payload, prev_hash, hash) "
                  "VALUES (?, ?, ?, ?, ?, ?, ?)", (seq, ts, kind, fact_id, body, prev, h))
        return h

    def verify(self) -> ChainCheck:
        prev, n = GENESIS, 0
        for row in self.store.read("SELECT * FROM events ORDER BY seq"):
            n += 1
            if row["seq"] != n:
                return ChainCheck(False, n, row["seq"], f"gap in sequence before {row['seq']}")
            if row["prev_hash"] != prev:
                return ChainCheck(False, n, row["seq"], "previous hash does not match")
            expected = _link(prev, row["seq"], row["ts"], row["kind"], row["fact_id"],
                             row["payload"])
            if row["hash"] != expected:
                return ChainCheck(False, n, row["seq"], "event content was altered")
            prev = row["hash"]
        return ChainCheck(True, n)

    def head(self) -> str:
        rows = self.store.read("SELECT hash FROM events ORDER BY seq DESC LIMIT 1")
        return rows[0]["hash"] if rows else GENESIS

    def tail(self, n: int = 20) -> list[dict[str, Any]]:
        rows = self.store.read("SELECT * FROM events ORDER BY seq DESC LIMIT ?", (n,))
        return [self._as_dict(r) for r in reversed(rows)]

    def export(self, dest: str | Path | TextIO) -> int:
        """Write the whole chain as JSON lines; returns the number of events."""
        rows = self.store.read("SELECT * FROM events ORDER BY seq")
        lines = [json.dumps(self._as_dict(r), ensure_ascii=False) + "\n" for r in rows]
        if isinstance(dest, (str, Path)):
            Path(dest).write_text("".join(lines), encoding="utf-8")
        else:
            dest.writelines(lines)
        return len(rows)

    @staticmethod
    def _as_dict(r: sqlite3.Row) -> dict[str, Any]:
        return {"seq": r["seq"], "ts": r["ts"], "kind": r["kind"], "fact_id": r["fact_id"],
                "payload": json.loads(r["payload"]), "prev_hash": r["prev_hash"],
                "hash": r["hash"]}
