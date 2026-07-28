# LLMWiki Architecture Overview

This document provides a high-level architectural map. For detailed specifications, see `docs/Volume_XX/`.

## Specification and Executable Surface

This repository is primarily a technical specification, not the production
LLMWiki binary. The executable surface under `eval/scripts/` is a local,
dependency-light reference implementation used to make selected claims
falsifiable.

| Surface | Status | Executable evidence |
|---|---|---|
| Semantic parsing, BM25 retrieval, core metrics | Runnable scaffold | `parse_units.py`, `retrieval_baseline.py`, `metrics.py`, `run_eval.py` |
| Time-scoped evidence gate | Runnable reference | `temporal_gate.py`, 19 tests |
| Budgeted evidence selection | Experimental reference | `evidence_packer.py`, 25 tests; not enabled in `run_eval.py` pending model A/B |
| WC/1 evidence transport | Runnable reference | `wire_contract.py`, 30 tests; production runtime integration pending |
| Discord-native knowledge source | Runnable reference | `integrations/discord_llmwiki/`, 19 tests; live guild and live OpenAI calls not exercised in CI |
| Full graph/index/runtime stack | Specification | Volumes 01-12; production Rust binary not present in this repository |

The source graph contains two code communities: the evaluation scripts and the
vendored CPython corpus used as test data. The three context-shaping modules are
deliberately standalone reference components rather than hidden dependencies of
the BM25 scaffold. Their integration boundary is therefore explicit.

---

## Three-Layer Decomposition

```
┌─────────────────────────────────────────────────────────────┐
│                    QUERY LAYER                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │    DAG      │  │   Agent     │  │ Gate → Packer → WC/1│  │
│  │  Planner    │──▶│  Runtime    │──▶│ Evidence Context    │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
└─────────┼───────────────┼─────────────────────┼─────────────┘
          │               │                     │
          ▼               ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│                      CORE LAYER                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │ Knowledge│ │  Hybrid  │ │  Entity  │ │  Budget /    │   │
│  │  Graph   │ │  Index   │ │Resolution│ │  State Mgmt  │   │
│  │ (RocksDB)│ │(HNSW+BM25+│ │          │ │              │   │
│  └────┬─────┘ │  Adj)    │ └────┬─────┘ └───────┬──────┘   │
└───────┼───────┴────┬───────┘      │             │          │
        │            │              │             │          │
        ▼            ▼              ▼             ▼          │
┌─────────────────────────────────────────────────────────────┐
│                    INGESTION LAYER                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │ Semantic │ │  Chunker │ │ Embedder │ │  Graph       │   │
│  │ Parser   │ │ (AST-    │ │ (ONNX    │ │  Mutator     │   │
│  │(Tree-sit)│ │  aware)  │ │  RT)     │ │              │   │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬───────┘   │
└───────┼────────────┼───────────┼──────────────┼────────────│
        │            │           │              │
        ▼            ▼           ▼              ▼
┌─────────────────────────────────────────────────────────────┐
│                  FILESYSTEM (WAL)                            │
│  .llmwiki/                                                   │
│  ├── wal/          # Append-only JSONL diffs                 │
│  ├── units/        # Content-addressed unit blobs            │
│  ├── graph/        # RocksDB column families                 │
│  ├── index/        # HNSW + Tantivy indices                  │
│  ├── planner/      # Plan cache                              │
│  └── evidence/     # Gate calibration data                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Flow Invariants

1. **Ingestion → Core**: Semantic units → Graph mutator + Index writer (atomic per file)
2. **Core → Query**: Planner reads Graph + Index stats → DAG → Runtime executes
3. **Evidence → Context**: Time scope → gate → budget selection → WC/1 serialization
4. **Citation Round Trip**: Model-visible integer ID → host map → exact occurrence and source span
5. **Query → Core**: Evidence Gate writes calibration data; Runtime updates budgets
6. **WAL Replay**: In any state, re-applying `wal/*.jsonl` produces bitwise-identical Core state

## Evidence Context Pipeline

```text
Hybrid candidates
    │
    ▼
As-of scope ── no valid evidence ───────────────▶ REFUSE(as_of=t)
    │
    ▼
Evidence gate ── no candidate clears threshold ▶ REFUSE
    │
    ▼
Budgeted selector
  - production default: score-ordered top-k
  - experimental: deterministic concept coverage
    │
    ▼
WC/1 serializer
  - verbatim evidence text
  - small integer citation handles
  - source path hoisted once per group
  - line-count framing for unambiguous parsing
    │
    ▼
LLM synthesis ── cited IDs ──▶ host-side resolver ──▶ occurrence/span
    │
    ▼
Claim support + evidence coverage verification
```

The order is load-bearing. Packing never runs before the evidence gate and
cannot turn a refusal into an answer. WC/1 compresses only the metadata
envelope; evidence text remains byte-identical so a human can audit citations.
Unknown contract versions fall back to JSON at the host integration boundary.

The WC/1 reference implementation measures a 30.3% English and 32.8% Korean
cold-prompt reduction against its JSON fallback, including the fixed contract
prefix. Prefix caching raises these figures to 31.7% and 36.6%. These are
transport measurements, not evidence that model answer quality is unchanged.
The required acceptance experiment is a four-cell comparison:
`(JSON, WC/1) × (top-k, packed)` across the `quality_at_budget` curve.

---

## Module Interface Contracts

### Ingestion
- **Input**: File path + bytes
- **Output**: Diff (added/modified/removed unit IDs) → WAL append
- **Guarantee**: Idempotent re-ingestion = no-op (content-addressed)

### Discord Source Adapter
- **Input**: REST history pages and Gateway message/thread dispatches
- **Durable truth**: Append-only SQLite event journal; edits and deletes are new events
- **Projection**: Channel/thread Markdown, JSONL audit copy, and stable `discord:<channel>:<message>` citations
- **Summary**: Prior memory + events after the successful summary checkpoint; provider is replaceable
- **Guarantee**: Duplicate delivery is a no-op; Markdown and current message state are replayable
- **Security**: Channel allowlist, least-privilege Discord permissions, untrusted-content prompt boundary, environment-only secrets

### Semantic Parser
- **Input**: Language + source bytes
- **Output**: Tree of SemanticUnit (typed, hierarchical, content-addressed)
- **Interface**: `Parser.parse(lang: str, bytes: &[u8]) -> Result<Vec<Unit>>`

### Graph Mutator
- **Input**: Unit diff + extracted entities/relations
- **Output**: RocksDB batch (nodes, edges, properties, indices)
- **Guarantee**: ACID per file; cross-file entity resolution async

### Hybrid Index
- **Vector**: HNSW (hnswlib) — cosine, dim=1024, M=16, efC=200
- **Keyword**: Tantivy BM25 — code analyzer
- **Graph**: Adjacency lists in RocksDB CF — prefix scan expansion
- **Fusion**: RRF(k=60, weights: vec=0.6, kw=0.3, graph=0.1)

### Evidence Gate
- **Input**: Query + candidate unit IDs (from hybrid index)
- **Process**: Cross-encoder batch → isotonic calibration → threshold τ
- **Output**: Verified evidence set (may be empty)
- **Guarantee**: `∀u∈verified: P(relevant|u) ≥ τ`

### Evidence Context Builder
- **Input**: Verified evidence set + context token budget
- **Selection**: Deterministic top-k baseline; optional concept-coverage packer
- **Transport**: WC/1 line-oriented envelope with verbatim evidence text
- **Host state**: `small_id → (content_id, occurrence_id, doc, span)`
- **Fallback**: JSON for unknown contract versions or failed capability negotiation
- **Guarantee**: Packing never exceeds budget; serialization round-trips evidence text

### Query Planner
- **Input**: Natural language query + context budget
- **Process**: LLM planner → DAG of subqueries (vector/graph/keyword/tool)
- **Optimization**: Cost model (index stats) → strategy per subquery
- **Output**: Executable QueryPlan DAG

### Agent Runtime
- **Input**: QueryPlan DAG
- **Execution**: Topological order, parallel fan-out, SSE streaming
- **State**: Scratchpad (intermediate results), Evidence set, Budget counters
- **Tools**: `search`, `graph_traverse`, `llm_complete`, `read_unit`

---

## Storage Layout

### Content-Addressed Units (`.llmwiki/units/`)
```
units/
├── ab/
│   └── ab12cd34... (first 2 hex = shard prefix)
│       ├── meta.json    # {id, type, language, parent_id, spans}
│       └── content.bin  # Canonical bytes
```

### Knowledge Graph (`.llmwiki/graph/`)
RocksDB Column Families:
- `nodes`: `unit_id -> NodeProto` (type, props, labels)
- `out_edges`: `unit_id + edge_type + target_id -> EdgeProto`
- `in_edges`: `target_id + edge_type + unit_id -> EdgeProto` (for reverse traversal)
- `entities`: `entity_id -> EntityProto` (canonical name, type, props)
- `entity_mentions`: `unit_id -> [entity_id]` (for resolution)
- `labels`: `label -> [unit_id prefix]` (for label scans)

### Hybrid Index (`.llmwiki/index/`)
- `hnsw/`: `hnswlib` index files (mmap'd)
- `tantivy/`: Tantivy directory (segments, meta)
- `adjacency/`: Same as graph `out_edges`/`in_edges` CFs

### WAL (`.llmwiki/wal/`)
```
wal/
├── 2024-01-15-000001.jsonl   # Rotated daily or per 100MB
├── 2024-01-15-000002.jsonl
└── CURRENT -> 2024-01-15-000002.jsonl
```
Each line: `{"op": "add|mod|del", "unit_id": "...", "file": "...", "timestamp": "...", "hash": "..."}`

---

## Deployment Topologies

### Local Development
- Single binary (`llmwiki`)
- Embedded models + grammars
- `.llmwiki/` in project root or `$HOME/.llmwiki/`

### Air-Gapped Server
- Same binary
- Models pre-baked or loaded from local model store
- No network calls ever

### Container/Kubernetes
- Distroless image (~150MB)
- PVC for `.llmwiki/`
- Optional: sidecar for model updates

### Discord Team Memory
- Python sidecar or companion process under `integrations/discord_llmwiki/`
- Local `.llmwiki-discord/discord-events.sqlite3` remains authoritative
- Discord Gateway is optional; REST backfill and deterministic projection run independently
- OpenAI Responses API is optional and used only for derived summaries; local search and exports remain available offline

### Distributed (Future)
- CRDT-based WAL merge
- Shared-nothing graph shards
- Central planner coordinator

---
## Key Design Decisions (Cross-Reference)

| Decision | ARCHITECTURE.md Section | DESIGN_DECISIONS.md |
|----------|------------------------|-------------------|
| Graph canonical | Data Flow | DD-001 |
| Filesystem WAL | Storage | DD-002 |
| Evidence Gate | Query Layer | DD-003 |
| SHA-256 units | Storage | DD-004 |
| Local-first | Deployment | DD-005 |
| DAG Planner | Query Layer | DD-006 |
| Tree-sitter | Ingestion | DD-007 |
| ONNX Runtime | Ingestion/Query | DD-008 |
| RocksDB | Storage | DD-009 |
| HNSW+Tantivy+Adj | Core Layer | DD-010 |
| Cross-encoder cal | Query Layer | DD-011 |
| SSE Streaming | Query Layer | DD-012 |
| Single Binary | Deployment | DD-013 |
| Budget Enforcer | Query Layer | DD-014 |
| CI Regression | Eval (Vol 6) | DD-015 |
| Evidence Context Transport | Evidence Context Pipeline | DD-023 |
| Budgeted Evidence Selection | Evidence Context Pipeline | DD-023 |
| Discord as Replayable Knowledge Source | Ingestion / Deployment | DD-024 |

---
*For detailed specifications, see `docs/Volume_01_Architecture/` through `docs/Volume_12_Mutation_Engine/`.*
