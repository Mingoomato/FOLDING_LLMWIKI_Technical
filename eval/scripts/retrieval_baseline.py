"""Local-only retrieval baseline for the eval harness.

A real, working (not mocked) BM25 implementation with zero third-party
dependencies -- this is what run_eval.py uses in `local_only: true` mode
(eval_config.yaml) in place of the HNSW/BM25/graph hybrid search specified
in Vol. 03-04, so the harness has something real to score against without
requiring a running LLMWiki instance. It is not a substitute for that
hybrid search once this benchmark is scaled up (see eval/README.md) --
BM25-only is exactly the "BM25 only" row of eval_config.yaml's
hybrid_weights sweep, included here as the baseline that's cheapest to
make actually work offline.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass


_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


@dataclass
class Bm25Index:
    doc_ids: list[str]
    doc_tokens: dict[str, list[str]]
    doc_freqs: dict[str, Counter]
    df: Counter
    avgdl: float
    k1: float = 1.5
    b: float = 0.75

    @classmethod
    def build(cls, documents: dict[str, str]) -> "Bm25Index":
        doc_ids = list(documents.keys())
        doc_tokens = {doc_id: tokenize(text) for doc_id, text in documents.items()}
        doc_freqs = {doc_id: Counter(toks) for doc_id, toks in doc_tokens.items()}
        df: Counter = Counter()
        for toks in doc_tokens.values():
            df.update(set(toks))
        avgdl = sum(len(t) for t in doc_tokens.values()) / max(1, len(doc_tokens))
        return cls(doc_ids=doc_ids, doc_tokens=doc_tokens, doc_freqs=doc_freqs, df=df, avgdl=avgdl)

    def _idf(self, term: str) -> float:
        n = len(self.doc_ids)
        df = self.df.get(term, 0)
        # BM25 idf with +1 smoothing to keep it non-negative for small corpora.
        return math.log((n - df + 0.5) / (df + 0.5) + 1)

    def score(self, query: str, doc_id: str) -> float:
        query_terms = tokenize(query)
        freqs = self.doc_freqs[doc_id]
        dl = len(self.doc_tokens[doc_id])
        score = 0.0
        for term in query_terms:
            f = freqs.get(term, 0)
            if f == 0:
                continue
            idf = self._idf(term)
            denom = f + self.k1 * (1 - self.b + self.b * dl / max(1e-9, self.avgdl))
            score += idf * (f * (self.k1 + 1)) / denom
        return score

    def rank(self, query: str, top_n: int | None = None) -> list[tuple[str, float]]:
        scored = [(doc_id, self.score(query, doc_id)) for doc_id in self.doc_ids]
        scored.sort(key=lambda x: x[1], reverse=True)
        scored = [s for s in scored if s[1] > 0]
        return scored[:top_n] if top_n else scored
