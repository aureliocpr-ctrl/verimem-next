"""Policies: versioned thresholds and settings, stored as JSON (ADR-0005)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from importlib import resources
from pathlib import Path
from typing import Any

DEFAULT_POLICY_FILE = "default.json"


@dataclass(frozen=True)
class Thresholds:
    """Decision thresholds on judge probabilities, all in [0, 1]."""

    support: float = 0.5
    uncertain: float = 0.2
    contradiction: float = 0.8

    def __post_init__(self) -> None:
        for name in ("support", "uncertain", "contradiction"):
            v = getattr(self, name)
            if not 0.0 <= v <= 1.0:
                raise ValueError(f"threshold {name}={v} is outside [0, 1]")
        if self.uncertain > self.support:
            raise ValueError("the uncertain threshold cannot exceed the support threshold")


@dataclass(frozen=True)
class Policy:
    """Everything that decides a verdict, apart from the judge's weights."""

    version: str
    judge: str
    thresholds: Thresholds = field(default_factory=Thresholds)
    per_language: dict[str, Thresholds] = field(default_factory=dict)
    numeric_check: bool = True
    context_check: bool = True
    max_windows: int = 4
    window_sizes: tuple[int, ...] = (1, 2)
    full_source_max_chars: int = 1500
    trusted_authors: tuple[str, ...] = ("user", "document", "system")
    relevance_threshold: float = 0.4
    relevance_related_threshold: float = 0.05
    relevance_templates: dict[str, str] = field(default_factory=lambda: {
        "en": "This text answers the question: {question}",
        "it": "Questo testo risponde alla domanda: {question}",
    })
    calibration: dict[str, Any] | None = None

    def thresholds_for(self, language: str) -> Thresholds:
        return self.per_language.get(language, self.thresholds)

    def with_thresholds(self, thresholds: Thresholds, *, version: str,
                        calibration: dict[str, Any] | None = None) -> Policy:
        return replace(self, thresholds=thresholds, per_language={}, version=version,
                       calibration=calibration)

    # ------------------------------------------------------------ (de)serialisation
    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["window_sizes"] = list(self.window_sizes)
        d["trusted_authors"] = list(self.trusted_authors)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Policy:
        d = dict(d)
        d["thresholds"] = Thresholds(**d.get("thresholds", {}))
        d["per_language"] = {k: Thresholds(**v) for k, v in d.get("per_language", {}).items()}
        d["window_sizes"] = tuple(d.get("window_sizes", (1, 2)))
        d["trusted_authors"] = tuple(d.get("trusted_authors", ("user", "document", "system")))
        known = set(cls.__dataclass_fields__)
        unknown = set(d) - known
        if unknown:
            raise ValueError(f"unknown policy fields: {sorted(unknown)}")
        return cls(**d)

    @classmethod
    def load(cls, path: str | Path) -> Policy:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")

    @classmethod
    def default(cls) -> Policy:
        text = resources.files("verimem.policies").joinpath(DEFAULT_POLICY_FILE).read_text(
            encoding="utf-8")
        return cls.from_dict(json.loads(text))
