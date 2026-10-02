"""Verify claims against their sources (DESIGN.md §5)."""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass

from .judges import Judge, JudgeUnavailable, NLIScores, load_judge
from .numbers import missing_quantities
from .policy import Policy
from .text import (
    char_trigrams,
    content_tokens,
    guess_language,
    is_question,
    normalize_ws,
    split_sentences,
)
from .types import Check, Evidence, Label, Span, Verdict


@dataclass(frozen=True)
class _Prepared:
    claim: str
    source: str
    language: str
    windows: tuple[Span, ...]
    missing: tuple[str, ...]
    first: int  # index of this item's first pair in the batched judge call


class Verifier:
    """Checks whether a source supports a claim. Thread-safe once the judge is loaded."""

    def __init__(self, judge: Judge | None = None, policy: Policy | None = None, *,
                 allow_download: bool = False) -> None:
        self.policy = policy or Policy.default()
        self._judge = judge
        self._allow_download = allow_download

    @classmethod
    def default(cls, *, allow_download: bool = False) -> Verifier:
        return cls(policy=Policy.default(), allow_download=allow_download)

    @property
    def judge(self) -> Judge:
        if self._judge is None:
            self._judge = load_judge(self.policy.judge, allow_download=self._allow_download)
        return self._judge

    def warmup(self) -> str:
        """Load the judge now (instead of on the first check) and return its id."""
        self.judge.score([("The sky is blue.", "The sky is blue.")])
        return self.judge.id

    # ------------------------------------------------------------ public API
    def check(self, source: str | None, claim: str, *, language: str | None = None) -> Verdict:
        return self.check_many([(source, claim)], language=language)[0]

    def check_many(self, items: Sequence[tuple[str | None, str]], *,
                   language: str | None = None) -> list[Verdict]:
        """Verify many (source, claim) pairs with one batched judge call."""
        t0 = time.perf_counter()
        prepared: list[_Prepared | None] = []
        pairs: list[tuple[str, str]] = []
        for source, claim in items:
            claim_n = normalize_ws(claim or "")
            if not claim_n:
                raise ValueError("claim is empty")
            if not source or not source.strip():
                prepared.append(None)
                continue
            lang = language or guess_language(claim_n)
            if lang == "und":
                lang = guess_language(source)
            windows = self._windows(source, claim_n)
            missing = missing_quantities(claim_n, source) if self.policy.numeric_check else []
            prepared.append(_Prepared(claim_n, source, lang, tuple(windows), tuple(missing),
                                      len(pairs)))
            pairs.extend((w.text, claim_n) for w in windows)

        error: str | None = None
        scores: list[NLIScores] = []
        judge_id = self.policy.judge
        if pairs:
            try:
                scores = self.judge.score(pairs)
                judge_id = self.judge.id
            except JudgeUnavailable as e:
                error = str(e)
        per_item_ms = (time.perf_counter() - t0) * 1000 / max(1, len(items))

        out: list[Verdict] = []
        for p in prepared:
            if p is None:
                out.append(self._unjudged("no source was given, so nothing can be verified",
                                          judge_id, "und", per_item_ms))
            elif error is not None:
                out.append(self._unjudged(error, judge_id, p.language, per_item_ms))
            else:
                item_scores = scores[p.first : p.first + len(p.windows)]
                out.append(self._decide(p, item_scores, judge_id, per_item_ms))
        return out

    # ------------------------------------------------------------ internals
    def _windows(self, source: str, claim: str) -> list[Span]:
        sents = split_sentences(source)
        if not sents:
            return [Span(0, len(source), source)]
        # A question states nothing, so it is never evidence on its own; next to its answer
        # it is context ("Where do you live?" "In Milan.").
        asks = [is_question(s.text) for s in sents]
        seen: dict[tuple[int, int], Span] = {}
        for size in self.policy.window_sizes:
            for i in range(len(sents) - size + 1):
                if all(asks[i : i + size]):
                    continue
                s, e = sents[i].start, sents[i + size - 1].end
                seen.setdefault((s, e), Span(s, e, source[s:e]))
        whole = (sents[0].start, sents[-1].end)
        has_whole = len(source) <= self.policy.full_source_max_chars and not all(asks)
        if has_whole:
            seen.setdefault(whole, Span(*whole, source[whole[0] : whole[1]]))
        windows = list(seen.values())
        if len(windows) <= self.policy.max_windows:
            return windows
        return self._prefilter(windows, claim, whole if has_whole else None)

    def _prefilter(self, windows: list[Span], claim: str,
                   whole: tuple[int, int] | None) -> list[Span]:
        """Keep the windows most likely to matter: lexical overlap plus character trigrams,
        which still work across languages and inflections."""
        ct, tri = content_tokens(claim), char_trigrams(claim)

        def relevance(w: Span) -> float:
            wt = content_tokens(w.text)
            tok = len(ct & wt) / len(ct) if ct else 0.0
            wtri = char_trigrams(w.text)
            jac = len(tri & wtri) / len(tri | wtri) if tri else 0.0
            return tok + 0.5 * jac

        ranked = sorted(windows, key=relevance, reverse=True)
        keep = ranked[: self.policy.max_windows]
        if whole is not None and all((w.start, w.end) != whole for w in keep):
            keep[-1] = next(w for w in windows if (w.start, w.end) == whole)
        return keep

    def _decide(self, p: _Prepared, scores: Sequence[NLIScores], judge_id: str,
                elapsed_ms: float) -> Verdict:
        checks: tuple[Check, ...] = ()
        if self.policy.numeric_check:
            detail = ("quantities not in the source: " + ", ".join(p.missing)) if p.missing \
                else "every quantity in the claim appears in the source"
            checks = (Check("quantities", not p.missing, detail),)
        if not p.windows:
            return Verdict(label=Label.NOT_SUPPORTED, support=0.0, contradiction=None,
                           evidence=None, checks=checks, judge=judge_id,
                           policy=self.policy.version, language=p.language,
                           reason="the source only asks questions: it states nothing",
                           elapsed_ms=elapsed_ms)
        th = self.policy.thresholds_for(p.language)
        best_i = max(range(len(scores)), key=lambda i: scores[i].entailment)
        best_s = scores[best_i].entailment
        contra = [(s.contradiction, i) for i, s in enumerate(scores) if s.contradiction is not None]
        best_c, best_c_i = max(contra) if contra else (None, None)

        def evidence(i: int) -> Evidence:
            w, s = p.windows[i], scores[i]
            return Evidence(w.start, w.end, w.text, s.entailment, s.contradiction)


        contradicted = best_c is not None and best_c >= th.contradiction
        context_s = self._context_support(p.windows, scores, best_i)
        if p.missing and not contradicted:
            label, ev = Label.NOT_SUPPORTED, evidence(best_i)
            reason = f"quantities not in the source: {', '.join(p.missing)}"
        elif contradicted and (p.missing or best_s < th.support):
            label, ev = Label.CONTRADICTED, evidence(best_c_i)  # type: ignore[arg-type]
            reason = f"the source contradicts the claim (p={best_c:.2f})"
        elif best_s >= th.support and context_s < th.uncertain:
            # One sentence alone supports the claim, the text around it does not: an update
            # ("moved to Friday") or a reversal ("but it was cancelled") follows.
            label, ev = Label.UNCERTAIN, evidence(best_i)
            reason = (f"one sentence supports it (p={best_s:.2f}) but its context does not "
                      f"(p={context_s:.2f})")
        elif best_s >= th.support:
            label, ev = Label.SUPPORTED, evidence(best_i)
            reason = f"supported by the source (p={best_s:.2f})"
        elif best_s >= th.uncertain:
            label, ev = Label.UNCERTAIN, evidence(best_i)
            reason = f"weak support (p={best_s:.2f}): not enough to verify"
        else:
            label, ev = Label.NOT_SUPPORTED, evidence(best_i)
            reason = f"the source does not state this (best support p={best_s:.2f})"
        return Verdict(label=label, support=best_s, contradiction=best_c, evidence=ev,
                       checks=checks, judge=judge_id, policy=self.policy.version,
                       language=p.language, reason=reason, elapsed_ms=elapsed_ms)

    def _context_support(self, windows: Sequence[Span], scores: Sequence[NLIScores],
                         best_i: int) -> float:
        """Lowest support among the windows that strictly contain the best one; the best
        window's own support when nothing contains it or the context check is off."""
        best = windows[best_i]
        if not self.policy.context_check:
            return scores[best_i].entailment
        around = [s.entailment for w, s in zip(windows, scores, strict=True)
                  if w.start <= best.start and w.end >= best.end
                  and (w.start, w.end) != (best.start, best.end)]
        return min(around) if around else scores[best_i].entailment

    def _unjudged(self, reason: str, judge_id: str, language: str, elapsed_ms: float) -> Verdict:
        return Verdict(label=Label.UNJUDGED, support=0.0, contradiction=None, evidence=None,
                       checks=(), judge=judge_id, policy=self.policy.version, language=language,
                       reason=reason, elapsed_ms=elapsed_ms)
