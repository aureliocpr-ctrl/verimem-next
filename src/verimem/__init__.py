"""verimem: verified memory for AI agents.

Nothing is served as a fact unless its source says it; every memory carries its evidence;
when memory doesn't know, it says so.
"""

from ._version import __version__
from .memory import Item, Memory
from .policy import Policy, Thresholds
from .types import (
    Answer,
    Author,
    Evidence,
    Fact,
    Label,
    Recalled,
    Status,
    Verdict,
    WriteResult,
)
from .verifier import Verifier

__all__ = [
    "Answer",
    "Author",
    "Evidence",
    "Fact",
    "Item",
    "Label",
    "Memory",
    "Policy",
    "Recalled",
    "Status",
    "Thresholds",
    "Verdict",
    "Verifier",
    "WriteResult",
    "__version__",
]
