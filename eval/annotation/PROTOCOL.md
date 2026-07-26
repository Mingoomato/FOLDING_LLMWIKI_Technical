# LLMWikiBench Annotation Protocol

Implements Vol. 06 (Evaluation Framework) Construction Process steps 3-5:
expert review, evidence annotation, quality control. This is the actual
protocol document referenced by `sec:eval:internal`'s Construction Process
list -- that list named the steps; this file specifies how to execute them.

## Scope

One annotation task = one generated question
(`questions_generated.jsonl`, `needs_review: true`) reviewed by exactly two
independent annotators (per the inter-annotator-agreement requirement
below; a single annotator's judgment is not sufficient to promote a
question to the gold set).

## Step 1: Expert Review (question quality)

For each candidate question, the annotator marks one of:

- `ACCEPT` -- the question is answerable from the corpus, unambiguous, and
  the templated phrasing reads naturally.
- `REJECT` -- the question is ill-posed (e.g., the target unit is too
  trivial to have a meaningful "what does this do" answer -- a bare
  `pass`-only stub) or ambiguous (multiple units share the target name
  across files, and the question doesn't disambiguate which one).
- `REWRITE` -- the question is salvageable with edited phrasing; annotator
  supplies the rewritten text.

Only `ACCEPT` and `REWRITE` (with the rewrite applied) proceed to Step 2.

## Step 2: Evidence Span Annotation

For each accepted question, the annotator records the **complete** set of
`occurrence_id`s (from `units.jsonl`, `UnitOccurrence` records) that
support the answer -- not just the single `target_content_id` the
question was templated from. This matters concretely for this corpus: a
"what does `_put` do" question templated against one occurrence should
also list every other occurrence sharing the same `content_id` if the
question doesn't disambiguate a specific file/class, since Evidence
Recall@k (Vol. 06 def:evidence-recall) is computed against the *complete*
ground-truth evidence set, and an incomplete one silently deflates every
system's recall score in a way that has nothing to do with retrieval
quality.

Annotators work from `eval/datasets/codeqa_python/units.jsonl` and the raw
source in `eval/datasets/codeqa_python/raw/`, not from the question text
alone -- the question text is the system's input, not the annotator's.

## Step 3: Independent Second Pass + Inter-Annotator Agreement

A second annotator repeats Steps 1-2 independently (no access to the first
annotator's labels). Agreement is computed with `metrics.cohens_kappa()`
over the categorical `ACCEPT`/`REJECT`/`REWRITE` decision (evidence-span
agreement is checked separately as span-set Jaccard overlap, reported
alongside kappa but not substituted for it, since kappa is defined over
categorical labels).

**Acceptance gate**: kappa > 0.8 (Vol. 06 Construction Process step 5). If
kappa falls at or below 0.8 for a batch, the batch is not merged into
`gold.jsonl`; the protocol (this document) or the templates
(`generate_questions.py`) are revised, not the annotators' individual
judgments overridden by a tiebreaker -- persistent low agreement is a
signal the task itself is under-specified.

## Step 4: Merge to Gold Set

Where both annotators agree (post-kappa-gate), the question and the
*union* of both annotators' evidence spans is written to
`eval/datasets/codeqa_python/gold.jsonl` in the `QueryResult`-compatible
schema `run_eval.py` consumes:

```json
{
  "query_id": "gen-8deab73c8802-0",
  "question": "What does the function `heappush` do?",
  "ground_truth_evidence": ["<occurrence_id_1>", "<occurrence_id_2>"]
}
```

## What This Repository Contains vs. What Full-Scale Annotation Requires

`eval/datasets/codeqa_python/gold_sample.jsonl` in this repository is a
**5-question illustrative sample**, annotated by a single reviewer (not
the two-annotator process above) purely to demonstrate the schema and let
`run_eval.py` execute end-to-end. It is explicitly not a validated gold
set and must not be quoted as benchmark ground truth -- see
`eval/README.md`. Running this protocol for real, at the scale Vol. 06
Table `eval:internal` specifies (200K units for CodeQA-Python alone),
requires recruiting actual second annotators and is out of scope for what
this repository can self-certify.
