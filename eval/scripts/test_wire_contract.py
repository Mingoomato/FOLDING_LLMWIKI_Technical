"""Unit tests for wire_contract.py. Run: python -m pytest eval/scripts/test_wire_contract.py -v
or, with no pytest available: python eval/scripts/test_wire_contract.py

These are the acceptance criteria from WIRE_CONTRACT.md Round 10. The ones that
matter most are test_roundtrip_* (evidence text must survive byte-for-byte, or a
citation cannot be checked against the source) and the adversarial-text cases,
which is where the first draft of the format was actually broken.
"""
from wire_contract import (
    PREFIX,
    VERSION,
    EvidenceBlock,
    as_json_payload,
    order_blocks,
    parse,
    quantize_score,
    render_prompt,
    resolve_citations,
    serialize,
)


def blk(cid, doc, kind, text, score=0.5, occ=None):
    return EvidenceBlock(cid, occ or f"occ_{cid}", doc, kind, text, score)


CORPUS = [
    blk("c3", "a/README.md", "para", "The gate refuses when nothing clears tau.", 0.9),
    blk("c1", "a/README.md", "list", "- one\n- two\n- three", 0.7),
    blk("c2", "b/spec.md", "code", "fn main() {\n    println!(\"hi\");\n}", 0.7),
]


# -- round-trip: the non-negotiable one ------------------------------------

def test_roundtrip_preserves_text_byte_for_byte():
    wire, id_map = serialize("gate", CORPUS)
    _, parsed = parse(wire)
    assert len(parsed) == len(CORPUS)
    for p in parsed:
        assert p.text == id_map[p.block_id].text, "evidence text must not be altered"


def test_roundtrip_preserves_query_kind_and_doc():
    wire, id_map = serialize("gate refuses", CORPUS)
    q, parsed = parse(wire)
    assert q == "gate refuses"
    for p in parsed:
        assert p.kind == id_map[p.block_id].kind
        assert p.doc == id_map[p.block_id].doc


def test_roundtrip_multiline_text():
    wire, id_map = serialize("q", [blk("c1", "d.md", "code", "a\nb\nc\nd")])
    _, parsed = parse(wire)
    assert parsed[0].text == "a\nb\nc\nd"


def test_roundtrip_empty_text():
    wire, _ = serialize("q", [blk("c1", "d.md", "para", "")])
    _, parsed = parse(wire)
    assert parsed[0].text == ""


# -- adversarial text: evidence that looks like the format itself ----------

def test_text_containing_at_line_does_not_break_parsing():
    """Real Markdown has lines starting with @ (decorators, handles)."""
    evil = "@decorator\nsome code"
    wire, _ = serialize("q", [blk("c1", "d.md", "code", evil)])
    _, parsed = parse(wire)
    assert parsed[0].text == evil
    assert len(parsed) == 1, "an @ line inside text must not open a new doc group"


def test_text_containing_block_header_shape_does_not_break_parsing():
    """A line like '0 list 2' inside evidence must not be read as a header."""
    evil = "0 list 2\nstill the same block"
    wire, _ = serialize("q", [blk("c1", "d.md", "para", evil)])
    _, parsed = parse(wire)
    assert len(parsed) == 1
    assert parsed[0].text == evil


def test_text_containing_q_line():
    evil = "Q not the query"
    wire, _ = serialize("real query", [blk("c1", "d.md", "para", evil)])
    q, parsed = parse(wire)
    assert q == "real query" and parsed[0].text == evil


# -- ordering: position bias + determinism ---------------------------------

def test_order_is_score_descending():
    ordered = order_blocks(CORPUS)
    assert [b.score for b in ordered] == sorted([b.score for b in CORPUS], reverse=True)


def test_ties_broken_by_content_id_deterministically():
    ordered = order_blocks(CORPUS)
    tied = [b.content_id for b in ordered if b.score == 0.7]
    assert tied == sorted(tied), "equal scores must order by content_id"


def test_order_is_stable_across_input_permutations():
    a, _ = serialize("q", CORPUS)
    b, _ = serialize("q", list(reversed(CORPUS)))
    assert a == b, "same set of blocks must serialise identically regardless of input order"


# -- prefix cacheability ---------------------------------------------------

def test_prefix_is_query_independent():
    p1 = render_prompt("query one", CORPUS).split("\n\nQ ")[0]
    p2 = render_prompt("totally different", [CORPUS[0]]).split("\n\nQ ")[0]
    assert p1 == p2 == PREFIX, "the cacheable prefix must not vary with the query"


def test_version_tag_present_in_prefix():
    assert VERSION in PREFIX, "an unknown version must be detectable for JSON fallback"


# -- host-side identifiers stay host-side ---------------------------------

def test_wire_contains_no_uuids_or_content_ids():
    wire, _ = serialize("gate", CORPUS)
    for b in CORPUS:
        assert b.occurrence_id not in wire, "occurrence_id must not reach the model"
        assert f" {b.content_id}" not in wire, "content_id must not reach the model"


def test_doc_name_emitted_once_per_group():
    wire, _ = serialize("gate", CORPUS)
    assert wire.count("@a/README.md") == 1, "doc name must be hoisted, not repeated"


def test_ids_are_small_integers_from_zero():
    _, id_map = serialize("gate", CORPUS)
    assert sorted(id_map) == list(range(len(CORPUS)))


# -- citation validation --------------------------------------------------

def test_valid_citations_resolve_to_blocks():
    _, id_map = serialize("gate", CORPUS)
    ok, bad = resolve_citations([0, 2], id_map)
    assert len(ok) == 2 and bad == []


def test_fabricated_citation_is_reported_not_ignored():
    _, id_map = serialize("gate", CORPUS)
    ok, bad = resolve_citations([0, 99], id_map)
    assert len(ok) == 1 and bad == [99]


def test_no_citations_is_not_an_error():
    _, id_map = serialize("gate", CORPUS)
    assert resolve_citations([], id_map) == ([], [])


# -- score quantisation ---------------------------------------------------

def test_quantize_is_integral_and_clamped():
    assert quantize_score(0.5) == 500
    assert quantize_score(-1.0) == 0
    assert quantize_score(2.0) == 1000
    assert isinstance(quantize_score(0.1234), int)


def test_quantize_nan_does_not_propagate():
    assert quantize_score(float("nan")) == 0


def test_quantize_is_stable_for_equal_inputs():
    assert quantize_score(0.1 + 0.2) == quantize_score(0.3)


# -- malformed input ------------------------------------------------------

def test_missing_query_line_rejected():
    try:
        parse("@d.md\n0 para 1\nx")
    except ValueError:
        return
    raise AssertionError("payload without a Q line must be rejected")


def test_truncated_block_rejected():
    try:
        parse("Q q\n@d.md\n0 para 5\nonly one line")
    except ValueError:
        return
    raise AssertionError("a block declaring more lines than present must be rejected")


def test_multiline_query_rejected():
    try:
        serialize("first line\nsecond line", CORPUS)
    except ValueError:
        return
    raise AssertionError("WC/1 query line must not be ambiguous")


def test_multiline_doc_path_rejected():
    try:
        serialize("q", [blk("c1", "doc.md\n@other.md", "para", "text")])
    except ValueError:
        return
    raise AssertionError("WC/1 document path must be a single line")


def test_whitespace_in_kind_rejected():
    try:
        serialize("q", [blk("c1", "doc.md", "code block", "text")])
    except ValueError:
        return
    raise AssertionError("WC/1 kind must be one token")


def test_duplicate_block_id_rejected():
    try:
        parse("Q q\n@d.md\n0 para 1\none\n0 para 1\ntwo")
    except ValueError:
        return
    raise AssertionError("duplicate model-visible ids must be rejected")


def test_negative_line_count_rejected():
    try:
        parse("Q q\n@d.md\n0 para -1")
    except ValueError:
        return
    raise AssertionError("negative line counts must be rejected")


def test_block_without_doc_rejected():
    try:
        parse("Q q\n0 para 1\ntext")
    except ValueError:
        return
    raise AssertionError("every block must resolve to a source document")


# -- the payoff: token saving vs the JSON fallback ------------------------

def test_token_saving_at_least_30_percent():
    """Acceptance criterion 2. Skipped when tiktoken is unavailable."""
    try:
        import tiktoken
    except ImportError:
        return
    enc = tiktoken.get_encoding("o200k_base")
    big = [
        blk(f"c{i:03d}", f"doc{i % 4}.md", "para",
            f"Evidence paragraph {i} about the evidence gate and its calibration.",
            score=1.0 - i / 100)
        for i in range(20)
    ]
    wire = render_prompt("gate calibration", big)
    js = as_json_payload("gate calibration", big)
    cut = 1 - len(enc.encode(wire)) / len(enc.encode(js))
    assert cut >= 0.30, f"expected >=30% token cut, got {cut*100:.1f}%"


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
