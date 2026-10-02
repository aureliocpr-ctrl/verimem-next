"""Reading the files people export: JSON lines, a JSON array, or CSV with a header."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any


def read_records(path: str | Path) -> list[dict[str, Any]]:
    """The rows of a JSON-lines file, a JSON array, or a CSV file (`,` or `;`).

    A quoted CSV field may span lines, so a conversation keeps its turns. JSON lines are
    split on newlines only: `str.splitlines()` would also cut at characters such as U+2028,
    which JSON allows unescaped inside a string.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() in {".jsonl", ".json"}:
        if text.lstrip().startswith("["):
            rows = json.loads(text)
            if not isinstance(rows, list):
                raise ValueError(f"{path}: expected a JSON array of objects")
            return rows
        return [json.loads(line) for line in text.split("\n") if line.strip()]
    first = text.split("\n", 1)[0]
    delim = ";" if first.count(";") > first.count(",") else ","
    return list(csv.DictReader(io.StringIO(text, newline=""), delimiter=delim))
