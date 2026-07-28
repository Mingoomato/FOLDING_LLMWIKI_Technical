"""Unit tests for evidence_packer.py. Run: python -m pytest eval/scripts/test_evidence_packer.py -v
or, with no pytest available: python eval/scripts/test_evidence_packer.py

The load-bearing ones: test_lazy_matches_naive (the acceleration must not change
the answer), test_determinism_* (packing must not break bitwise replay), and
test_greedy_beats_topk_on_redundant_set (the reason this module exists).
"""
from evidence_packer import (
    Candidate,
    concept_weights,
    coverage,
    coverage_of,
    extract_concepts,
    pack,
    pack_greedy,
    pack_greedy_naive,
    pack_topk,
    packed_cost,
)


def cand(cid, words, cost, score=0.5):
    return Candidate(cid, frozenset(words.split()), cost, score)


# a: unique concepts; b: restates a; c: adds new ground cheaply
REDUNDANT = [
    cand("c1", "alpha beta gamma", 10, score=0.9),
    cand("c2", "alpha beta gamma", 10, score=0.8),   # pure restatement of c1
    cand("c3", "delta epsilon zeta", 10, score=0.1),  # new ground, low score
]


# -- concept extraction ----------------------------------------------------

def test_extract_drops_short_tokens():
    assert "of" not in extract_concepts("proof of work")
    assert "proof" in extract_concepts("proof of work")


def test_extract_is_case_folded():
    assert extract_concepts("Rust rust RUST") == frozenset({"rust"})


def test_extract_handles_korean():
    c = extract_concepts("증거 게이트는 거부한다")
    assert any("증거" in x for x in c)


def test_extract_empty_text():
    assert extract_concepts("") == frozenset()


# -- weighting -------------------------------------------------------------

def test_ubiquitous_concept_weighs_least():
    w = concept_weights(REDUNDANT)
    # alpha is in 2 of 3; delta in 1 of 3 -> delta must outweigh alpha
    assert w["delta"] > w["alpha"]


def test_weights_are_positive():
    w = concept_weights(REDUNDANT)
    assert all(v > 0 for v in w.values()), "a zero weight makes coverage indifferent"


def test_weights_of_empty_input():
    assert concept_weights([]) == {}


# -- the point of the module ----------------------------------------------

def test_greedy_beats_topk_on_redundant_set():
    """Budget fits 2 of 3 blocks. top-k takes c1+c2 (identical concepts);
    greedy must take c1+c3 and cover twice the ground."""
    w = concept_weights(REDUNDANT)
    t = pack_topk(REDUNDANT, budget=20)
    g = pack_greedy(REDUNDANT, budget=20)
    assert packed_cost(t) <= 20 and packed_cost(g) <= 20
    assert coverage_of(g, w) > coverage_of(t, w), (
        f"greedy {coverage_of(g, w):.3f} should beat top-k {coverage_of(t, w):.3f}"
    )


def test_topk_really_does_pick_the_restatement():
    ids = [c.content_id for c in pack_topk(REDUNDANT, budget=20)]
    assert ids == ["c1", "c2"], "baseline must be the naive one we claim to beat"


def test_greedy_skips_pure_restatement():
    ids = {c.content_id for c in pack_greedy(REDUNDANT, budget=20)}
    assert "c3" in ids, "greedy must prefer new ground over a restatement"


def test_zero_gain_candidate_never_selected_while_budget_remains():
    dup = REDUNDANT[:2]          # c2 adds nothing over c1
    sel = pack_greedy(dup, budget=100)
    assert len(sel) == 1, "a candidate with no marginal gain must not be taken"


# -- lazy acceleration must be exact --------------------------------------

def test_lazy_matches_naive():
    for b in (0, 5, 10, 15, 20, 25, 30, 100):
        lazy = [c.content_id for c in pack_greedy(REDUNDANT, b)]
        naive = [c.content_id for c in pack_greedy_naive(REDUNDANT, b)]
        assert lazy == naive, f"budget {b}: lazy {lazy} != naive {naive}"


def _big_set():
    return [cand(f"c{i:03d}", f"w{i} w{i%5} w{i%7} shared", 3 + i % 4, score=1 - i / 50)
            for i in range(30)]


def test_lazy_matches_naive_objective_on_larger_set():
    """Lazy evaluation must not cost objective value.

    It is not required to reproduce the reference implementation's tie order:
    when several candidates have exactly equal marginal gain, which one is
    confirmed first depends on the stale upper bounds still in the heap. Equal
    coverage at equal cost is the guarantee that matters; per-run determinism is
    covered by test_determinism_* below.
    """
    big = _big_set()
    w = concept_weights(big)
    for b in (10, 25, 50, 90):
        lz, nv = pack_greedy(big, b), pack_greedy_naive(big, b)
        assert abs(coverage_of(lz, w) - coverage_of(nv, w)) < 1e-9, \
            f"budget {b}: lazy coverage {coverage_of(lz, w)} != naive {coverage_of(nv, w)}"
        assert packed_cost(lz) == packed_cost(nv), f"budget {b}: cost differs"


def test_lazy_is_deterministic_on_larger_set():
    """The property replay actually needs: same input, same output, every time."""
    big = _big_set()
    first = [c.content_id for c in pack_greedy(big, 90)]
    for _ in range(5):
        assert [c.content_id for c in pack_greedy(big, 90)] == first
    shuffled = list(reversed(big))
    assert [c.content_id for c in pack_greedy(shuffled, 90)] == first, \
        "selection must not depend on input order"


# -- determinism -----------------------------------------------------------

def test_determinism_independent_of_input_order():
    a = [c.content_id for c in pack_greedy(REDUNDANT, 20)]
    b = [c.content_id for c in pack_greedy(list(reversed(REDUNDANT)), 20)]
    assert a == b, "selection must not depend on candidate order"


def test_determinism_repeated_calls():
    a = [c.content_id for c in pack_greedy(REDUNDANT, 20)]
    for _ in range(5):
        assert [c.content_id for c in pack_greedy(REDUNDANT, 20)] == a


def test_equal_ratio_tie_broken_by_content_id():
    twins = [cand("c_b", "x y", 4, 0.5), cand("c_a", "p q", 4, 0.5)]
    sel = pack_greedy(twins, budget=4)
    assert len(sel) == 1 and sel[0].content_id == "c_a", "ties resolve on content_id"


# -- budget is a hard constraint ------------------------------------------

def test_never_exceeds_budget():
    for b in range(0, 40):
        assert packed_cost(pack_greedy(REDUNDANT, b)) <= b


def test_zero_budget_selects_nothing():
    assert pack_greedy(REDUNDANT, 0) == []


def test_negative_budget_selects_nothing():
    assert pack_greedy(REDUNDANT, -5) == []


def test_budget_smaller_than_every_block():
    assert pack_greedy(REDUNDANT, 1) == []


def test_zero_cost_candidate_does_not_divide_by_zero():
    weird = [Candidate("c0", frozenset({"a"}), 0, 0.5), REDUNDANT[0]]
    pack_greedy(weird, budget=20)     # must not raise


# -- singleton fallback ---------------------------------------------------

def test_singleton_fallback_never_lowers_coverage():
    w = concept_weights(REDUNDANT)
    for b in (10, 20, 30):
        assert coverage_of(pack(REDUNDANT, b), w) >= \
               coverage_of(pack(REDUNDANT, b, singleton_fallback=False), w)


def test_singleton_fallback_respects_budget():
    for b in range(0, 40):
        assert packed_cost(pack(REDUNDANT, b)) <= b


def test_empty_candidates():
    assert pack([], 100) == [] and pack_greedy([], 100) == [] and pack_topk([], 100) == []


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
