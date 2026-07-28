"""WC/1 evidence wire contract — token-lean envelope for LLM-read evidence.

Implements the format specified in WIRE_CONTRACT.md Round 9. The point is to
spend tokens on evidence text and almost nothing on framing. The implementation
measurement, including the fixed contract prefix, cuts the total payload by
30.3% on an English corpus and 32.8% on Korean without relying on prefix-cache
hits (31.7% and 36.6% after the prefix is cached).

Two rules carry the whole design:

  * The evidence text is passed through byte-for-byte. Never normalised,
    reformatted, or abbreviated -- a citation a human cannot verify against the
    source is worth nothing (Vol. 06 attribution_score).
  * Machine identifiers do not go on the wire. The model cites small integers;
    the host resolves those to (content_id, occurrence_id, doc, span). UUIDs
    alone measured 437 tokens, 10.8% of a 20-match payload.

Ambiguity note: an earlier draft delimited blocks by pattern alone, which breaks
the moment evidence text contains a line like "@decorator" or "0 list" -- and
real Markdown does. Each block header therefore carries its line count and the
parser reads exactly that many lines, which makes the format unambiguous for
arbitrary text.

No external dependencies and no network calls, per the Local-First Evaluation
principle (Vol. 06 sec:eval:philosophy). tiktoken is used only by the tests, and
only when it is importable.
"""
from __future__ import annotations

from dataclasses import dataclass

VERSION = "WC/1"

# Query-independent, therefore eligible for prompt-prefix KV caching: the
# contract's instructional cost ("prompt tax") amortises to ~0 from the second
# call on. Must stay byte-identical across queries -- test_prefix_is_query_
# independent enforces that.
PREFIX = (
    "WC/1 evidence envelope. A line '@<path>' names a source file. A line "
    "'<id> <kind> <n>' opens an evidence block whose text is exactly the next "
    "<n> lines, verbatim. Cite evidence by its id."
)


@dataclass(frozen=True)
class EvidenceBlock:
    """One retrieved unit, before serialisation."""
    content_id: str      # SemanticUnit.id -- the tie-break key, never sent
    occurrence_id: str   # UnitOccurrence.occurrence_id -- never sent
    doc: str             # source path, sent once per @ group
    kind: str            # heading | para | list | code | table | quote
    text: str            # verbatim source text; passed through untouched
    score: float = 0.0   # gate score; only its ordering matters on the wire


def quantize_score(score: float, scale: int = 1000) -> int:
    """Float score -> integer, so a serialised score is bit-stable.

    Prefix cache eligibility depends on byte-identical text, and float
    formatting is not stable across builds: the same expression compiled with
    -ffast-math or -march=native differs in its low bits (see
    TECH_COMPETITIVENESS_PLAN.md Round 8). Integers have no such problem.
    """
    if score != score:  # NaN
        return 0
    clamped = 0.0 if score < 0.0 else (1.0 if score > 1.0 else score)
    return int(clamped * scale + 0.5)


def order_blocks(blocks: list[EvidenceBlock]) -> list[EvidenceBlock]:
    """Score descending, ties broken by content_id.

    Descending score puts the strongest evidence first, which is the cheap
    mitigation for position bias -- models attend to the start and end of a long
    context and neglect the middle. The content_id tie-break makes the order a
    deterministic function of the input, so replay stays reproducible.
    """
    return sorted(blocks, key=lambda b: (-b.score, b.content_id))


def serialize(query: str, blocks: list[EvidenceBlock]) -> tuple[str, dict[int, EvidenceBlock]]:
    """Render the query-specific suffix. Returns (wire_text, id -> block).

    The id map stays host-side; it is what turns a model's "[3]" back into a
    verifiable (doc, span) citation.
    """
    if "\n" in query or "\r" in query:
        raise ValueError("WC/1 query must be a single line")
    for block in blocks:
        if not block.doc or "\n" in block.doc or "\r" in block.doc:
            raise ValueError("WC/1 document path must be a non-empty single line")
        if not block.kind or any(ch.isspace() for ch in block.kind):
            raise ValueError("WC/1 block kind must be a non-empty token")

    ordered = order_blocks(blocks)
    lines = [f"Q {query}"]
    id_map: dict[int, EvidenceBlock] = {}
    current_doc: str | None = None
    for i, b in enumerate(ordered):
        id_map[i] = b
        if b.doc != current_doc:
            lines.append(f"@{b.doc}")
            current_doc = b.doc
        body = b.text.split("\n")
        lines.append(f"{i} {b.kind} {len(body)}")
        lines.extend(body)
    return "\n".join(lines), id_map


@dataclass(frozen=True)
class ParsedBlock:
    block_id: int
    kind: str
    doc: str
    text: str


def parse(wire: str) -> tuple[str, list[ParsedBlock]]:
    """Inverse of serialize. Returns (query, blocks) with text byte-identical."""
    lines = wire.split("\n")
    if not lines or not lines[0].startswith("Q "):
        raise ValueError("wire payload must open with a 'Q <query>' line")
    query = lines[0][2:]
    out: list[ParsedBlock] = []
    seen_ids: set[int] = set()
    doc = ""
    i = 1
    while i < len(lines):
        line = lines[i]
        if line.startswith("@"):
            doc = line[1:]
            i += 1
            continue
        head = line.split(" ")
        if len(head) != 3:
            raise ValueError(f"malformed block header at line {i}: {line!r}")
        bid, kind, n = int(head[0]), head[1], int(head[2])
        if not doc:
            raise ValueError(f"block {bid} has no source document")
        if bid < 0 or n < 0:
            raise ValueError(f"block id and line count must be non-negative: {line!r}")
        if bid in seen_ids:
            raise ValueError(f"duplicate block id: {bid}")
        seen_ids.add(bid)
        body = lines[i + 1: i + 1 + n]
        if len(body) != n:
            raise ValueError(f"block {bid} declares {n} lines, found {len(body)}")
        out.append(ParsedBlock(bid, kind, doc, "\n".join(body)))
        i += 1 + n
    return query, out


def resolve_citations(
    cited: list[int],
    id_map: dict[int, EvidenceBlock],
) -> tuple[list[EvidenceBlock], list[int]]:
    """Split cited ids into resolvable blocks and unresolvable ids.

    An id the host did not issue is a fabricated citation, not a lookup miss, so
    it is returned for the caller to reject -- the same refusal path the evidence
    gate uses when nothing clears threshold (Vol. 04).
    """
    ok, bad = [], []
    for c in cited:
        b = id_map.get(c)
        (ok.append(b) if b is not None else bad.append(c))
    return ok, bad


def render_prompt(query: str, blocks: list[EvidenceBlock]) -> str:
    """Full prompt: cacheable prefix + query-specific suffix."""
    suffix, _ = serialize(query, blocks)
    return f"{PREFIX}\n\n{suffix}"


def as_json_payload(query: str, blocks: list[EvidenceBlock]) -> str:
    """The verbose equivalent, for the fallback path and for token comparison.

    Kept because the contract is an optimisation, not a correctness requirement:
    on an unknown version tag, fall back to this rather than guess.
    """
    import json
    ordered = order_blocks(blocks)
    return json.dumps({
        "query": query,
        "matches": [
            {
                "doc": b.doc,
                "block_id": b.occurrence_id,
                "kind": b.kind,
                "level": None,
                "score": b.score,
                "text": b.text,
            }
            for b in ordered
        ],
    }, ensure_ascii=False)
