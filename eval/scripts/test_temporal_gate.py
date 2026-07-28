"""Unit tests for temporal_gate.py. Run: python -m pytest eval/scripts/test_temporal_gate.py -v
or, with no pytest available: python eval/scripts/test_temporal_gate.py

The falsification tests for TECH_COMPETITIVENESS_PLAN.md's narrow novelty
claim are test_refuses_before_evidence_exists / test_answers_once_evidence_valid
(a query is refused at t=1 and answered at t=2 on the same corpus, differing
only in the as-of bound) and test_leakage_is_zero_through_as_of_path.
"""
from temporal_gate import (
    ANSWER,
    REFUSE,
    REVIEW,
    GateDecision,
    TemporalQueryRecord,
    TemporalUnit,
    as_of,
    decide,
    query_as_of,
    temporal_leakage_rate,
)


# The fact "heap_push maintains the invariant" only becomes valid at t=2.
CORPUS = [
    TemporalUnit("u_unrelated", "socket timeout retry backoff network", 0),
    TemporalUnit("u_heap", "heap_push maintains the heap invariant by sifting up", 2),
    TemporalUnit("u_super", "queue uses a plain list as its container", 1, 3),
]


# -- validity interval semantics -------------------------------------------

def test_valid_at_half_open_interval():
    u = TemporalUnit("x", "t", 1, 3)
    assert not u.valid_at(0)
    assert u.valid_at(1)
    assert u.valid_at(2)
    assert not u.valid_at(3), "valid_to must be exclusive"


def test_open_interval_never_expires():
    u = TemporalUnit("x", "t", 1, None)
    assert u.valid_at(1) and u.valid_at(10_000)


def test_as_of_hides_future_and_superseded():
    assert set(as_of(CORPUS, 0)) == {"u_unrelated"}
    assert set(as_of(CORPUS, 1)) == {"u_unrelated", "u_super"}
    assert set(as_of(CORPUS, 2)) == {"u_unrelated", "u_super", "u_heap"}
    # u_super is superseded at t=3 -- present in history, not in the as-of view
    assert set(as_of(CORPUS, 3)) == {"u_unrelated", "u_heap"}


# -- time-scoped refusal (the novelty claim) --------------------------------

def test_refuses_before_evidence_exists():
    d = query_as_of(CORPUS, "heap invariant sifting", t=1)
    assert d.action == REFUSE, f"expected REFUSE, got {d.action}: {d.reason}"
    assert d.evidence == ()
    assert "t=1" in d.reason, "refusal must report the time bound that produced it"


def test_answers_once_evidence_valid():
    d = query_as_of(CORPUS, "heap invariant sifting", t=2)
    assert d.action == ANSWER, f"expected ANSWER, got {d.action}: {d.reason}"
    assert "u_heap" in d.evidence


def test_refusal_and_answer_differ_only_in_as_of_bound():
    """Same corpus, same query -- only the time bound changes the outcome."""
    q = "heap invariant sifting"
    assert query_as_of(CORPUS, q, t=1).action == REFUSE
    assert query_as_of(CORPUS, q, t=2).action == ANSWER


def test_refusal_is_reproducible():
    a = query_as_of(CORPUS, "heap invariant sifting", t=1)
    b = query_as_of(CORPUS, "heap invariant sifting", t=1)
    assert a == b, "same inputs must yield an identical decision"


def test_empty_corpus_refuses():
    d = query_as_of(CORPUS, "anything", t=-1)
    assert d.action == REFUSE and "empty corpus" in d.reason


# -- 3-way decision --------------------------------------------------------

def test_review_on_weak_evidence():
    d = decide([("a", 1.0)], query_time=0, tau_refuse=0.5, tau_answer=2.0)
    assert d.action == REVIEW and d.evidence == ("a",)


def test_review_on_indiscriminable_top_two():
    d = decide([("a", 5.0), ("b", 4.9)], query_time=0, tau_answer=2.0, min_margin=0.15)
    assert d.action == REVIEW, "gate must not pick between candidates it cannot separate"


def test_answer_on_clear_winner():
    d = decide([("a", 5.0), ("b", 1.0)], query_time=0, tau_answer=2.0, min_margin=0.15)
    assert d.action == ANSWER and d.evidence == ("a", "b")


def test_refuse_when_all_below_threshold():
    d = decide([("a", 0.2)], query_time=0, tau_refuse=0.5)
    assert d.action == REFUSE and d.evidence == ()


def test_zero_scores_are_not_evidence():
    d = decide([("a", 0.0), ("b", 0.0)], query_time=0)
    assert d.action == REFUSE


def test_three_actions_are_distinct():
    assert len({ANSWER, REFUSE, REVIEW}) == 3


# -- temporal leakage metric -----------------------------------------------

def test_leakage_is_zero_through_as_of_path():
    """Evidence obtained via query_as_of must never leak future facts."""
    recs = []
    for t in (0, 1, 2, 3):
        d = query_as_of(CORPUS, "heap invariant queue container", t=t)
        recs.append(TemporalQueryRecord(f"q{t}", t, d.evidence))
    assert temporal_leakage_rate(recs, CORPUS) == 0.0


def test_leakage_detects_future_evidence():
    """A retrieval that ignores validity must be caught by the metric."""
    leaky = [TemporalQueryRecord("q", 1, ("u_unrelated", "u_heap"))]  # u_heap valid from 2
    assert temporal_leakage_rate(leaky, CORPUS) == 0.5


def test_leakage_detects_superseded_evidence():
    leaky = [TemporalQueryRecord("q", 5, ("u_super",))]  # valid [1,3)
    assert temporal_leakage_rate(leaky, CORPUS) == 1.0


def test_unknown_unit_counts_as_leak():
    recs = [TemporalQueryRecord("q", 0, ("does_not_exist",))]
    assert temporal_leakage_rate(recs, CORPUS) == 1.0


def test_leakage_of_no_evidence_is_zero_not_error():
    assert temporal_leakage_rate([TemporalQueryRecord("q", 0, ())], CORPUS) == 0.0


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
