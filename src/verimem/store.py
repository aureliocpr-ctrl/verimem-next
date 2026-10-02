"""SQLite storage. All SQL lives here; `Memory` decides, `Store` persists."""

from __future__ import annotations

import json
import secrets
import sqlite3
import threading
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .text import content_tokens, words

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS sources (
    id          TEXT PRIMARY KEY,           -- sha256 of the whitespace-normalised text
    text        TEXT,                       -- NULL once every fact using it is forgotten
    origin      TEXT NOT NULL DEFAULT '',
    author      TEXT NOT NULL,
    observed_at TEXT,
    created_at  TEXT NOT NULL,
    meta        TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS facts (
    rowid         INTEGER PRIMARY KEY,
    id            TEXT NOT NULL UNIQUE,
    text          TEXT NOT NULL,
    norm          TEXT NOT NULL,            -- normalised text, for duplicate detection
    subject       TEXT,
    status        TEXT NOT NULL,
    reason        TEXT NOT NULL DEFAULT '',  -- why the fact has its status
    label         TEXT NOT NULL,
    support       REAL NOT NULL,
    verdict       TEXT NOT NULL,            -- Verdict.to_dict() as JSON
    source_id     TEXT REFERENCES sources(id),
    written_by    TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL,
    valid_from    TEXT,
    superseded_by TEXT,
    superseded_at TEXT,
    reviewed_by   TEXT,
    meta          TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS facts_status  ON facts(status);
CREATE INDEX IF NOT EXISTS facts_subject ON facts(subject);
CREATE INDEX IF NOT EXISTS facts_norm    ON facts(norm);

CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
    text, content='facts', content_rowid='rowid',
    tokenize='porter unicode61 remove_diacritics 2'
);
CREATE TRIGGER IF NOT EXISTS facts_ai AFTER INSERT ON facts BEGIN
    INSERT INTO facts_fts(rowid, text) VALUES (new.rowid, new.text);
END;
CREATE TRIGGER IF NOT EXISTS facts_ad AFTER DELETE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, text) VALUES ('delete', old.rowid, old.text);
END;
CREATE TRIGGER IF NOT EXISTS facts_au AFTER UPDATE OF text ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, text) VALUES ('delete', old.rowid, old.text);
    INSERT INTO facts_fts(rowid, text) VALUES (new.rowid, new.text);
END;

CREATE TABLE IF NOT EXISTS events (
    seq       INTEGER PRIMARY KEY,
    ts        TEXT NOT NULL,
    kind      TEXT NOT NULL,
    fact_id   TEXT,
    payload   TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    hash      TEXT NOT NULL
);
"""

FACT_COLUMNS = ("id", "text", "norm", "subject", "status", "reason", "label", "support",
                "verdict",
                "source_id", "written_by", "created_at", "valid_from", "superseded_by",
                "superseded_at", "reviewed_by", "meta")


def new_id() -> str:
    """Time-ordered identifier: 12 hex digits of milliseconds + 10 random hex digits."""
    return f"{int(time.time() * 1000):012x}{secrets.token_hex(5)}"


def normalize_fact(text: str) -> str:
    return " ".join(words(text))


def fts_query(text: str) -> str:
    """A safe FTS5 query: content words OR-ed, plus a prefix for long words so that
    inflected forms ("consegnato"/"consegnati") still meet."""
    toks = sorted(content_tokens(text)) or sorted(set(words(text)))
    terms: list[str] = []
    for t in toks:
        terms.append(f'"{t}"')
        if len(t) >= 6 and t.isalpha():
            terms.append(f'"{t[: len(t) - 2]}"*')
    return " OR ".join(terms)


class Store:
    """A thread-safe SQLite store. Use `transaction()` for every write."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA busy_timeout = 5000")
        self._conn.execute("PRAGMA secure_delete = ON")  # deleted text is overwritten on disk
        if self.path != ":memory:":
            self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.executescript(_SCHEMA)
        with self.transaction() as c:
            c.execute("INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', ?)",
                      (str(SCHEMA_VERSION),))
            c.execute("INSERT OR IGNORE INTO meta(key, value) VALUES ('store_id', ?)", (new_id(),))
            c.execute("INSERT OR IGNORE INTO meta(key, value) VALUES ('hash_key', ?)",
                      (secrets.token_hex(32),))
        version = int(self.meta("schema_version") or 0)
        if version != SCHEMA_VERSION:
            raise RuntimeError(f"store schema v{version} is not supported (expected "
                               f"v{SCHEMA_VERSION}); upgrade verimem or migrate the store")

    # ------------------------------------------------------------ plumbing
    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            self._conn.execute("COMMIT")

    def read(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def meta(self, key: str) -> str | None:
        rows = self.read("SELECT value FROM meta WHERE key = ?", (key,))
        return rows[0]["value"] if rows else None

    def purge(self) -> None:
        """Make deletions physical: merge the full-text index (dropping deleted entries) and
        truncate the write-ahead log, which still holds old page images."""
        with self._lock:
            self._conn.execute("INSERT INTO facts_fts(facts_fts) VALUES ('optimize')")
            if self.path != ":memory:":
                self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ------------------------------------------------------------ sources
    @staticmethod
    def put_source(c: sqlite3.Connection, *, source_id: str, text: str, origin: str, author: str,
                   observed_at: str | None, created_at: str, meta: dict[str, Any]) -> None:
        c.execute(
            "INSERT INTO sources(id, text, origin, author, observed_at, created_at, meta) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
            "text = COALESCE(sources.text, excluded.text)",
            (source_id, text, origin, author, observed_at, created_at, json.dumps(meta)),
        )

    def get_source(self, source_id: str) -> sqlite3.Row | None:
        rows = self.read("SELECT * FROM sources WHERE id = ?", (source_id,))
        return rows[0] if rows else None

    # ------------------------------------------------------------ facts
    @staticmethod
    def insert_fact(c: sqlite3.Connection, row: dict[str, Any]) -> None:
        cols = ", ".join(FACT_COLUMNS)
        marks = ", ".join("?" for _ in FACT_COLUMNS)
        c.execute(f"INSERT INTO facts({cols}) VALUES ({marks})",
                  [row.get(k) for k in FACT_COLUMNS])

    @staticmethod
    def update_fact(c: sqlite3.Connection, fact_id: str, **fields: Any) -> None:
        bad = set(fields) - set(FACT_COLUMNS)
        if bad:
            raise ValueError(f"unknown fact columns: {sorted(bad)}")
        sets = ", ".join(f"{k} = ?" for k in fields)
        c.execute(f"UPDATE facts SET {sets} WHERE id = ?", [*fields.values(), fact_id])

    _FACT_SELECT = ("SELECT f.*, s.origin AS source_origin, s.author AS source_author "
                    "FROM facts f LEFT JOIN sources s ON s.id = f.source_id")

    def get_fact(self, fact_id: str) -> sqlite3.Row | None:
        rows = self.read(f"{self._FACT_SELECT} WHERE f.id = ?", (fact_id,))
        return rows[0] if rows else None

    def facts_where(self, where: str, params: Sequence[Any] = (), *, order: str = "f.rowid",
                    limit: int = -1) -> list[sqlite3.Row]:
        return self.read(f"{self._FACT_SELECT} WHERE {where} ORDER BY {order} LIMIT ?",
                         (*params, limit))

    def search(self, query: str, statuses: Sequence[str],
               limit: int) -> list[tuple[sqlite3.Row, float]]:
        q = fts_query(query)
        if not q or not statuses:
            return []
        marks = ", ".join("?" for _ in statuses)
        rows = self.read(
            f"SELECT f.*, s.origin AS source_origin, s.author AS source_author, "
            f"bm25(facts_fts) AS rank FROM facts_fts "
            f"JOIN facts f ON f.rowid = facts_fts.rowid "
            f"LEFT JOIN sources s ON s.id = f.source_id "
            f"WHERE facts_fts MATCH ? AND f.status IN ({marks}) ORDER BY rank LIMIT ?",
            (q, *statuses, limit),
        )
        return [(r, -float(r["rank"])) for r in rows]

    def count_by_status(self) -> dict[str, int]:
        return {r["status"]: r["n"] for r in
                self.read("SELECT status, COUNT(*) AS n FROM facts GROUP BY status")}

    def count(self, table: str) -> int:
        if table not in {"facts", "sources", "events"}:
            raise ValueError(table)
        return int(self.read(f"SELECT COUNT(*) AS n FROM {table}")[0]["n"])
