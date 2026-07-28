# LLMWikiBench: harness scaffold

This directory is a **real, runnable scaffold** for the evaluation
framework specified in Vol. 06 (Evaluation Framework) -- not the full
LLMWikiBench benchmark Vol. 06 Table `eval:internal` describes (6 internal
benchmarks, up to 1M units, human-annotated at scale). Read this file
before citing anything under `eval/` as a result; the distinction between
"the harness works" and "we have benchmark numbers" is the exact thing
Vol. 11 §11.3 ("Status of empirical claims") exists to keep separate, and
this README exists so `eval/` doesn't quietly become the place that
distinction gets lost.

## What's real here

- `scripts/parse_units.py` -- a working parser (stdlib `ast`, no deps)
  that extracts `SemanticUnit`/`UnitOccurrence` records from Python source,
  implementing the corrected content_id/occurrence_id split from
  Appendix B §A.1. Run against the toy corpus in `datasets/codeqa_python/raw/`
  (two real CPython stdlib files), it genuinely finds repeated content at
  different locations (4 duplicate `content_id`s in the current corpus --
  shared helper methods across `queue.py`'s `Queue`/`LifoQueue`/
  `PriorityQueue` subclasses) and gives them one `content_id` each with
  distinct `occurrence_id`s, which is the property the schema exists to
  provide.
- `scripts/metrics.py` -- implements the Vol. 06 evidence-quality metrics and
  the context-efficiency axis (tokens per answered query, coverage per token,
  budget utilisation, quality-at-budget, refusal token cost), with 17 passing
  unit tests (`scripts/test_metrics.py`).
- `scripts/retrieval_baseline.py` -- a real BM25 implementation (no
  third-party deps) used as the harness's local-only retrieval backend.
- `scripts/run_eval.py` -- runs the full pipeline (parse -> index -> query
  -> gate -> metrics -> report) end-to-end against the toy corpus and
  writes a timestamped report to `results/`. This actually executes; it is
  not a mock.
- `scripts/temporal_gate.py` -- executable as-of filtering, three-way
  Answer/Refuse/Review decisions, and temporal-leakage accounting (19 tests).
- `scripts/evidence_packer.py` -- deterministic budgeted concept-coverage
  selection (25 tests). It is an experimental reference component and does not
  replace top-k in `run_eval.py` until the documented model A/B succeeds.
- `scripts/wire_contract.py` -- the WC/1 evidence envelope, deterministic
  ordering, host-side citation resolution, parser validation, and JSON fallback
  payload generation (30 tests). It is not yet wired into a production runtime.
- `annotation/PROTOCOL.md` -- the annotation protocol Vol. 06's
  Construction Process steps 3-5 reference, specified in enough detail to
  actually run (acceptance criteria, evidence-span annotation rules,
  kappa gate, merge process).
- `datasets/codeqa_python/gold_sample.jsonl` -- 5 hand-verified
  question/evidence pairs, annotated by a single reviewer (this session)
  against the real corpus content, explicitly to exercise the schema and
  `run_eval.py` -- not a validated gold set (PROTOCOL.md requires two
  independent annotators + kappa > 0.8 for that status).

## What a sample run actually produces

```
$ cd eval/scripts && python run_eval.py
Corpus: 49 SemanticUnits, 54 UnitOccurrences from ['heapq.py', 'queue.py']
Gold set: 5 questions -- single-reviewer illustrative sample

| k  | EvRecall@k | EvPrecision@k | Evidence F1@k |
|----|-----------|---------------|---------------|
| 5  | 0.600     | 0.120         | 0.200         |
| 10 | 1.000     | 0.100         | 0.182         |
| 20 | 1.000     | 0.050         | 0.095         |
```

These numbers are real (computed, not invented) but describe BM25 lexical
retrieval over 2 files and 5 questions -- they say nothing about LLMWiki's
actual hybrid search, evidence gate, or any of the Vol. 11 performance
targets, and must not be cited as if they did. Their only purpose is to
prove the harness computes what it claims to compute.

## What's NOT here, and what closing each gap requires

| Gap | What full-scale requires |
|-----|---------------------------|
| Corpus scale (2 files vs. Vol. 06's 50 repos / 200K units per benchmark) | Curate and license-check real repositories (Apache, Kubernetes, etc. per Vol. 06 §6.2.1); `parse_units.py`'s approach generalizes but Vol. 02's actual Tree-sitter-based parser should replace the `ast`-only stand-in for non-Python languages and for parity with the production ingestion path. |
| Gold set scale (5 questions, 1 reviewer vs. thousands, 2 reviewers + kappa gate) | Recruit and pay two independent annotators per PROTOCOL.md; this is people and budget, not code. |
| Attribution Score, Answer Correctness | Need a real generated answer, which needs a real LLM call -- out of scope for `local_only: true`. Wire in a local model (per Vol. 06's Local-First Evaluation principle) and replace `metrics.lexical_overlap_nli_stub` with a real NLI model before trusting attribution numbers; the stub is explicitly documented as unsound for anything beyond exercising the code path. |
| Hybrid retrieval (vector + BM25 + graph) | Needs an actual embedding model and a running graph store (Vol. 03); `retrieval_baseline.py` is BM25-only, i.e. exactly one row of `eval_config.yaml`'s `hybrid_weights` sweep. |
| Full configuration matrix sweep | Needs the above plus compute budget to actually run every (k, weights, threshold, embedder, model) combination in `configs/eval_config.yaml`. |
| External benchmarks (NQ, HotpotQA, MS MARCO, BEIR, CodeSearchNet, Spider/BIRD) | Not started; Vol. 06 §6.2.2 lists them but no adapter code exists yet. |
| CI regression gate (Vol. 06 §6.6) | The `.github/workflows/eval.yml` snippet in Vol. 06 is illustrative; wiring it to this harness needs a `llmwiki eval run`/`check` CLI that doesn't exist (the harness here is invoked as a Python script, not a subcommand of a built `llmwiki` binary, because that binary doesn't exist yet either -- see DD-021). |

## Running it yourself

```bash
cd eval/scripts
python parse_units.py          # regenerate units.jsonl from raw/
python generate_questions.py   # regenerate questions_generated.jsonl (candidates, not gold)
python test_metrics.py         # verify metrics implementations (17 tests)
python test_temporal_gate.py   # verify as-of gate semantics (19 tests)
python test_evidence_packer.py # verify budgeted selection (25 tests)
python test_wire_contract.py   # verify WC/1 transport contract (30 tests)
python run_eval.py             # full pipeline, writes results/<timestamp>/
```

No network access is required to run any of these once `raw/` is
populated (network was used once, to fetch the two seed files -- see
`datasets/codeqa_python/raw/SOURCE.md`). No API keys, no external
services, consistent with Vol. 06's Local-First Evaluation principle.
