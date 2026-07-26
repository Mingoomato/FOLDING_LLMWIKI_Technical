"""Minimal real parser for the CodeQA-Python slice of LLMWikiBench.

Uses Python's stdlib `ast` module (no third-party deps, no Tree-sitter --
this is a benchmark-harness stand-in, not the production parser specified
in Vol. 02) to extract function/class definitions as SemanticUnit +
UnitOccurrence pairs, following the corrected data model in Appendix B
sec:app:data-model:identity: content_id is a hash of normalized source
text only; occurrence_id additionally depends on file path + span, so two
functions with identical bodies in different files get the same content_id
but different occurrence_ids -- exercised directly in test_parse_units.py.
"""
from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonicalize(source: str) -> str:
    """Whitespace-normalized canonical form used to derive content_id.
    Matches Vol. 02 def:semantic-unit's 'content: canonical text
    representation (whitespace-normalized)'.
    """
    lines = [line.rstrip() for line in source.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


@dataclass(frozen=True)
class SemanticUnit:
    content_id: str
    type: str
    content: str
    name: str = ""


@dataclass(frozen=True)
class UnitOccurrence:
    occurrence_id: str
    content_id: str
    file_path: str
    span: tuple[int, int]      # (start_line, end_line), matches span_type=line_column in Appendix B
    span_type: str
    ordinal: int


def parse_file(path: Path, ordinal_start: int = 0) -> tuple[list[SemanticUnit], list[UnitOccurrence]]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    lines = source.splitlines()

    units: dict[str, SemanticUnit] = {}
    occurrences: list[UnitOccurrence] = []
    ordinal = ordinal_start

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            start = node.lineno
            end = getattr(node, "end_lineno", start)
            raw = "\n".join(lines[start - 1 : end])
            canonical = canonicalize(raw)
            content_id = _sha256(canonical)
            unit_type = "class" if isinstance(node, ast.ClassDef) else "function"

            units[content_id] = SemanticUnit(content_id=content_id, type=unit_type, content=canonical, name=node.name)

            occurrence_id = _sha256(f"{path.name}|{start}|{end}")
            occurrences.append(
                UnitOccurrence(
                    occurrence_id=occurrence_id,
                    content_id=content_id,
                    file_path=str(path),
                    span=(start, end),
                    span_type="line_column",
                    ordinal=ordinal,
                )
            )
            ordinal += 1

    return list(units.values()), occurrences


def parse_corpus(raw_dir: Path) -> tuple[list[SemanticUnit], list[UnitOccurrence]]:
    all_units: dict[str, SemanticUnit] = {}
    all_occurrences: list[UnitOccurrence] = []
    ordinal = 0
    for path in sorted(raw_dir.glob("*.py")):
        units, occurrences = parse_file(path, ordinal_start=ordinal)
        for u in units:
            all_units[u.content_id] = u  # dedup by content_id, as designed
        all_occurrences.extend(occurrences)
        ordinal += len(occurrences)
    return list(all_units.values()), all_occurrences


def main():
    raw_dir = Path(__file__).parent.parent / "datasets" / "codeqa_python" / "raw"
    out_path = Path(__file__).parent.parent / "datasets" / "codeqa_python" / "units.jsonl"

    units, occurrences = parse_corpus(raw_dir)

    with out_path.open("w", encoding="utf-8") as f:
        for u in units:
            f.write(json.dumps({"record": "SemanticUnit", **asdict(u)}) + "\n")
        for o in occurrences:
            f.write(json.dumps({"record": "UnitOccurrence", **asdict(o)}) + "\n")

    print(f"Parsed {len(units)} SemanticUnits, {len(occurrences)} UnitOccurrences from {raw_dir}")
    print(f"Wrote {out_path}")

    # Sanity signal for the content_id/occurrence_id split: any content_id
    # with more than one occurrence proves dedup is doing something real,
    # not just theoretically possible.
    from collections import Counter

    counts = Counter(o.content_id for o in occurrences)
    dupes = {cid: n for cid, n in counts.items() if n > 1}
    if dupes:
        print(f"{len(dupes)} content_id(s) have multiple occurrences (dedup exercised)")
    else:
        print("No repeated content_id in this corpus slice (expected at this small scale)")


if __name__ == "__main__":
    main()
