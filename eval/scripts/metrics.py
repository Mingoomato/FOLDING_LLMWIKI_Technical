"""LLMWikiBench metric implementations.

Implements the metric definitions from Vol. 06 (Evaluation Framework):
evidence retrieval and attribution metrics plus the context-efficiency axis
used to evaluate WC/1 and budgeted evidence packing. Each function's docstring
cites the LaTeX label it implements so the two stay checkable against each
other.

This module has no external dependencies and no network calls, per the
Local-First Evaluation design principle (Vol. 06 sec:eval:philosophy).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence


@dataclass(frozen=True)
class QueryResult:
    """One query's ground truth and system output, for a single eval run."""
    query_id: str
    ground_truth_evidence: frozenset[str]      # E*(q): human-annotated unit ids
    retrieved_candidates: tuple[str, ...]       # R(q): pre-gate candidate ids, ranked
    gate_verified: tuple[str, ...]              # E(q): candidates surviving the evidence gate, ranked
    answer_claims: tuple[str, ...] = field(default_factory=tuple)   # atomic claims extracted from the answer
    claim_citations: dict[str, tuple[str, ...]] = field(default_factory=dict)  # claim -> cited unit ids


@dataclass(frozen=True)
class ContextEfficiencyRecord:
    """One query's measured context cost and quality at a budget setting."""
    query_id: str
    prompt_tokens: int
    context_budget: int
    answered: bool
    weighted_coverage: float = 0.0
    evidence_f1: float = 0.0
    budget_fraction: float = 1.0


def evidence_recall_at_k(results: Sequence[QueryResult], k: int) -> float:
    """EvRecall@k -- Vol. 06 def:evidence-recall.

    (1/|Q|) * sum_q |E*(q) intersect E_k(q)| / |E*(q)|
    E_k(q) is the gate-verified top-k, truncated here to the first k entries
    of `gate_verified` (which is expected to already be gate-filtered and
    ranked, matching Algorithm evidence-gate's SortByScoreDesc output).
    """
    if not results:
        return 0.0
    total = 0.0
    counted = 0
    for r in results:
        if not r.ground_truth_evidence:
            continue
        top_k = frozenset(r.gate_verified[:k])
        total += len(r.ground_truth_evidence & top_k) / len(r.ground_truth_evidence)
        counted += 1
    return total / counted if counted else 0.0


def evidence_precision_at_k(results: Sequence[QueryResult], k: int) -> float:
    """EvPrecision@k -- Vol. 06 def:evidence-precision.

    (1/|Q|) * sum_q |E*(q) intersect E_k(q)| / |E_k(q)|
    """
    if not results:
        return 0.0
    total = 0.0
    counted = 0
    for r in results:
        top_k = frozenset(r.gate_verified[:k])
        if not top_k:
            continue
        total += len(r.ground_truth_evidence & top_k) / len(top_k)
        counted += 1
    return total / counted if counted else 0.0


def evidence_f1_at_k(results: Sequence[QueryResult], k: int) -> float:
    """Evidence F1@k -- Vol. 06 def:evidence-f1. Harmonic mean of the above."""
    p = evidence_precision_at_k(results, k)
    r = evidence_recall_at_k(results, k)
    if p + r == 0:
        return 0.0
    return 2 * p * r / (p + r)


def gate_rejection_rate(results: Sequence[QueryResult]) -> float:
    """GateReject -- Vol. 06 def:gate-rejection.

    (|R| - |E|) / |R|, aggregated over all queries (not averaged per-query,
    matching the definition's use of set cardinalities rather than a mean
    of per-query rates).
    """
    total_candidates = sum(len(r.retrieved_candidates) for r in results)
    total_verified = sum(len(r.gate_verified) for r in results)
    if total_candidates == 0:
        return 0.0
    return (total_candidates - total_verified) / total_candidates


NliJudge = Callable[[str, str], bool]  # (evidence_text, claim_text) -> entailed?


def lexical_overlap_nli_stub(evidence_text: str, claim_text: str, threshold: float = 0.5) -> bool:
    """Placeholder NLI judge: token-overlap ratio >= threshold.

    This is NOT a substitute for the NLI model specified in Vol. 04
    (sec:retrieval:synthesis) and Vol. 06 (def:attribution) -- it exists so
    attribution_score() is runnable offline, with zero external calls, for
    the toy corpus in this scaffold. Swap in a real NLI model (loaded
    locally, e.g. a small cross-encoder) before trusting this metric on a
    scaled-up corpus; a lexical-overlap stub will systematically
    over-credit claims that share vocabulary with their evidence without
    actually being entailed by it.
    """
    ev_tokens = set(evidence_text.lower().split())
    claim_tokens = set(claim_text.lower().split())
    if not claim_tokens:
        return False
    overlap = len(ev_tokens & claim_tokens) / len(claim_tokens)
    return overlap >= threshold


def attribution_score(
    result: QueryResult,
    unit_text: dict[str, str],
    nli_judge: NliJudge = lexical_overlap_nli_stub,
) -> float:
    """Attribution Score -- Vol. 06 def:attribution.

    (1/n) * sum_i 1[exists e in citations(c_i): NLI(e, c_i) = Entailment]
    """
    if not result.answer_claims:
        return 0.0
    supported = 0
    for claim in result.answer_claims:
        cited_units = result.claim_citations.get(claim, ())
        if any(nli_judge(unit_text.get(u, ""), claim) for u in cited_units):
            supported += 1
    return supported / len(result.answer_claims)


def tokens_per_answered_query(records: Sequence[ContextEfficiencyRecord]) -> float:
    """Median prompt tokens for answered queries -- Vol. 06
    def:tokens-per-answered-query.
    """
    values = sorted(r.prompt_tokens for r in records if r.answered)
    if not values:
        return 0.0
    middle = len(values) // 2
    if len(values) % 2:
        return float(values[middle])
    return (values[middle - 1] + values[middle]) / 2


def coverage_per_token(record: ContextEfficiencyRecord) -> float:
    """Weighted concept coverage per prompt token -- Vol. 06
    def:coverage-per-token.
    """
    return record.weighted_coverage / record.prompt_tokens if record.prompt_tokens > 0 else 0.0


def budget_utilisation(record: ContextEfficiencyRecord) -> float:
    """Used prompt tokens divided by the configured budget -- Vol. 06
    def:budget-utilisation.
    """
    return record.prompt_tokens / record.context_budget if record.context_budget > 0 else 0.0


def quality_at_budget(records: Sequence[ContextEfficiencyRecord]) -> dict[float, float]:
    """Mean Evidence F1 at each budget fraction -- Vol. 06
    def:quality-at-budget.
    """
    grouped: dict[float, list[float]] = {}
    for record in records:
        grouped.setdefault(record.budget_fraction, []).append(record.evidence_f1)
    return {
        fraction: sum(values) / len(values)
        for fraction, values in sorted(grouped.items())
    }


def refusal_token_cost(records: Sequence[ContextEfficiencyRecord]) -> float:
    """Mean prompt-token cost of refused queries -- Vol. 06
    def:refusal-token-cost.
    """
    values = [r.prompt_tokens for r in records if not r.answered]
    return sum(values) / len(values) if values else 0.0


def cohens_kappa(rater_a: Sequence[str], rater_b: Sequence[str]) -> float:
    """Cohen's kappa for inter-annotator agreement -- used by the annotation
    protocol (eval/annotation/PROTOCOL.md) to gate acceptance at kappa > 0.8
    per Vol. 06's Construction Process step 5. Two raters' per-item
    categorical labels (equal length, same item order) in.
    """
    if len(rater_a) != len(rater_b) or not rater_a:
        raise ValueError("rater_a and rater_b must be non-empty and equal length")
    n = len(rater_a)
    labels = sorted(set(rater_a) | set(rater_b))
    observed_agreement = sum(a == b for a, b in zip(rater_a, rater_b)) / n
    expected_agreement = 0.0
    for label in labels:
        p_a = rater_a.count(label) / n
        p_b = rater_b.count(label) / n
        expected_agreement += p_a * p_b
    if expected_agreement == 1.0:
        return 1.0
    return (observed_agreement - expected_agreement) / (1 - expected_agreement)


def bootstrap_ci(
    values: Sequence[float],
    resamples: int = 1000,
    confidence: float = 0.95,
    seed: int = 0,
) -> tuple[float, float, float]:
    """Bootstrap confidence interval -- Vol. 06 sec:eval:statistical
    (1000 resamples, 95% CI). Returns (mean, lower, upper).
    """
    import random

    if not values:
        return (0.0, 0.0, 0.0)
    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(resamples):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    alpha = 1 - confidence
    lo_idx = int((alpha / 2) * resamples)
    hi_idx = int((1 - alpha / 2) * resamples) - 1
    point = sum(values) / n
    return (point, means[max(0, lo_idx)], means[min(resamples - 1, hi_idx)])
