"""Evaluation harness -- implements the pipeline in Vol. 06
sec:eval:pipeline (Dataset -> Ingest -> Retrieve+Gate -> Generate Answer ->
Compute Metrics -> Report) against the toy CodeQA-Python corpus and the
5-question illustrative gold sample.

Answer generation is intentionally NOT implemented here: it would require
an actual LLM call, which local_only: true (eval_config.yaml) rules out
for this scaffold. Retrieval, gating, and the retrieval-side metrics
(EvRecall@k, EvPrecision@k, Evidence F1@k, GateRejectionRate) run for
real; Attribution Score is demonstrated separately in metrics.py's tests
since it needs an answer to score.

Usage: python run_eval.py
Output: eval/results/<timestamp>/report.json (+ human-readable report.md)
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from metrics import QueryResult, evidence_recall_at_k, evidence_precision_at_k, evidence_f1_at_k, gate_rejection_rate, bootstrap_ci
from parse_units import parse_corpus
from retrieval_baseline import Bm25Index

DATASET_DIR = Path(__file__).parent.parent / "datasets" / "codeqa_python"
RESULTS_DIR = Path(__file__).parent.parent / "results"


def load_gold(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def run(k_values: tuple[int, ...] = (5, 10, 20), gate_threshold: float = 0.0) -> dict:
    units, occurrences = parse_corpus(DATASET_DIR / "raw")
    unit_by_content = {u.content_id: u for u in units}

    # Index at occurrence granularity: what a query actually retrieves is a
    # located instance of content, not a bare content blob, matching the
    # UnitOccurrence-is-the-citable-thing design in Appendix B sec:app:data-model:identity.
    documents = {o.occurrence_id: unit_by_content[o.content_id].content for o in occurrences}
    index = Bm25Index.build(documents)

    gold = load_gold(DATASET_DIR / "gold_sample.jsonl")

    results_by_k: dict[int, list[QueryResult]] = {k: [] for k in k_values}
    per_query_detail = []

    for item in gold:
        ranked = index.rank(item["question"])
        candidate_ids = tuple(doc_id for doc_id, _ in ranked)
        # "Gate": keep candidates with score >= gate_threshold. At
        # threshold 0.0 this is a no-op (BM25 already filters zero-score
        # docs in Bm25Index.rank); raise gate_threshold to see rejection
        # rate move, matching eval_config.yaml's gate_threshold sweep.
        verified = tuple(doc_id for doc_id, score in ranked if score >= gate_threshold)

        gt = frozenset(item["ground_truth_evidence"])
        for k in k_values:
            results_by_k[k].append(
                QueryResult(
                    query_id=item["query_id"],
                    ground_truth_evidence=gt,
                    retrieved_candidates=candidate_ids,
                    gate_verified=verified,
                )
            )
        per_query_detail.append(
            {
                "query_id": item["query_id"],
                "question": item["question"],
                "top_5_retrieved": candidate_ids[:5],
                "ground_truth": list(gt),
                "hit_at_5": bool(gt & set(candidate_ids[:5])),
            }
        )

    report: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "corpus": {
            "raw_files": sorted(p.name for p in (DATASET_DIR / "raw").glob("*.py")),
            "n_semantic_units": len(units),
            "n_occurrences": len(occurrences),
        },
        "gold_set": {
            "path": str(DATASET_DIR / "gold_sample.jsonl"),
            "n_questions": len(gold),
            "status": "single-reviewer illustrative sample -- NOT a validated benchmark; see PROTOCOL.md",
        },
        "retrieval_backend": "BM25 (local, no external calls) -- see retrieval_baseline.py docstring for scope",
        "gate_threshold": gate_threshold,
        "metrics": {},
        "per_query_detail": per_query_detail,
    }

    for k in k_values:
        rec_vals = [evidence_recall_at_k([r], k) for r in results_by_k[k]]
        report["metrics"][f"k={k}"] = {
            "evidence_recall_at_k": evidence_recall_at_k(results_by_k[k], k),
            "evidence_recall_at_k_bootstrap_ci": bootstrap_ci(rec_vals),
            "evidence_precision_at_k": evidence_precision_at_k(results_by_k[k], k),
            "evidence_f1_at_k": evidence_f1_at_k(results_by_k[k], k),
        }
    report["metrics"]["gate_rejection_rate"] = gate_rejection_rate(results_by_k[k_values[0]])

    return report


def write_report(report: dict) -> Path:
    run_dir = RESULTS_DIR / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# LLMWikiBench harness run (illustrative scaffold, not a benchmark result)",
        "",
        f"Generated: {report['generated_at']}",
        f"Corpus: {report['corpus']['n_semantic_units']} SemanticUnits, "
        f"{report['corpus']['n_occurrences']} UnitOccurrences from {report['corpus']['raw_files']}",
        f"Gold set: {report['gold_set']['n_questions']} questions -- {report['gold_set']['status']}",
        f"Retrieval backend: {report['retrieval_backend']}",
        "",
        "## Metrics",
        "",
        "| k | EvRecall@k | EvPrecision@k | Evidence F1@k |",
        "|---|-----------|---------------|---------------|",
    ]
    for k_label, m in report["metrics"].items():
        if not k_label.startswith("k="):
            continue
        lines.append(
            f"| {k_label[2:]} | {m['evidence_recall_at_k']:.3f} | "
            f"{m['evidence_precision_at_k']:.3f} | {m['evidence_f1_at_k']:.3f} |"
        )
    lines.append(f"\nGate rejection rate: {report['metrics']['gate_rejection_rate']:.3f}")
    lines.append("\n## Per-query detail\n")
    for d in report["per_query_detail"]:
        status = "HIT" if d["hit_at_5"] else "MISS"
        lines.append(f"- [{status}] `{d['query_id']}`: {d['question']}")

    (run_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return run_dir


def main():
    report = run()
    run_dir = write_report(report)
    print(f"Wrote {run_dir / 'report.json'} and report.md")
    print()
    print((run_dir / "report.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
