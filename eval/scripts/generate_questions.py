"""Template-based question generation -- Vol. 06 Construction Process step 2
('Template-based + LLM-assisted (local model) for diversity'). This script
implements the template half only; the LLM-assisted-diversity half needs a
local model wired in before this produces the full benchmark (see
eval/README.md). Every generated question is written with `needs_review:
true` and MUST go through eval/annotation/PROTOCOL.md's expert review step
(Vol. 06 Construction Process step 3) before being treated as ground truth
-- this script does not annotate evidence spans, only proposes questions.
"""
from __future__ import annotations

import json
from pathlib import Path

TEMPLATES = {
    "function": [
        "What does the function `{name}` do?",
        "Which module defines the function `{name}`?",
    ],
    "class": [
        "What does the class `{name}` implement?",
        "Which module defines the class `{name}`?",
    ],
}


def generate(units_path: Path) -> list[dict]:
    questions = []
    for line in units_path.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if rec["record"] != "SemanticUnit" or not rec.get("name"):
            continue
        for template in TEMPLATES.get(rec["type"], []):
            questions.append(
                {
                    "query_id": f"gen-{rec['content_id'][:12]}-{len(questions)}",
                    "question": template.format(name=rec["name"]),
                    "target_content_id": rec["content_id"],
                    "target_name": rec["name"],
                    "target_type": rec["type"],
                    "needs_review": True,
                    "ground_truth_evidence": [],  # filled in during annotation, not here
                }
            )
    return questions


def main():
    units_path = Path(__file__).parent.parent / "datasets" / "codeqa_python" / "units.jsonl"
    out_path = Path(__file__).parent.parent / "datasets" / "codeqa_python" / "questions_generated.jsonl"

    questions = generate(units_path)
    with out_path.open("w", encoding="utf-8") as f:
        for q in questions:
            f.write(json.dumps(q) + "\n")

    print(f"Generated {len(questions)} candidate questions -> {out_path}")
    print("All have needs_review=true; run eval/annotation/PROTOCOL.md before use as ground truth.")


if __name__ == "__main__":
    main()
