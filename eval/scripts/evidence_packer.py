"""Budget-constrained evidence packing: pick WHAT to send, not how to shorten it.

Once the wire envelope is down to ~5% of the payload (wire_contract.py) and
evidence text is off-limits to compression, the only remaining freedom is the
choice of blocks. That makes it a budgeted subset-selection problem rather than
a compression problem, which is a setting with real guarantees attached.

Why coverage and not top-k
--------------------------
Top-k truncation fills the budget with whatever ranked highest, so it happily
spends tokens on a block whose every concept is already covered by a block
above it. In the exploratory 20-block English fixture documented in
WIRE_CONTRACT_ADVANCED.md Round 6, cost-scaled greedy coverage beat top-k by
61.3% weighted concept coverage at a 25% token budget. This is a proxy-metric
result, not an answer-quality result; production replacement of top-k remains
gated on the four-way model A/B specified in that document.

Note this is concept-level redundancy, not duplicate text: SimHash over the same
corpus found only 8 near-duplicate pairs among 277 blocks, so text-level
deduplication was measured and dropped. The redundancy that wastes budget is
overlap in what blocks are *about*.

Method
------
Weighted coverage is monotone submodular, so the cost-scaled greedy of Lin &
Bilmes (2011) applies, with the classic (1 - 1/e) greedy result of Nemhauser,
Wolsey & Fisher (1978) behind the cardinality-constrained case. Lazy evaluation
(Minoux 1978) exploits the fact that marginal gains can only shrink, so a stale
upper bound that already loses to the current best need not be recomputed.

Determinism: every tie is broken on content_id, so a given candidate set always
produces the same selection in the same order -- packing must not break
bitwise-identical replay (claim:replay).

No external dependencies and no network calls, per Vol. 06 sec:eval:philosophy.
"""
from __future__ import annotations

import heapq
import math
import re
from collections import Counter
from dataclasses import dataclass

_WORD = re.compile(r"[0-9A-Za-z_가-힣]+")
_HANGUL = re.compile(r"[가-힣]")

# Korean content nouns are very often two syllables (증거, 거부, 관계, 시점), so a
# single minimum length applied to both scripts silently drops most of the
# Korean concept layer -- which for a Korean-first product is the layer that
# matters. Hangul tokens therefore qualify at 2 characters, Latin at 3.
MIN_LEN_LATIN = 3
MIN_LEN_HANGUL = 2

# A concept appearing in more than this fraction of blocks is corpus-wide
# vocabulary, not evidence of anything, and is dropped rather than down-weighted.
# Which words are uninformative is a property of the corpus, not a fixed list:
# "plugin" is noise in a plugin repository and signal anywhere else.
MAX_DF_RATIO = 1 / 3


@dataclass(frozen=True)
class Candidate:
    """One retrievable block, with its token cost already known."""
    content_id: str
    concepts: frozenset[str]
    cost: int             # tokens the block's text occupies on the wire
    score: float = 0.0    # gate/retrieval score, used only as a fallback signal


def extract_concepts(text: str) -> frozenset[str]:
    """Cheap stand-in for the concept layer: content words, case-folded.

    Deliberately not a stoplist -- see MAX_DF_RATIO. The minimum length is
    script-dependent because a Korean two-syllable noun carries as much as an
    English five-letter one.
    """
    out = set()
    for w in _WORD.findall(text.lower()):
        floor = MIN_LEN_HANGUL if _HANGUL.search(w) else MIN_LEN_LATIN
        if len(w) >= floor:
            out.add(w)
    return frozenset(out)


def concept_weights(
    cands: list[Candidate],
    max_df_ratio: float = MAX_DF_RATIO,
) -> dict[str, float]:
    """idf weight per concept, with corpus-wide vocabulary dropped entirely.

    Weight is ln(n/df) + 1 so that every retained concept is worth something;
    concepts above max_df_ratio are omitted from the mapping, and `coverage`
    scores an absent concept as 0. Dropping rather than down-weighting matters:
    with dozens of ubiquitous words, a small positive weight each still adds up
    to enough to sway the selection.

    max_df_ratio is not applied when there are too few candidates for a document
    frequency to mean anything (a concept in 1 of 2 blocks is not vault-wide).
    """
    if not cands:
        return {}
    df: Counter[str] = Counter()
    for c in cands:
        df.update(c.concepts)
    n = len(cands)
    cutoff = n * max_df_ratio if n >= 4 else n + 1
    return {t: math.log(n / d) + 1.0 for t, d in df.items() if d <= cutoff}


def coverage(selected_concepts: frozenset[str], weights: dict[str, float]) -> float:
    return sum(weights.get(t, 0.0) for t in selected_concepts)


def pack_topk(cands: list[Candidate], budget: int) -> list[Candidate]:
    """Baseline: score order, stop at the first block that does not fit."""
    ordered = sorted(cands, key=lambda c: (-c.score, c.content_id))
    out, used = [], 0
    for c in ordered:
        if used + c.cost > budget:
            break
        out.append(c)
        used += c.cost
    return out


def pack_greedy(
    cands: list[Candidate],
    budget: int,
    weights: dict[str, float] | None = None,
) -> list[Candidate]:
    """Cost-scaled lazy greedy maximisation of weighted concept coverage.

    Each step takes the candidate with the best marginal-gain-per-token among
    those that still fit. A candidate whose concepts are already covered has
    gain 0 and is never chosen while anything with positive gain fits, which is
    what stops the budget going on restatement.

    Ties on the gain ratio are broken by content_id so the result is a
    deterministic function of the input set, independent of input order.
    """
    if budget <= 0 or not cands:
        return []
    if weights is None:
        weights = concept_weights(cands)

    pool = sorted(cands, key=lambda c: c.content_id)
    selected: list[Candidate] = []
    covered: frozenset[str] = frozenset()
    used = 0

    # max-heap on (ratio, -index) via negation; ratio is an upper bound that
    # only ever decreases as `covered` grows, which is what makes lazy re-
    # evaluation sound for a monotone submodular objective.
    heap: list[tuple[float, int]] = []
    for i, c in enumerate(pool):
        if c.cost > 0:
            heapq.heappush(heap, (-coverage(c.concepts, weights) / c.cost, i))

    while heap:
        neg_ratio, i = heapq.heappop(heap)
        c = pool[i]
        if used + c.cost > budget:
            continue                      # cannot fit; drop it permanently
        gain = coverage(covered | c.concepts, weights) - coverage(covered, weights)
        fresh = gain / c.cost if c.cost else 0.0
        if fresh <= 0.0:
            continue                      # contributes nothing new
        # If the recomputed key still wins against the next stale bound, it is
        # the true maximum and can be taken; otherwise push it back.
        # The comparison is on the full key, index included: comparing ratios
        # alone lets a tie be settled by whichever entry happened to surface
        # first, which diverges from content_id order and so from the reference
        # implementation. Selection has to be a function of the input set only.
        if heap and (-fresh, i) > heap[0]:
            heapq.heappush(heap, (-fresh, i))
            continue
        selected.append(c)
        covered = covered | c.concepts
        used += c.cost

    return selected


def pack_greedy_naive(
    cands: list[Candidate],
    budget: int,
    weights: dict[str, float] | None = None,
) -> list[Candidate]:
    """Unaccelerated reference implementation, for testing pack_greedy."""
    if budget <= 0 or not cands:
        return []
    if weights is None:
        weights = concept_weights(cands)
    remaining = sorted(cands, key=lambda c: c.content_id)
    selected: list[Candidate] = []
    covered: frozenset[str] = frozenset()
    used = 0
    while True:
        best, best_ratio = None, 0.0
        base = coverage(covered, weights)
        for c in remaining:
            if used + c.cost > budget or c.cost <= 0:
                continue
            ratio = (coverage(covered | c.concepts, weights) - base) / c.cost
            if ratio > best_ratio:
                best, best_ratio = c, ratio
        if best is None:
            return selected
        selected.append(best)
        covered = covered | best.concepts
        used += best.cost
        remaining.remove(best)


def pack(
    cands: list[Candidate],
    budget: int,
    *,
    singleton_fallback: bool = True,
) -> list[Candidate]:
    """Greedy pack, with the Lin & Bilmes singleton guard.

    A single high-value block can be worth more than everything greedy fits
    around it; comparing against the best affordable singleton is what makes the
    budgeted variant's constant-factor bound hold.
    """
    weights = concept_weights(cands)
    greedy = pack_greedy(cands, budget, weights)
    if not singleton_fallback:
        return greedy
    affordable = [c for c in cands if c.cost <= budget]
    if not affordable:
        return greedy
    best_single = max(
        affordable,
        key=lambda c: (coverage(c.concepts, weights), c.content_id),
    )
    g_cov = coverage(frozenset().union(*[c.concepts for c in greedy]) if greedy
                     else frozenset(), weights)
    return greedy if g_cov >= coverage(best_single.concepts, weights) else [best_single]


def packed_cost(sel: list[Candidate]) -> int:
    return sum(c.cost for c in sel)


def coverage_of(sel: list[Candidate], weights: dict[str, float]) -> float:
    if not sel:
        return 0.0
    return coverage(frozenset().union(*[c.concepts for c in sel]), weights)
