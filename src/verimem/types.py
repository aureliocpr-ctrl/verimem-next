"""Public data types. Everything here is immutable and serialisable to plain dicts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Label(str, Enum):
    """What the verifier concluded about a claim and its source."""

    SUPPORTED = "supported"
    NOT_SUPPORTED = "not_supported"
    CONTRADICTED = "contradicted"
    UNCERTAIN = "uncertain"
    UNJUDGED = "unjudged"


class Status(str, Enum):
    """Lifecycle state of a stored fact. Only VERIFIED facts are served as facts by default."""

    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    QUARANTINED = "quarantined"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    FORGOTTEN = "forgotten"


class Author(str, Enum):
    """Who produced a source. Trust policy decides which authors may verify a fact."""

    USER = "user"
    DOCUMENT = "document"
    SYSTEM = "system"
    AGENT = "agent"
    TOOL = "tool"
    WEB = "web"


@dataclass(frozen=True)
class Span:
    """A slice of a text, with character offsets into it."""

    start: int
    end: int
    text: str


@dataclass(frozen=True)
class Evidence:
    """The source window the judge compared the claim with, and how it scored."""

    start: int
    end: int
    text: str
    support: float
    contradiction: float | None = None


@dataclass(frozen=True)
class Check:
    """A deterministic check that ran during verification."""

    name: str
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class Verdict:
    """The outcome of verifying one claim against one source."""

    label: Label
    support: float
    contradiction: float | None
    evidence: Evidence | None
    checks: tuple[Check, ...]
    judge: str
    policy: str
    language: str
    reason: str
    elapsed_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["label"] = self.label.value
        d["checks"] = [asdict(c) for c in self.checks]
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Verdict:
        ev = d.get("evidence")
        return cls(
            label=Label(d["label"]),
            support=float(d["support"]),
            contradiction=d.get("contradiction"),
            evidence=Evidence(**ev) if ev else None,
            checks=tuple(Check(**c) for c in d.get("checks", ())),
            judge=d["judge"],
            policy=d["policy"],
            language=d.get("language", "und"),
            reason=d.get("reason", ""),
            elapsed_ms=float(d.get("elapsed_ms", 0.0)),
        )


@dataclass(frozen=True)
class Fact:
    """A stored memory with its provenance."""

    id: str
    text: str
    status: Status
    label: Label
    support: float
    subject: str | None
    source_id: str | None
    source_origin: str | None
    source_author: str | None
    evidence: Evidence | None
    judge: str
    policy: str
    reason: str
    created_at: str
    valid_from: str | None
    superseded_by: str | None = None
    reviewed_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        d["label"] = self.label.value
        return d


@dataclass(frozen=True)
class WriteResult:
    """What `Memory.remember` did with a claim."""

    fact_id: str
    status: Status
    verdict: Verdict
    superseded: tuple[str, ...] = ()
    duplicate_of: str | None = None

    @property
    def verified(self) -> bool:
        return self.status is Status.VERIFIED

    def to_dict(self) -> dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "status": self.status.value,
            "verdict": self.verdict.to_dict(),
            "superseded": list(self.superseded),
            "duplicate_of": self.duplicate_of,
        }


@dataclass(frozen=True)
class Recalled:
    """A fact returned by a read, with the score that ranked it."""

    fact: Fact
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {"score": self.score, **self.fact.to_dict()}


@dataclass(frozen=True)
class Answer:
    """The result of `Memory.ask`: relevant verified facts, or an explicit abstention."""

    question: str
    facts: tuple[Recalled, ...]
    abstained: bool
    reason: str
    considered: int = 0
    scores: tuple[float, ...] = field(default=())

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "abstained": self.abstained,
            "reason": self.reason,
            "considered": self.considered,
            "facts": [r.to_dict() for r in self.facts],
        }
