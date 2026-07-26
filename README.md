# LLMWiki

**A Semantic Operating Layer for Local Knowledge**

---

LLMWiki is not a Retrieval-Augmented Generation framework. It is a **semantic operating layer** that continuously transforms heterogeneous digital artifacts into an evidence-aware knowledge space.

## Quick Links

- [Developer Handoff Note](HANDOFF_NOTE.md) — What changed in the latest build, verified build state, rebuild instructions
- [Project Vision](PROJECT_VISION.md) — Mission, goals, non-goals, success metrics
- [System Philosophy](SYSTEM_PHILOSOPHY.md) — 8 foundational architectural principles
- [Architecture Overview](ARCHITECTURE.md) — Three-layer decomposition, data flow, module contracts
- [Roadmap](ROADMAP.md) — Milestones, timeline, resource estimates
- [Design Decisions](DESIGN_DECISIONS.md) — 15 recorded decisions with rationale
- [Technical Specification](docs/) — 11 Volumes + Appendices (LaTeX source)
- [Contributing](CONTRIBUTING.md) — Development setup, standards, workflow
- [Changelog](CHANGELOG.md) — Release history

## What Makes LLMWiki Different

| Aspect | Traditional RAG | LLMWiki |
|--------|-----------------|---------|
| **Primary Store** | Vector DB | Property Graph (RocksDB) |
| **Retrieval** | ANN only | Hybrid: HNSW + BM25 + Graph Adjacency |
| **Verification** | Reranker (optional) | Mandatory Evidence Gate (cross-encoder + calibration) |
| **Deployment** | Cloud API | Local binary / Air-gapped / Container |
| **Updates** | Re-embed all | Incremental (Tree-sitter diff) |
| **Attribution** | Post-hoc | Built-in (content-addressed units) |
| **Lineage** | None | Full (WAL replay) |

## Core Invariants

1. **Event Log is Durable Truth** — Graph/vector/keyword indices are rebuildable projections of the append-only log, not independent sources of truth
2. **Graph is the Canonical Query-Time Representation** — among the projections, the property graph is what the planner queries first
3. **SHA-256 is Content Identity, Not Location Identity** — content identity and occurrence (file+span) identity are separate; see Appendix B
4. **Evidence Gate is Mandatory (Four Stages)** — Relevance, Structural/Source-Validity, Claim Support, and Evidence Coverage; empty set = "insufficient evidence"
5. **Local-First, LLM-Optional** — Critical path has zero external calls
6. **DAG Planner** — Parallel, explainable, budgeted
7. **Incremental Consistency** — Per-projection, per-sequence: once a projection's last_applied_sequence reaches n, it matches log replay 1..n
8. **Deterministic Replay** — Same input → same output; crash recovery via a sequence-numbered, idempotent projection scanner
9. **Mutation Requires Approval** — No write to a source artifact bypasses the approval pipeline (Volume 12) and produces a rollback record

## Documentation

The complete technical specification is organized as 12 volumes:

| Volume | Title | Focus |
|--------|-------|-------|
| 01 | Architecture | Three-layer design, invariants, module contracts, crash consistency |
| 02 | Semantic Parsing | Tree-sitter, SCM, chunking, embedding, extraction |
| 03 | Knowledge Graph | Property graph, RocksDB, entity resolution, hybrid index |
| 04 | Retrieval | Hybrid search, four-stage Evidence Gate, synthesis with citations |
| 05 | Agent Runtime | DAG planner, executor, SSE streaming, budget enforcement |
| 06 | Evaluation | Benchmarks, metrics (Evidence F1, Attribution), CI gates |
| 07 | Deployment | Local, container, K8s, air-gapped, monitoring |
| 08 | API Reference | REST/gRPC/WS, auth, rate limits, SDKs |
| 09 | Developer Guide | Extension points (parsers, chunkers, embedders, tools, auth) |
| 10 | Patent | Draft claims (unfiled; pending counsel review and prior-art search) |
| 11 | Research Paper | Architecture and evaluation protocol; benchmark results are preliminary targets pending public release of LLMWikiBench |
| 12 | Mutation and Approval Engine | Document write-back, format-aware patching, human approval, rollback, resync |

Appendices: Mathematical Notation, Data Models (content identity vs. occurrence identity), Config Schema, Grammar Specs, Evaluation Protocol, Related Work, Design Decisions

## Building the PDF

```bash
cd LLMWiki
make pdf
```

Requires: TeX Live / MacTeX with `latexmk`, `lualatex` (via `fontspec`), `bibtex`

> **Windows/MiKTeX note**: if `bibtex` reports "I couldn't open database file" despite `bibliography/LLMWiki.bib` existing, set `BIBINPUTS` to a Windows-style path before building: `export BIBINPUTS="<repo-root-absolute-path>;"`. This is a `kpsewhich` path-resolution quirk, not a missing file.

## License

Apache License 2.0 (see [LICENSE](LICENSE))

---

*LLMWiki: Transforming heterogeneous digital artifacts into an evidence-aware knowledge space.*
