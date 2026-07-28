"""Unit tests for metrics.py. Run: python -m pytest eval/scripts/test_metrics.py -v
or, with no pytest available: python eval/scripts/test_metrics.py
"""
from metrics import (
    ContextEfficiencyRecord,
    QueryResult,
    budget_utilisation,
    coverage_per_token,
    evidence_recall_at_k,
    evidence_precision_at_k,
    evidence_f1_at_k,
    gate_rejection_rate,
    attribution_score,
    lexical_overlap_nli_stub,
    cohens_kappa,
    bootstrap_ci,
    quality_at_budget,
    refusal_token_cost,
    tokens_per_answered_query,
)


def test_evidence_recall_perfect():
    r = QueryResult("q1", frozenset({"a", "b"}), (), ("a", "b", "c"))
    assert evidence_recall_at_k([r], k=3) == 1.0


def test_evidence_recall_partial():
    r = QueryResult("q1", frozenset({"a", "b"}), (), ("a", "c", "d"))
    assert evidence_recall_at_k([r], k=3) == 0.5


def test_evidence_precision():
    r = QueryResult("q1", frozenset({"a", "b"}), (), ("a", "c", "d"))
    # top-3 = {a,c,d}, intersect gt = {a} -> 1/3
    assert abs(evidence_precision_at_k([r], k=3) - (1 / 3)) < 1e-9


def test_evidence_f1_matches_harmonic_mean():
    r = QueryResult("q1", frozenset({"a", "b"}), (), ("a", "b"))
    p = evidence_precision_at_k([r], k=2)
    rec = evidence_recall_at_k([r], k=2)
    f1 = evidence_f1_at_k([r], k=2)
    assert p == 1.0 and rec == 1.0 and f1 == 1.0


def test_evidence_f1_zero_when_no_overlap():
    r = QueryResult("q1", frozenset({"a"}), (), ("x", "y"))
    assert evidence_f1_at_k([r], k=2) == 0.0


def test_gate_rejection_rate():
    r1 = QueryResult("q1", frozenset(), ("a", "b", "c", "d"), ("a", "b"))
    r2 = QueryResult("q2", frozenset(), ("a", "b"), ("a",))
    # total candidates = 6, total verified = 3 -> reject = 3/6 = 0.5
    assert gate_rejection_rate([r1, r2]) == 0.5


def test_attribution_score_supported_claim():
    unit_text = {"e1": "the function validates currency before processing"}
    r = QueryResult(
        "q1", frozenset(), (), (),
        answer_claims=("the function validates currency",),
        claim_citations={"the function validates currency": ("e1",)},
    )
    assert attribution_score(r, unit_text) == 1.0


def test_attribution_score_unsupported_claim():
    unit_text = {"e1": "completely unrelated text about weather patterns"}
    r = QueryResult(
        "q1", frozenset(), (), (),
        answer_claims=("the function validates currency",),
        claim_citations={"the function validates currency": ("e1",)},
    )
    assert attribution_score(r, unit_text) == 0.0


def test_lexical_overlap_nli_stub_threshold():
    assert lexical_overlap_nli_stub("cat sat on mat", "cat sat", threshold=0.5) is True
    assert lexical_overlap_nli_stub("cat sat on mat", "dog ran fast", threshold=0.5) is False


def test_cohens_kappa_perfect_agreement():
    a = ["yes", "no", "yes", "no"]
    b = ["yes", "no", "yes", "no"]
    assert cohens_kappa(a, b) == 1.0


def test_cohens_kappa_chance_agreement_near_zero():
    # Deliberately anti-correlated but balanced -> kappa should be low/negative, not near 1
    a = ["yes", "no", "yes", "no"]
    b = ["no", "yes", "no", "yes"]
    k = cohens_kappa(a, b)
    assert k < 0.5


def test_bootstrap_ci_shape():
    point, lo, hi = bootstrap_ci([0.7, 0.8, 0.75, 0.72, 0.79], resamples=200, seed=1)
    assert lo <= point <= hi


def test_tokens_per_answered_query_is_median():
    records = [
        ContextEfficiencyRecord("q1", 100, 200, True),
        ContextEfficiencyRecord("q2", 300, 400, True),
        ContextEfficiencyRecord("q3", 999, 1000, False),
    ]
    assert tokens_per_answered_query(records) == 200.0


def test_coverage_per_token():
    record = ContextEfficiencyRecord("q", 20, 100, True, weighted_coverage=50.0)
    assert coverage_per_token(record) == 2.5


def test_budget_utilisation():
    record = ContextEfficiencyRecord("q", 75, 100, True)
    assert budget_utilisation(record) == 0.75


def test_quality_at_budget_returns_curve():
    records = [
        ContextEfficiencyRecord("q1", 25, 100, True, evidence_f1=0.4, budget_fraction=0.25),
        ContextEfficiencyRecord("q2", 25, 100, True, evidence_f1=0.6, budget_fraction=0.25),
        ContextEfficiencyRecord("q3", 50, 100, True, evidence_f1=0.8, budget_fraction=0.5),
    ]
    assert quality_at_budget(records) == {0.25: 0.5, 0.5: 0.8}


def test_refusal_token_cost():
    records = [
        ContextEfficiencyRecord("q1", 40, 100, False),
        ContextEfficiencyRecord("q2", 60, 100, False),
        ContextEfficiencyRecord("q3", 80, 100, True),
    ]
    assert refusal_token_cost(records) == 50.0


def _run_all():
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    _run_all()
