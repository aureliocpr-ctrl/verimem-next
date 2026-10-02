"""Quantities in text, and whether a claim's quantities appear in its source.

A claim that adds a number the source never states (an amount, a percentage, a count, a
date) is the cheapest confabulation to catch and one of the most damaging to store, so it
is checked deterministically, before and regardless of the model judge.

Covered: digits with either thousands/decimal convention (both readings kept when
ambiguous), number words in Italian and English, percentages, scale words and suffixes
(k, M, thousand, mila, million, milioni, ...), ordinals, times, numeric dates and month names.
Not covered (by design): quantities the claim computes from the source ("3 + 2 = 5 people");
such claims are reported as not supported, which is the conservative side.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------- number words


def _english_words() -> dict[str, int]:
    units = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
             "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
             "seventeen", "eighteen", "nineteen"]
    tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
    out = {w: i for i, w in enumerate(units)}
    for t in range(2, 10):
        out[tens[t]] = t * 10
        for u in range(1, 10):
            out[f"{tens[t]}-{units[u]}"] = t * 10 + u
    out.update({"hundred": 100, "thousand": 1000, "dozen": 12})
    return out


def _italian_words() -> dict[str, int]:
    units = ["zero", "uno", "due", "tre", "quattro", "cinque", "sei", "sette", "otto", "nove",
             "dieci", "undici", "dodici", "tredici", "quattordici", "quindici", "sedici",
             "diciassette", "diciotto", "diciannove"]
    tens = ["", "", "venti", "trenta", "quaranta", "cinquanta", "sessanta", "settanta",
            "ottanta", "novanta"]
    base = {w: i for i, w in enumerate(units)}
    for t in range(2, 10):
        base[tens[t]] = t * 10
        for u in range(1, 10):
            unit = "tré" if u == 3 else units[u]
            # "venti" + "uno" -> "ventuno": the tens word drops its last vowel before a vowel.
            stem = tens[t][:-1] if unit[0] in "uo" else tens[t]
            base[stem + unit] = t * 10 + u
            if u == 3:
                base[stem + "tre"] = t * 10 + 3
    out = dict(base)
    hundreds = {1: "cento", 2: "duecento", 3: "trecento", 4: "quattrocento", 5: "cinquecento",
                6: "seicento", 7: "settecento", 8: "ottocento", 9: "novecento"}
    for h, hw in hundreds.items():
        out[hw] = h * 100
        for word, val in base.items():
            if 0 < val < 100:
                out[hw + word] = h * 100 + val
                if word.startswith("o"):  # "centottanta" as well as "centoottanta"
                    out[hw[:-1] + word] = h * 100 + val
    out.update({"mille": 1000, "dozzina": 12})
    for n in range(2, 10):
        out[units[n] + "mila"] = n * 1000
    return out


# Left out on purpose: "one"/"uno" (articles far more often than counts) and "sei" (the verb
# "you are" far more often than six).
_NUMBER_WORDS = {
    **{k: v for k, v in _english_words().items() if k not in {"one"}},
    **{k: v for k, v in _italian_words().items() if k not in {"uno", "sei"}},
}
_SCALES = {
    "k": 1e3, "thousand": 1e3, "thousands": 1e3, "mila": 1e3,
    "m": 1e6, "mln": 1e6, "million": 1e6, "millions": 1e6, "milione": 1e6, "milioni": 1e6,
    "bn": 1e9, "b": 1e9, "billion": 1e9, "billions": 1e9, "miliardo": 1e9, "miliardi": 1e9,
    "mld": 1e9, "mrd": 1e9,
}
_PERCENT_WORDS = ("percent", "per cent", "per cento", "percento")

_MONTHS = {
    # English month names only count when capitalised ("May" vs the verb "may").
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6, "July": 7,
    "August": 8, "September": 9, "October": 10, "November": 11, "December": 12,
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}
_ITALIAN_MONTH_FORMS = {k for k in _MONTHS if k.islower()}

# ---------------------------------------------------------------- regexes

_NUM = r"\d{1,3}(?:[.,]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?"
_DATE_NUMERIC = re.compile(r"(?<![\w.,/-])(\d{1,4})[/.-](\d{1,2})[/.-](\d{1,4})(?![\w/-])")
_TIME = re.compile(r"(?<![\w.,:])(\d{1,2})[:h](\d{2})(?![\w:])")
_NUMBER = re.compile(
    rf"(?<![\w.,])(?P<num>{_NUM})(?P<ord>st|nd|rd|th|°|ª|º)?"
    rf"(?:\s?(?P<pct>%|{'|'.join(re.escape(w) for w in _PERCENT_WORDS)}))?"
    rf"(?:\s?(?P<scale>{'|'.join(sorted(_SCALES, key=len, reverse=True))})\b)?",
    re.IGNORECASE,
)
_WORD = re.compile(r"[A-Za-zÀ-ÿ]+(?:-[A-Za-zÀ-ÿ]+)?")


@dataclass(frozen=True)
class Quantity:
    """A quantity found in a text: its surface form, offsets and candidate values."""

    surface: str
    start: int
    end: int
    values: frozenset[float]
    kind: str  # "number" or "month"


def _readings(raw: str) -> set[float]:
    """Every value a digit string can denote under the IT or EN conventions."""
    if "." in raw and "," in raw:
        dec = "." if raw.rfind(".") > raw.rfind(",") else ","
        thou = "," if dec == "." else "."
        return {float(raw.replace(thou, "").replace(dec, "."))}
    sep = "." if "." in raw else "," if "," in raw else ""
    if not sep:
        return {float(raw)}
    head, *tails = raw.split(sep)
    if len(tails) > 1:  # "1.250.000" or "1,250,000": only thousands
        return {float(head + "".join(tails))}
    tail = tails[0]
    as_decimal = float(f"{head}.{tail}")
    if len(tail) == 3 and head != "0":
        return {as_decimal, float(head + tail)}  # "1,250": 1.25 (IT) or 1250 (EN)
    return {as_decimal}


def extract(text: str) -> list[Quantity]:
    """All quantities in `text`, left to right."""
    found: list[Quantity] = []
    taken: list[tuple[int, int]] = []

    def free(s: int, e: int) -> bool:
        return all(e <= a or s >= b for a, b in taken)

    def add(surface: str, s: int, e: int, values: set[float], kind: str = "number") -> None:
        found.append(Quantity(surface, s, e, frozenset(values), kind))
        taken.append((s, e))

    for m in _DATE_NUMERIC.finditer(text):
        a, b, c = (int(g) for g in m.groups())
        add(m.group(), m.start(), m.end(), {float(a), float(b), float(c)})
        for month in {b, a} if a <= 12 else {b}:  # d/m/y or m/d/y when ambiguous
            if 1 <= month <= 12:
                found.append(Quantity(m.group(), m.start(), m.end(), frozenset({month}), "month"))
    for m in _TIME.finditer(text):
        if free(m.start(), m.end()):
            h, mi = int(m.group(1)), int(m.group(2))
            add(m.group(), m.start(), m.end(), {h * 60.0 + mi, float(h), float(f"{h}.{mi:02d}")})
    for m in _NUMBER.finditer(text):
        if not free(m.start(), m.end()):
            continue
        values = _readings(m.group("num"))
        scale = m.group("scale")
        # Lowercase "m" and "b" are metres and bytes ("5 m"); "5M" and "2B" are scales.
        if scale and scale not in {"m", "b"}:
            values |= {v * _SCALES[scale.lower()] for v in values}
        # "10.30" may be a time in Italian: keep the minutes reading too.
        raw = m.group("num")
        if re.fullmatch(r"\d{1,2}\.\d{2}", raw):
            h, mi = (int(x) for x in raw.split("."))
            if h < 24 and mi < 60:
                values.add(h * 60.0 + mi)
        add(m.group(), m.start(), m.end(), values)
    for m in _WORD.finditer(text):
        word = m.group()
        low = word.lower()
        if not free(m.start(), m.end()):
            continue
        if word in _MONTHS or low in _ITALIAN_MONTH_FORMS:
            month = _MONTHS.get(word) or _MONTHS[low]
            add(word, m.start(), m.end(), {float(month)}, "month")
        elif low in _NUMBER_WORDS:
            add(word, m.start(), m.end(), {float(_NUMBER_WORDS[low])})
    found.sort(key=lambda q: (q.start, q.kind))
    return found


def _same(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))


def missing_quantities(claim: str, source: str) -> list[str]:
    """Surface forms of the claim's quantities that have no match anywhere in the source."""
    src = extract(source)
    numbers = [q for q in src if q.kind == "number"]
    months = [q for q in src if q.kind == "month"]
    missing: list[str] = []
    for q in extract(claim):
        pool = months if q.kind == "month" else numbers
        if not any(_same(a, b) for s in pool for a in q.values for b in s.values):
            missing.append(q.surface)
    return missing
