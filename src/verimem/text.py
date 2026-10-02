"""Text utilities: sentence splitting with offsets, language guess, content tokens.

Only the standard library. Tuned for Italian and English, safe on other Latin-script text.
"""

from __future__ import annotations

import re
import unicodedata

from .types import Span

# Words that end with a period without ending a sentence (lowercase, without the period).
_ABBREVIATIONS = frozenset(
    """
    mr mrs ms dr prof sr jr st vs etc e.g i.e inc ltd co corp no nr n p pp pag art cap
    sig sigg sig.ra dott dott.ssa ing avv geom rag ecc es cfr fig tab vol ed al approx
    ca min max gen feb mar apr mag giu lug ago set ott nov dic jan jun jul aug sep sept
    oct dec u.s u.k a.m p.m spa s.p.a srl s.r.l resp dir amm tel rif uff pres segr
    """.split()
)

_SENT_END = re.compile(r"[.!?…]+[\"'”’»)\]]*(?=\s)")
_BULLET = re.compile(r"^\s*(?:[-*•▪◦]|\d{1,3}[.)])\s+")
_SPEAKER = re.compile(r"^\s*[\w .'-]{1,30}:\s")
_WORD = re.compile(r"\w+", re.UNICODE)
_QUESTION_END = re.compile(r"\?[?!…]*[\"'”’»)\]]*\s*$")

_STOP_IT = frozenset(
    """
    il lo la i gli le un una uno di da del della dello dei degli delle al allo alla ai
    agli alle dal dalla dai dagli dalle nel nella nei negli nelle sul sulla sui sugli
    sulle con per tra fra che chi cui non è e ed o od ma se anche come più meno molto
    sono sei siamo siete era erano stato stata stati state essere ho hai ha abbiamo
    avete hanno mi ti si ci vi ne questo questa questi queste quello quella quelli
    quelle perché quando dove già ancora poi solo sempre suo sua suoi sue mio mia miei
    mie tuo tua nostro nostra loro
    """.split()
)
_STOP_EN = frozenset(
    """
    the an of to and or is are was were be been being not for with that this these those
    it its on by from at as have has had do does did i my me we our you your he she they
    them his her their but if because so than then there here what which who whom when
    where why how all any some more most very can could will would should may might must
    also just about into over after before up down out
    """.split()
)
# Words common to both languages are useless for telling them apart.
_AMBIGUOUS = frozenset({"a", "in", "e", "come", "se", "per", "do", "no"})
_STOPWORDS = _STOP_IT | _STOP_EN | {"a", "in"}


def normalize_ws(text: str) -> str:
    """Collapse runs of whitespace into single spaces and strip the ends."""
    return " ".join(text.split())


def _is_abbreviation(text: str, dot_index: int) -> bool:
    """True if the period at `dot_index` closes an abbreviation or an initial."""
    start = dot_index
    while start > 0 and not text[start - 1].isspace() and text[start - 1] not in "([\"'“‘«":
        start -= 1
    token = text[start:dot_index].lower()
    if not token:
        return False
    if token in _ABBREVIATIONS:
        return True
    # A single letter followed by a period is an initial ("J. Smith"), not a sentence end.
    return len(token) == 1 and token.isalpha()


def _line_breaks_sentence(prev_line: str, next_line: str) -> bool:
    """Decide whether a single newline separates two sentences or just wraps one."""
    prev = prev_line.rstrip()
    if not prev or not next_line.strip():
        return True
    if prev[-1] in ".!?…:;\"”’»)]":
        return True
    if _BULLET.match(next_line) or _SPEAKER.match(next_line):
        return True
    # Short lines (chat turns, list items, titles) are units of their own.
    return len(prev) < 60


def split_sentences(text: str) -> list[Span]:
    """Split `text` into sentences, returning spans with offsets into `text`.

    Handles abbreviations (Dr., ecc., e.g.), initials, decimals (no space after the
    period), chat and list lines, and hard-wrapped paragraphs.
    """
    if not text or not text.strip():
        return []
    boundaries: set[int] = set()

    # 1. Line structure: blank lines always separate; single newlines sometimes do.
    lines = text.split("\n")
    pos = 0
    for i, line in enumerate(lines[:-1]):
        end_of_line = pos + len(line)
        if _line_breaks_sentence(line, lines[i + 1]):
            boundaries.add(end_of_line)
        pos = end_of_line + 1

    # 2. Sentence-final punctuation followed by whitespace.
    for m in _SENT_END.finditer(text):
        dot = m.start()
        if text[dot] == "." and m.group().rstrip("\"'”’»)]") == "." and _is_abbreviation(text, dot):
            continue
        boundaries.add(m.end())

    spans: list[Span] = []
    start = 0
    for b in [*sorted(boundaries), len(text)]:
        if b <= start:
            continue
        _append_span(text, start, b, spans)
        start = b
    return spans


def _append_span(text: str, start: int, end: int, out: list[Span]) -> None:
    chunk = text[start:end]
    lead = len(chunk) - len(chunk.lstrip())
    trail = len(chunk) - len(chunk.rstrip())
    s, e = start + lead, end - trail
    if e > s:
        out.append(Span(s, e, text[s:e]))


def is_question(sentence: str) -> bool:
    """True when the sentence asks instead of stating (it ends with a question mark)."""
    return _QUESTION_END.search(sentence) is not None


def words(text: str) -> list[str]:
    """Lowercased word tokens (Unicode-aware), NFKC-normalised."""
    return [w.lower() for w in _WORD.findall(unicodedata.normalize("NFKC", text))]


def content_tokens(text: str) -> set[str]:
    """Words that carry meaning: no stopwords, no single letters (digits are kept)."""
    return {w for w in words(text) if w not in _STOPWORDS and (len(w) > 1 or w.isdigit())}


def guess_language(text: str) -> str:
    """Return "it", "en" or "und" from function-word counts. Cheap and good enough for routing."""
    toks = words(text)
    it = sum(1 for t in toks if t in _STOP_IT and t not in _AMBIGUOUS)
    en = sum(1 for t in toks if t in _STOP_EN and t not in _AMBIGUOUS)
    if it == en:
        return "und"
    return "it" if it > en else "en"


def char_trigrams(text: str) -> set[str]:
    """Character trigrams of the lowercased text, for language-agnostic overlap."""
    t = f"  {normalize_ws(text).lower()}  "
    return {t[i : i + 3] for i in range(len(t) - 2)}
