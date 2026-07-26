++ # LLMWiki Architecture Overview
++ 
++ This document provides a high-level architectural map. For detailed specifications, see `docs/Volume_XX/`.
++ 
++ ---
++ 
++ ## Three-Layer Decomposition
++ 
++ ```
++ ┌─────────────────────────────────────────────────────────────┐
++ │                    QUERY LAYER                               │
++ │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
++ │  │    DAG      │  │   Agent     │  │    Evidence Gate    │  │
++ │  │  Planner    │──▶│  Runtime    │──▶│  (Cross-Encoder)    │  │
++ │  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
++ └─────────┼───────────────┼─────────────────────┼─────────────┘
++           │               │                     │
++           ▼               ▼                     ▼
++ ┌─────────────────────────────────────────────────────────────┐
++ │                      CORE LAYER                              │
++ │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
++ │  │ Knowledge│ │  Hybrid  │ │  Entity  │ │  Budget /    │   │
++ │  │  Graph   │ │  Index   │ │Resolution│ │  State Mgmt  │   │
++ │  │ (RocksDB)│ │(HNSW+BM25+│ │          │ │              │   │
++ │  └────┬─────┘ │  Adj)    │ └────┬─────┘ └───────┬──────┘   │
++ └───────┼───────┴────┬───────┘      │             │          │
++         │            │              │             │          │
++         ▼            ▼              ▼             ▼          │
++ ┌─────────────────────────────────────────────────────────────┐
++ │                    INGESTION LAYER                           │
++ │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
++ │  │ Semantic │ │  Chunker │ │ Embedder │ │  Graph       │   │
++ │  │ Parser   │ │ (AST-    │ │ (ONNX    │ │  Mutator     │   │
++ │  │(Tree-sit)│ │  aware)  │ │  RT)     │ │              │   │
++ │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬───────┘   │
++ └───────┼────────────┼───────────┼──────────────┼────────────│
++         │            │           │              │
++         ▼            ▼           ▼              ▼
++ ┌─────────────────────────────────────────────────────────────┐
++ │                  FILESYSTEM (WAL)                            │
++ │  .llmwiki/                                                   │
++ │  ├── wal/          # Append-only JSONL diffs                 │
++ │  ├── units/        # Content-addressed unit blobs            │
++ │  ├── graph/        # RocksDB column families                 │
++ │  ├── index/        # HNSW + Tantivy indices                  │
++ │  ├── planner/      # Plan cache                              │
++ │  └── evidence/     # Gate calibration data                   │
++ └─────────────────────────────────────────────────────────────┘
++ ```
++ 
++ ---
++ 
++ ## Data Flow Invariants
++ 
++ 1. **Ingestion → Core**: Semantic units → Graph mutator + Index writer (atomic per file)
++ 2. **Core → Query**: Planner reads Graph + Index stats → DAG → Runtime executes
++ 3. **Query → Core**: Evidence Gate writes calibration data; Runtime updates budgets
++ 4. **WAL Replay**: In any state, re-applying `wal/*.jsonl` produces bitwise-identical Core state
++ 
++ ---
++ 
++ ## Module Interface Contracts
++ 
++ ### Ingestion
++ - **Input**: File path + bytes
++ - **Output**: Diff (added/modified/removed unit IDs) → WAL append
++ - **Guarantee**: Idempotent re-ingestion = no-op (content-addressed)
++ 
++ ### Semantic Parser
++ - **Input**: Language + source bytes
++ - **Output**: Tree of SemanticUnit (typed, hierarchical, content-addressed)
++ - **Interface**: `Parser.parse(lang: str, bytes: &[u8]) -> Result<Vec<Unit>>`
++ 
++ ### Graph Mutator
++ - **Input**: Unit diff + extracted entities/relations
++ - **Output**: RocksDB batch (nodes, edges, properties, indices)
++ - **Guarantee**: ACID per file; cross-file entity resolution async
++ 
++ ### Hybrid Index
++ - **Vector**: HNSW (hnswlib) — cosine, dim=1024, M=16, efC=200
++ - **Keyword**: Tantivy BM25 — code analyzer
++ - **Graph**: Adjacency lists in RocksDB CF — prefix scan expansion
++ - **Fusion**: RRF(k=60, weights: vec=0.6, kw=0.3, graph=0.1)
++ 
++ ### Evidence Gate
++ - **Input**: Query + candidate unit IDs (from hybrid index)
++ - **Process**: Cross-encoder batch → isotonic calibration → threshold τ
++ - **Output**: Verified evidence set (may be empty)
++ - **Guarantee**: `∀u∈verified: P(relevant|u) ≥ τ`
++ 
++ ### Query Planner
++ - **Input**: Natural language query + context budget
++ - **Process**: LLM planner → DAG of subqueries (vector/graph/keyword/tool)
++ - **Optimization**: Cost model (index stats) → strategy per subquery
++ - **Output**: Executable QueryPlan DAG
++ 
++ ### Agent Runtime
++ - **Input**: QueryPlan DAG
++ - **Execution**: Topological order, parallel fan-out, SSE streaming
++ - **State**: Scratchpad (intermediate results), Evidence set, Budget counters
++ - **Tools**: `search`, `graph_traverse`, `llm_complete`, `read_unit`
++ 
++ ---
++ 
++ ## Storage Layout
++ 
++ ### Content-Addressed Units (`.llmwiki/units/`)
++ ```
++ units/
++ ├── ab/
++ │   └── ab12cd34... (first 2 hex = shard prefix)
++ │       ├── meta.json    # {id, type, language, parent_id, spans}
++ │       └── content.bin  # Canonical bytes
++ ```
++ 
++ ### Knowledge Graph (`.llmwiki/graph/`)
++ RocksDB Column Families:
++ - `nodes`: `unit_id -> NodeProto` (type, props, labels)
++ - `out_edges`: `unit_id + edge_type + target_id -> EdgeProto`
++ - `in_edges`: `target_id + edge_type + unit_id -> EdgeProto` (for reverse traversal)
++ - `entities`: `entity_id -> EntityProto` (canonical name, type, props)
++ - `entity_mentions`: `unit_id -> [entity_id]` (for resolution)
++ - `labels`: `label -> [unit_id prefix]` (for label scans)
++ 
++ ### Hybrid Index (`.llmwiki/index/`)
++ - `hnsw/`: `hnswlib` index files (mmap'd)
++ - `tantivy/`: Tantivy directory (segments, meta)
++ - `adjacency/`: Same as graph `out_edges`/`in_edges` CFs
++ 
++ ### WAL (`.llmwiki/wal/`)
++ ```
++ wal/
++ ├── 2024-01-15-000001.jsonl   # Rotated daily or per 100MB
++ ├── 2024-01-15-000002.jsonl
++ └── CURRENT -> 2024-01-15-000002.jsonl
++ ```
++ Each line: `{"op": "add|mod|del", "unit_id": "...", "file": "...", "timestamp": "...", "hash": "..."}`
++ 
++ ---
++ 
++ ## Deployment Topologies
++ 
++ ### Local Development
++ - Single binary (`llmwiki`)
++ - Embedded models + grammars
++ - `.llmwiki/` in project root or `$HOME/.llmwiki/`
++ 
++ ### Air-Gapped Server
++ - Same binary
++ - Models pre-baked or loaded from local model store
++ - No network calls ever
++ 
++ ### Container/Kubernetes
++ - Distroless image (~150MB)
++ - PVC for `.llmwiki/`
++ - Optional: sidecar for model updates
++ 
++ ### Distributed (Future)
++ - CRDT-based WAL merge
++ - Shared-nothing graph shards
++ - Central planner coordinator
++ 
++ ---
++ ## Key Design Decisions (Cross-Reference)
++ 
++ | Decision | ARCHITECTURE.md Section | DESIGN_DECISIONS.md |
++ |----------|------------------------|-------------------|
++ | Graph canonical | Data Flow | DD-001 |
++ | Filesystem WAL | Storage | DD-002 |
++ | Evidence Gate | Query Layer | DD-003 |
++ | SHA-256 units | Storage | DD-004 |
++ | Local-first | Deployment | DD-005 |
++ | DAG Planner | Query Layer | DD-006 |
++ | Tree-sitter | Ingestion | DD-007 |
++ | ONNX Runtime | Ingestion/Query | DD-008 |
++ | RocksDB | Storage | DD-009 |
++ | HNSW+Tantivy+Adj | Core Layer | DD-010 |
++ | Cross-encoder cal | Query Layer | DD-011 |
++ | SSE Streaming | Query Layer | DD-012 |
++ | Single Binary | Deployment | DD-013 |
++ | Budget Enforcer | Query Layer | DD-014 |
++ | CI Regression | Eval (Vol 6) | DD-015 |
++ 
++ ---
++ *For detailed specifications, see `docs/Volume_01_Architecture/` through `docs/Volume_11_Research_Paper/`.*
