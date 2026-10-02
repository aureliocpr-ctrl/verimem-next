"""The memory: one write path, one read path (ADR-0003), verified that fails closed (ADR-0004)."""

from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .audit import AuditLog
from .judges import JudgeUnavailable
from .policy import Policy
from .relevance import NLIRelevance, Relevance
from .store import Store, new_id, normalize_fact
from .text import normalize_ws
from .types import Answer, Author, Fact, Label, Recalled, Status, Verdict, WriteResult
from .verifier import Verifier

_REVIEWABLE = (Status.UNVERIFIED, Status.QUARANTINED, Status.REJECTED)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def to_utc_iso(value: str | datetime | None) -> str | None:
    """Normalise a timestamp to UTC ISO-8601 (naive values are taken as UTC)."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as e:
            raise ValueError(f"not an ISO-8601 timestamp: {value!r}") from e
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    iso = value.astimezone(timezone.utc).isoformat(timespec="microseconds")
    return iso.replace("+00:00", "Z")


def status_for(verdict: Verdict, *, trusted_source: bool,
               judge_is_model: bool) -> tuple[Status, str]:
    """The only mapping from a verdict to a stored status (ADR-0003, ADR-0004)."""
    if verdict.label is Label.SUPPORTED:
        if not judge_is_model:
            return Status.UNVERIFIED, "a heuristic judge cannot verify a fact"
        if not trusted_source:
            return Status.UNVERIFIED, "the source's author is not trusted to verify facts"
        return Status.VERIFIED, verdict.reason
    if verdict.label in (Label.NOT_SUPPORTED, Label.CONTRADICTED):
        return Status.QUARANTINED, verdict.reason
    return Status.UNVERIFIED, verdict.reason


@dataclass(frozen=True)
class Item:
    """One candidate memory for `remember_many`."""

    claim: str
    source: str | None = None
    author: str = "user"
    origin: str = ""
    subject: str | None = None
    observed_at: str | datetime | None = None
    written_by: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


class Memory:
    """Verified memory backed by a SQLite file (or ``":memory:"``)."""

    def __init__(self, path: str | Path = ":memory:", *, verifier: Verifier | None = None,
                 policy: Policy | None = None, relevance: Relevance | None = None,
                 clock: Callable[[], str] = utcnow) -> None:
        if verifier is not None and policy is not None and policy is not verifier.policy:
            raise ValueError("pass either a verifier or a policy, not both")
        self.verifier = verifier or Verifier(policy=policy)
        self.policy = self.verifier.policy
        self.store = Store(path)
        self.audit = AuditLog(self.store)
        self._relevance = relevance
        self._clock = clock
        self._key = bytes.fromhex(self.store.meta("hash_key") or "")

    # ------------------------------------------------------------ lifecycle
    def close(self) -> None:
        self.store.close()

    def __enter__(self) -> Memory:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @property
    def relevance(self) -> Relevance:
        if self._relevance is None:
            self._relevance = NLIRelevance(self.verifier.judge, self.policy.relevance_templates)
        return self._relevance

    # ------------------------------------------------------------ write path
    def remember(self, claim: str, *, source: str | None = None, author: str = "user",
                 origin: str = "", subject: str | None = None,
                 observed_at: str | datetime | None = None, written_by: str = "",
                 meta: dict[str, Any] | None = None) -> WriteResult:
        """Verify `claim` against `source` and store it with the resulting status."""
        item = Item(claim, source, author, origin, subject, observed_at, written_by, meta or {})
        return self.remember_many([item])[0]

    def remember_many(self, items: Sequence[Item]) -> list[WriteResult]:
        """Like `remember`, verifying all items with one batched judge call."""
        prepared = []
        for it in items:
            claim = normalize_ws(it.claim or "")
            if not claim:
                raise ValueError("claim is empty")
            author = Author(it.author).value  # raises ValueError on an unknown author
            prepared.append((it, claim, author, to_utc_iso(it.observed_at)))
        verdicts = self.verifier.check_many([(it.source, claim) for it, claim, _, _ in prepared])
        judge_is_model = self._judge_is_model()
        results = []
        for (it, claim, author, observed), verdict in zip(prepared, verdicts, strict=True):
            trusted = author in self.policy.trusted_authors
            status, reason = status_for(verdict, trusted_source=trusted,
                                        judge_is_model=judge_is_model)
            results.append(self._store_one(it, claim, author, observed, verdict, status, reason))
        return results

    def _store_one(self, it: Item, claim: str, author: str, observed: str | None,
                   verdict: Verdict, status: Status, reason: str) -> WriteResult:
        now = self._clock()
        with self.store.transaction() as c:
            source_id = None
            if it.source and it.source.strip():
                source_id = self._hash(normalize_ws(it.source))
                Store.put_source(c, source_id=source_id, text=it.source, origin=it.origin,
                                 author=author, observed_at=observed, created_at=now, meta={})
            norm = normalize_fact(claim)
            if status is Status.VERIFIED:
                dup = c.execute("SELECT id FROM facts WHERE norm = ? AND status = 'verified' "
                                "AND subject IS ? LIMIT 1", (norm, it.subject)).fetchone()
                if dup:
                    self.audit.append(c, ts=now, kind="duplicate", fact_id=dup["id"],
                                      payload={"source": source_id, "claim": self._hash(claim)})
                    return WriteResult(dup["id"], Status.VERIFIED, verdict,
                                       duplicate_of=dup["id"])
            fact_id = new_id()
            valid_from = observed or now
            Store.insert_fact(c, {
                "id": fact_id, "text": claim, "norm": norm, "subject": it.subject,
                "status": status.value, "reason": reason, "label": verdict.label.value,
                "support": verdict.support, "verdict": json.dumps(verdict.to_dict()),
                "source_id": source_id, "written_by": it.written_by, "created_at": now,
                "valid_from": valid_from, "meta": json.dumps(it.meta),
            })
            self.audit.append(c, ts=now, kind="write", fact_id=fact_id, payload={
                "status": status.value, "label": verdict.label.value,
                "support": round(verdict.support, 6), "judge": verdict.judge,
                "policy": verdict.policy, "claim": self._hash(claim), "source": source_id,
                "author": author, "written_by": it.written_by,
            })
            superseded: tuple[str, ...] = ()
            if status is Status.VERIFIED and it.subject:
                superseded, status = self._supersede(c, fact_id, it.subject, valid_from, now)
        return WriteResult(fact_id, status, verdict, superseded)

    def _supersede(self, c: sqlite3.Connection, fact_id: str, subject: str, valid_from: str,
                   now: str) -> tuple[tuple[str, ...], Status]:
        """Newer verified facts on a subject replace older ones; an older arrival is history."""
        rows = c.execute("SELECT id, valid_from FROM facts WHERE subject = ? AND "
                         "status = 'verified' AND id != ?", (subject, fact_id)).fetchall()
        replaced = []
        for r in rows:
            if (r["valid_from"] or "") <= valid_from:
                Store.update_fact(c, r["id"], status=Status.SUPERSEDED.value,
                                  superseded_by=fact_id, superseded_at=now)
                self.audit.append(c, ts=now, kind="supersede", fact_id=r["id"],
                                  payload={"by": fact_id})
                replaced.append(r["id"])
            else:
                Store.update_fact(c, fact_id, status=Status.SUPERSEDED.value,
                                  superseded_by=r["id"], superseded_at=now,
                                  reason="a more recent verified fact exists on this subject")
                self.audit.append(c, ts=now, kind="supersede", fact_id=fact_id,
                                  payload={"by": r["id"]})
                return tuple(replaced), Status.SUPERSEDED
        return tuple(replaced), Status.VERIFIED

    # ------------------------------------------------------------ review and deletion
    def review(self, fact_id: str, *, approve: bool, reviewer: str) -> Fact:
        """A human decision on an unverified, quarantined or rejected fact."""
        if not reviewer.strip():
            raise ValueError("a review needs the reviewer's name")
        fact = self._require(fact_id)
        if fact.status not in _REVIEWABLE:
            raise ValueError(f"a {fact.status.value} fact cannot be reviewed")
        new = Status.VERIFIED if approve else Status.REJECTED
        now = self._clock()
        with self.store.transaction() as c:
            verb = "approved" if approve else "rejected"
            Store.update_fact(c, fact_id, status=new.value, reviewed_by=reviewer,
                              reason=f"{verb} by {reviewer}")
            self.audit.append(c, ts=now, kind="review", fact_id=fact_id, payload={
                "from": fact.status.value, "to": new.value, "reviewer": reviewer})
            if approve and fact.subject:
                self._supersede(c, fact_id, fact.subject, fact.valid_from or now, now)
        return self._require(fact_id)

    def review_queue(self, limit: int = 20) -> list[Fact]:
        rows = self.store.facts_where("f.status IN ('unverified', 'quarantined')",
                                      order="f.rowid DESC", limit=limit)
        return [self._to_fact(r) for r in rows]

    def forget(self, fact_id: str, *, reason: str = "") -> None:
        """Delete a fact's content for good; the audit chain keeps only a keyed hash."""
        fact = self._require(fact_id)
        if fact.status is Status.FORGOTTEN:
            return
        scrubbed = Verdict(label=fact.label, support=fact.support, contradiction=None,
                           evidence=None, checks=(), judge=fact.judge, policy=fact.policy,
                           language="und", reason="forgotten")
        now = self._clock()
        with self.store.transaction() as c:
            Store.update_fact(c, fact_id, text="", norm="", subject=None,
                              status=Status.FORGOTTEN.value, reason="forgotten on request",
                              verdict=json.dumps(scrubbed.to_dict()), meta="{}")
            if fact.source_id:
                still_used = c.execute(
                    "SELECT 1 FROM facts WHERE source_id = ? AND status != 'forgotten' LIMIT 1",
                    (fact.source_id,)).fetchone()
                if not still_used:
                    c.execute("UPDATE sources SET text = NULL, origin = '', meta = '{}' "
                              "WHERE id = ?", (fact.source_id,))
            self.audit.append(c, ts=now, kind="forget", fact_id=fact_id, payload={
                "from": fact.status.value, "reason": self._hash(reason) if reason else None})
        self.store.purge()

    # ------------------------------------------------------------ read path
    def get(self, fact_id: str) -> Fact | None:
        row = self.store.get_fact(fact_id)
        return self._to_fact(row) if row else None

    def recall(self, query: str, *, k: int = 5,
               include: Sequence[Status | str] = (Status.VERIFIED,)) -> list[Recalled]:
        """Full-text search over facts with the given statuses (verified only by default)."""
        statuses = [Status(s).value for s in include]
        return [Recalled(self._to_fact(r), score)
                for r, score in self.store.search(query, statuses, limit=k)]

    def ask(self, question: str, *, k: int = 5) -> Answer:
        """Verified facts that answer `question`, or an explicit abstention with its reason."""
        hits = self.store.search(question, [Status.VERIFIED.value], limit=max(4 * k, 20))
        if not hits:
            return Answer(question, (), True, "no verified fact shares words with the question")
        facts = [self._to_fact(r) for r, _ in hits]
        if not self._judge_is_model():
            return Answer(question, (), True, "relevance needs a model judge; use recall() "
                          "for keyword matches", considered=len(facts))
        try:
            scores = self.relevance.score(question, [f.text for f in facts])
        except JudgeUnavailable as e:
            return Answer(question, (), True, f"cannot check relevance: {e}",
                          considered=len(facts))
        ranked = sorted(zip(facts, scores, strict=True), key=lambda x: x[1], reverse=True)
        th, floor = self.policy.relevance_threshold, self.policy.relevance_related_threshold
        kept = tuple(Recalled(f, s) for f, s in ranked if s >= th)[:k]
        related = tuple(Recalled(f, s) for f, s in ranked if floor <= s < th)[:k]
        candidates = tuple((f.id, s) for f, s in ranked)
        more = f"; {len(related)} related fact(s) may help" if related else ""
        if not kept:
            return Answer(question, (), True, "no verified fact answers the question "
                          f"(best relevance p={ranked[0][1]:.2f}){more}", len(facts), candidates,
                          related)
        return Answer(question, kept, False, f"{len(kept)} verified fact(s) answer the "
                      f"question{more}", len(facts), candidates, related)

    def history(self, subject: str) -> list[Fact]:
        rows = self.store.facts_where("f.subject = ?", (subject,), order="f.valid_from, f.rowid")
        return [self._to_fact(r) for r in rows]

    def stats(self) -> dict[str, Any]:
        check = self.audit.verify()
        return {
            "facts": self.store.count_by_status(),
            "sources": self.store.count("sources"),
            "events": check.events,
            "audit_chain_ok": check.ok,
            "store_id": self.store.meta("store_id"),
            "policy": self.policy.version,
            "judge": self.policy.judge,
        }

    # ------------------------------------------------------------ helpers
    def _hash(self, text: str) -> str:
        return hmac.new(self._key, text.encode("utf-8"), hashlib.sha256).hexdigest()

    def _judge_is_model(self) -> bool:
        try:
            return bool(self.verifier.judge.is_model)
        except (ValueError, JudgeUnavailable):
            return False

    def _require(self, fact_id: str) -> Fact:
        fact = self.get(fact_id)
        if fact is None:
            raise KeyError(f"no fact with id {fact_id!r}")
        return fact

    @staticmethod
    def _to_fact(row: sqlite3.Row) -> Fact:
        v = Verdict.from_dict(json.loads(row["verdict"]))
        return Fact(
            id=row["id"], text=row["text"], status=Status(row["status"]),
            label=Label(row["label"]), support=float(row["support"]), subject=row["subject"],
            source_id=row["source_id"], source_origin=row["source_origin"],
            source_author=row["source_author"], evidence=v.evidence, judge=v.judge,
            policy=v.policy, reason=row["reason"], created_at=row["created_at"],
            valid_from=row["valid_from"], superseded_by=row["superseded_by"],
            reviewed_by=row["reviewed_by"],
        )
