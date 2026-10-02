"""NLI judge backed by a Hugging Face sequence-classification model.

Two mistakes this module guards against, both seen in practice:
- picking the "entailment" class by substring ("unsupported" contains "support",
  "not_entailment" contains "entail"): labels are matched by exact name;
- trusting a label mapping blindly: every load runs a known supported/unsupported pair and
  refuses a model whose orientation comes out reversed.
"""

from __future__ import annotations

import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import DTYPES, JudgeUnavailable, NLIScores

_ENTAIL = {"entailment", "entailed", "supported", "support", "consistent"}
_CONTRA = {"contradiction", "contradicted", "refuted"}
_NEUTRAL = {"neutral"}
_NOT_ENTAIL = {"not_entailment", "not_entailed", "non_entailment", "unsupported",
               "not_supported", "inconsistent"}

SANITY_PREMISE = ("The Eiffel Tower is 330 metres tall and was completed in 1889 "
                  "for the World's Fair.")
SANITY_TRUE = "The tower was finished in 1889."
SANITY_FALSE = "The tower was finished in 1899."


def _cached_revision(model_id: str, revision: str | None) -> str | None:
    """The commit hash of the cached snapshot, so verdicts name the exact weights used."""
    try:
        from huggingface_hub import try_to_load_from_cache

        path = try_to_load_from_cache(model_id, "config.json", revision=revision)
    except Exception:  # noqa: BLE001 - provenance is best effort, never a reason to fail
        return None
    if isinstance(path, str):
        parts = Path(path).parts
        if "snapshots" in parts:
            return parts[parts.index("snapshots") + 1]
    return None


def _transformers_major() -> int:
    import transformers

    return int(transformers.__version__.split(".")[0])


def _norm(label: str) -> str:
    return str(label).strip().lower().replace("-", "_").replace(" ", "_")


class HFNLIJudge:
    """Scores (premise, hypothesis) pairs with a local transformers model."""

    is_model = True

    def __init__(self, model_id: str, *, revision: str | None = None, device: str = "cpu",
                 max_length: int = 512, batch_size: int = 16, allow_download: bool = False,
                 dtype: str = "float32") -> None:
        if dtype not in DTYPES:
            raise ValueError(f"dtype {dtype!r} is not one of {', '.join(DTYPES)}")
        self.model_id = model_id
        self.dtype = dtype
        self.revision = revision
        self.device = device
        self.max_length = max_length
        self.batch_size = batch_size
        self.allow_download = allow_download
        self._lock = threading.Lock()
        self._tok: Any = None
        self._model: Any = None
        self._entail: int | None = None
        self._contra: int | None = None
        self._neutral: int | None = None
        self._sigmoid = False
        self._resolved: str | None = None

    # ------------------------------------------------------------ identity
    @property
    def id(self) -> str:
        rev = (self._resolved or self.revision or "unresolved")[:12]
        precision = "" if self.dtype == "float32" else f"+{self.dtype}"
        return f"hf:{self.model_id}@{rev}{precision}"

    @property
    def three_way(self) -> bool:
        self.load()
        return self._contra is not None

    @property
    def loaded(self) -> bool:
        return self._model is not None

    # ------------------------------------------------------------ loading
    def load(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            try:
                import torch
                from transformers import AutoModelForSequenceClassification, AutoTokenizer
            except ImportError as e:
                raise JudgeUnavailable(
                    "Model judges need the 'nli' extra: pip install 'verimem[nli]'"
                ) from e
            kw = {"revision": self.revision, "local_files_only": not self.allow_download}
            # Load straight into the precision we run in: no second copy of the weights.
            dtype = getattr(torch, self.dtype)
            dtype_kw = {"dtype" if _transformers_major() >= 5 else "torch_dtype": dtype}
            try:
                tok = AutoTokenizer.from_pretrained(self.model_id, **kw)
                model = AutoModelForSequenceClassification.from_pretrained(self.model_id, **kw,
                                                                           **dtype_kw)
            except OSError as e:
                raise JudgeUnavailable(
                    f"Model {self.model_id} is not available locally. Run `verimem warmup` "
                    "to download it, or construct the judge with allow_download=True."
                ) from e
            model.eval()
            # Explicit: transformers 5 loads a float16 checkpoint as float16, transformers 4
            # as float32, and the scores would depend on the installed version.
            model.to(device=self.device, dtype=dtype)
            self._map_labels(model)
            self._tok, self._model = tok, model
            self._resolved = (getattr(model.config, "_commit_hash", None)
                              or _cached_revision(self.model_id, self.revision) or self.revision)
            self._check_orientation()

    def _map_labels(self, model: Any) -> None:
        labels = {int(i): _norm(v) for i, v in model.config.id2label.items()}
        n = int(model.config.num_labels)
        if n == 1:
            self._entail, self._sigmoid = 0, True
            return
        find = lambda names: next((i for i, v in labels.items() if v in names), None)  # noqa: E731
        self._entail = find(_ENTAIL)
        self._contra = find(_CONTRA)
        self._neutral = find(_NEUTRAL)
        if self._entail is None and n == 2:
            not_entail = find(_NOT_ENTAIL)
            # Unnamed binary heads ("LABEL_0"/"LABEL_1"): assume 1 = supported, checked below.
            self._entail = 1 - not_entail if not_entail is not None else 1
        if self._entail is None:
            raise JudgeUnavailable(
                f"Cannot find an entailment class among the labels of {self.model_id}: {labels}"
            )

    def _check_orientation(self) -> None:
        good, bad = self._raw_score([(SANITY_PREMISE, SANITY_TRUE), (SANITY_PREMISE, SANITY_FALSE)])
        if good.entailment > bad.entailment:
            return
        if self._contra is None and self._neutral is None and not self._sigmoid:
            self._entail = 1 - self._entail  # unnamed binary head with the opposite convention
            good, bad = self._raw_score(
                [(SANITY_PREMISE, SANITY_TRUE), (SANITY_PREMISE, SANITY_FALSE)])
            if good.entailment > bad.entailment:
                return
        self._model = None
        raise JudgeUnavailable(
            f"{self.model_id} failed the orientation check (supported pair scored "
            f"{good.entailment:.2f}, unsupported {bad.entailment:.2f}); refusing to use it."
        )

    # ------------------------------------------------------------ scoring
    def score(self, pairs: Sequence[tuple[str, str]]) -> list[NLIScores]:
        if not pairs:
            return []
        self.load()
        with self._lock:
            return self._raw_score(pairs)

    def _raw_score(self, pairs: Sequence[tuple[str, str]]) -> list[NLIScores]:
        import torch

        # Batches of similar length waste less time on padding; results go back in order.
        order = sorted(range(len(pairs)), key=lambda i: len(pairs[i][0]) + len(pairs[i][1]))
        out: list[NLIScores] = [NLIScores(entailment=0.0)] * len(pairs)
        with torch.inference_mode():
            for start in range(0, len(order), self.batch_size):
                idx = order[start : start + self.batch_size]
                enc = self._encode([pairs[i][0] for i in idx], [pairs[i][1] for i in idx])
                logits = self._model(**enc).logits.float()
                if self._sigmoid:
                    for i, p in zip(idx, torch.sigmoid(logits[:, 0]).tolist(), strict=True):
                        out[i] = NLIScores(entailment=float(p))
                    continue
                c, n = self._contra, self._neutral
                for i, row in zip(idx, torch.softmax(logits, dim=-1).tolist(), strict=True):
                    out[i] = NLIScores(
                        entailment=float(row[self._entail]),
                        contradiction=float(row[c]) if c is not None else None,
                        neutral=float(row[n]) if n is not None else None,
                    )
        return out

    def _encode(self, premises: list[str], hypotheses: list[str]) -> Any:
        kw = {"padding": True, "max_length": self.max_length, "return_tensors": "pt"}
        try:
            enc = self._tok(premises, hypotheses, truncation="only_first", **kw)
        except Exception:  # noqa: BLE001 - tokenizers raises a bare Exception when the
            # hypothesis alone exceeds the window; truncating both sides is the fallback.
            enc = self._tok(premises, hypotheses, truncation=True, **kw)
        return {k: v.to(self.device) for k, v in enc.items()}
