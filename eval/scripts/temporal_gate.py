"""Time-scoped evidence gate: as-of retrieval, 3-way decisions, leakage metric.

This module exists to make three claims *executable* rather than asserted in
prose (see TECH_COMPETITIVENESS_PLAN.md Round 4). Each is falsifiable by
test_temporal_gate.py:

  1. as-of scoping     -- evidence is retrievable only within its validity
                          interval, so a query at time t cannot see facts that
                          only become valid after t.
  2. time-scoped refusal -- "not answerable from the corpus as of t" is a
                          first-class, reproducible outcome, not an empty list.
                          This is the narrow novelty claim: Glean/Kythe have
                          revision-scoped code graphs but no refusal semantics;
                          Zep/Graphiti have bitemporal validity but no gate.
  3. temporal leakage  -- the fraction of returned evidence that was NOT valid
                          at query time. Must be 0.0; the metric exists to fail
                          loudly if as-of filtering regresses.

Extends the binary abstain of Vol. 04 (Abstain("contradictory evidence",
witness)) to the 3-way Answer / Refuse / Review of Vol. 12's approval path.

No external dependencies and no network calls, per the Local-First Evaluation
principle (Vol. 06 sec:eval:philosophy).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from retrieval_baseline import Bm25Index


# --------------------------------------------------------------------------
# Temporal data model
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class TemporalUnit:
    """A semantic unit carrying a validity interval.

    Mirrors the `valid_from` / `valid_to` fields proposed for
    schemas/Relation.json and schemas/Entity.json. The interval is
    half-open: valid at t iff valid_from <= t < valid_to, with
    valid_to=None meaning "still valid" (an open interval, i.e. the
    fact has not been superseded).

    Note this is *valid* time (when the fact holds), distinct from
    ArtifactVersion.observed_at, which is *transaction* time (when we
    parsed it). Both axes are needed; only the latter exists today.
    """
    unit_id: str
    text: str
    valid_from: int
    valid_to: int | None = None

    def valid_at(self, t: int) -> bool:
        if t < self.valid_from:
            return False
        return self.valid_to is None or t < self.valid_to


def as_of(units: Sequence[TemporalUnit], t: int) -> dict[str, str]:
    """Corpus visible at time t, shaped for Bm25Index.build."""
    return {u.unit_id: u.text for u in units if u.valid_at(t)}


# --------------------------------------------------------------------------
# 3-way gate
# --------------------------------------------------------------------------

ANSWER = "answer"
REFUSE = "refuse"
REVIEW = "review"


@dataclass(frozen=True)
class GateDecision:
    """Outcome of the time-scoped evidence gate."""
    action: str                      # ANSWER | REFUSE | REVIEW
    evidence: tuple[str, ...]        # unit ids supporting the answer (empty on REFUSE)
    reason: str
    query_time: int


def decide(
    ranked: Sequence[tuple[str, float]],
    query_time: int,
    *,
    tau_refuse: float = 0.5,
    tau_answer: float = 2.0,
    min_margin: float = 0.15,
) -> GateDecision:
    """Answer / Refuse / Review from a ranked candidate list.

    REFUSE when no candidate clears tau_refuse -- the corpus as of
    query_time does not support an answer. This is the "insufficient
    evidence as of t" outcome; it is distinct from a retrieval that
    happens to return nothing, because it is reported with the time
    bound that produced it.

    REVIEW when evidence exists but is weak (below tau_answer) or the
    top two candidates are within min_margin of each other, i.e. the
    gate cannot discriminate. Routes to the human approval path of
    Vol. 12 rather than guessing.
    """
    surviving = [(uid, s) for uid, s in ranked if s > 0.0]
    if not surviving or surviving[0][1] < tau_refuse:
        return GateDecision(
            REFUSE, (),
            f"no evidence above tau_refuse={tau_refuse} in corpus as of t={query_time}",
            query_time,
        )

    top_id, top_score = surviving[0]
    if top_score < tau_answer:
        return GateDecision(
            REVIEW, tuple(uid for uid, _ in surviving),
            f"top score {top_score:.3f} below tau_answer={tau_answer}",
            query_time,
        )

    if len(surviving) > 1:
        second = surviving[1][1]
        if top_score > 0 and (top_score - second) / top_score < min_margin:
            return GateDecision(
                REVIEW, tuple(uid for uid, _ in surviving),
                f"top-2 margin {(top_score - second) / top_score:.3f} below min_margin={min_margin}",
                query_time,
            )

    return GateDecision(
        ANSWER, tuple(uid for uid, _ in surviving),
        f"top score {top_score:.3f} cleared tau_answer={tau_answer}", query_time,
    )


def query_as_of(
    units: Sequence[TemporalUnit],
    query: str,
    t: int,
    *,
    top_n: int = 10,
    **gate_kwargs,
) -> GateDecision:
    """Full path: scope corpus to t, rank with BM25, apply the 3-way gate."""
    corpus = as_of(units, t)
    if not corpus:
        return GateDecision(REFUSE, (), f"empty corpus as of t={t}", t)
    index = Bm25Index.build(corpus)
    return decide(index.rank(query, top_n=top_n), t, **gate_kwargs)


# --------------------------------------------------------------------------
# Metric
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class TemporalQueryRecord:
    """One query's returned evidence, for leakage auditing."""
    query_id: str
    query_time: int
    returned: tuple[str, ...]


def temporal_leakage_rate(
    records: Sequence[TemporalQueryRecord],
    units: Sequence[TemporalUnit],
) -> float:
    """Fraction of returned evidence that was not valid at query time.

    A non-zero value means the system answered using facts it could not
    have known at the time it was asked about -- future-information
    leakage. Unlike the accuracy metrics in metrics.py, the target is
    not "high" but exactly 0.0: any leak invalidates as-of replay.

    Unknown unit ids count as leaks, since evidence that cannot be
    resolved to a validity interval cannot be shown to be admissible.
    """
    by_id = {u.unit_id: u for u in units}
    total = leaked = 0
    for r in records:
        for uid in r.returned:
            total += 1
            u = by_id.get(uid)
            if u is None or not u.valid_at(r.query_time):
                leaked += 1
    return leaked / total if total else 0.0
