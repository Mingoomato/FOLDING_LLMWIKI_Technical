# LLMWiki Design Decisions Log

This document records all significant architectural and design decisions for the LLMWiki project.
Each entry follows the format: Decision ID, Decision, Alternatives Considered, Rationale, Status.

---

## Decision Index

| ID | Title | Status |
|----|-------|--------|
| DD-001 | Graph as Canonical Query Representation (Vectors as Projections) | ✅ Accepted (revised 2026-07-27) |
| DD-002 | Filesystem-Backed Event Log as Sole Durability Layer | ✅ Accepted (revised 2026-07-27) |
| DD-003 | Mandatory Evidence Gate (Not Reranker) | ✅ Accepted |
| DD-004 | Content-Addressed Units (SHA-256) | ✅ Accepted |
| DD-005 | Local-First, LLM-Optional Critical Path | ✅ Accepted |
| DD-006 | DAG Query Planner with Cost Model | ✅ Accepted |
| DD-007 | Tree-sitter for Code Parsing | ✅ Accepted |
| DD-008 | ONNX Runtime for Embeddings | ✅ Accepted |
| DD-009 | RocksDB for Graph Storage | ✅ Accepted |
| DD-010 | HNSW + Tantivy + Custom Adjacency Index | ✅ Accepted |
| DD-011 | Cross-Encoder with Isotonic Calibration | ✅ Accepted |
| DD-012 | SSE Streaming Protocol | ✅ Accepted |
| DD-013 | Single-Binary Deployment | ✅ Accepted |
| DD-014 | Budget Enforcement at Executor | ✅ Accepted |
| DD-015 | Regression Gates in CI | ✅ Accepted |
| DD-021 | Rust Core with PyO3 Bindings (over Python/FastAPI Core) | ✅ Accepted |
| DD-022 | Deployment Tier Separation: Local MVP / Team Server / Enterprise Cluster | ✅ Accepted |

---

## DD-001: Graph as Canonical Query Representation (Vectors as Projections)

**Date**: 2024-01-15
**Revised**: 2026-07-27 — see note below
**Status**: ✅ Accepted (revised)

### Decision
The property knowledge graph is the canonical representation for query-time reasoning: the planner and evidence gate query it first, and vector/keyword indices exist to accelerate or widen that graph-centric retrieval. This is a statement about which representation query execution treats as primary, not a durability claim — durability is DD-002's job (the graph, like the vector and keyword indices, is a rebuildable projection of the event log, not itself a source of truth). The original 2024-01-15 wording of this decision ("canonical knowledge representation," full stop) was ambiguous between these two meanings and was read as a claim that the graph was also the durability layer, which directly conflicted with DD-002. This revision states the graph's role precisely; see Vol. 01 §architecture:philosophy for the full architectural argument.

### Alternatives Considered
1. **Vector-first (e.g., FAISS/Milvus as primary)**: Simpler for semantic search, but loses structural relationships, multi-hop reasoning, and explainability.
2. **Document store (e.g., Elasticsearch)**: Good for keyword search, but no native graph traversal or entity resolution.
3. **Relational DB (PostgreSQL + pgvector)**: Mature, but graph queries require recursive CTEs; poor performance for deep traversals.

### Rationale
- Enables structural queries (CONTAINS, CALLS, INHERITS, REFERENCES) that vectors cannot express
- Supports multi-hop reasoning and graph algorithms (PageRank, community detection)
- Deterministic updates: graph mutations are explicit, not implicit via re-embedding
- Vectors remain useful as one of several retrieval signals (hybrid search)
- Aligns with Semantic OS vision: knowledge as connected structure, not bag of embeddings

### Consequences
- Requires dedicated graph storage (RocksDB) and query engine
- Vector indices must be rebuilt from graph on schema changes
- More complex than pure vector RAG

---

## DD-002: Filesystem-Backed Event Log as Sole Durability Layer

**Date**: 2024-01-15
**Revised**: 2026-07-27 — see note below
**Status**: ✅ Accepted (revised)

### Decision
The append-only event log in `.llmwiki/wal/` is the sole durability mechanism and the system's one source of truth for history (alongside the user's original source artifacts, which are authoritative for content). Graph, vector, and keyword projections carry no durability obligation of their own: they are rebuildable from the log and a `_projection.meta` marker (`last_applied_sequence`) makes rebuilding idempotent and resumable after a crash. No auxiliary transaction log service (Kafka, Redis Streams, etc.) is required.

### Alternatives Considered
1. **Kafka/Redis Streams**: Battle-tested, but adds operational complexity; overkill for single-node local-first.
2. **SQLite WAL mode**: Good, but still a database dependency; filesystem is more transparent.
3. **Custom binary log**: Reinventing the wheel; JSONL on POSIX is human-readable and tool-friendly.

### Rationale
- **Zero operational dependencies**: Works on any POSIX filesystem; no broker to run
- **Content-addressed deduplication**: Identical units produce identical WAL entries
- **`rsync`/`git` replay of `wal/` segments**: safe because segments are immutable once published; replay = re-apply JSONL in order. This does **not** extend to live-copying `graph/`/`index/` — RocksDB/HNSW/Tantivy each need a consistent checkpoint, not a directory copy (Vol. 01 §architecture:crash-consistency).
- **Atomic commit, not bare `rename()`**: temp file + fsync + rename/`MoveFileEx` + directory fsync, specified separately for POSIX and Windows (Vol. 01 §architecture:crash-consistency) — the original 2024-01-15 wording ("POSIX `rename()` atomicity") assumed a POSIX-only deployment target, which doesn't hold for this project's Windows-inclusive local-first target.
- **Auditability**: Human-readable JSONL; `jq`/`grep` for debugging

### Consequences
- Not horizontally scalable (single-writer assumed); clustering would need a log service
- Large WAL files need rotation/compaction strategy, bounded by periodic checkpoints (`checkpoints/`)
- Read-after-write on graph/index projections lags event commit by however long `ApplyGraph`/`ApplyIndex` take; this is ordinary event-sourcing lag, not a correctness gap, and is made explicit rather than hidden (Vol. 01 Algorithm ingestion)

---

## DD-003: Mandatory Evidence Gate (Not Reranker)

**Date**: 2024-01-15
**Status**: ✅ Accepted

### Decision
Retrieval results must pass a mandatory cross-encoder verification stage before synthesis. This is an **evidence filter**, not a reranker: it may reject *all* candidates (empty evidence set), triggering "insufficient evidence" response.

### Alternatives Considered
1. **Reranker only (Cohere Rerank, BGE-Reranker)**: Reorders but always returns top-k; no explicit quality gate.
2. **LLM-as-judge**: Flexible but slow, non-deterministic, expensive; unsuitable for critical path.
3. **Heuristic filters (BM25 score, length, recency)**: Fast but brittle; no semantic understanding.

### Rationale
- **Evidence Closure Invariant**: Every citation must be verified (`∀c∈citations: verify(c) ≥ τ`)
- **Calibrated probabilities**: Isotonic regression maps cross-encoder scores → true P(relevant)
- **FDR control**: Threshold `τ` chosen to bound False Discovery Rate (e.g., 5%)
- **Empty set = honest "I don't know"**: Better than hallucinated answer from weak evidence
- **Conformal prediction**: Can provide prediction sets with coverage guarantees

### Consequences
- Adds latency (~50-200ms per query for cross-encoder)
- Requires calibration dataset for each domain
- May reduce recall if threshold too aggressive

---

## DD-004: Content-Addressed Units (SHA-256)

**Date**: 2024-01-15
**Status**: ✅ Accepted

### Decision
Every semantic unit is identified by SHA-256 of its canonical representation: `id(u) = SHA256(canonical(u))`.

### Alternatives Considered
1. **UUIDv4**: Simple, but no deduplication; same content → different IDs.
2. **UUIDv5 (namespace + name)**: Better, but requires stable naming; canonical form still needed.
3. **Merkle tree roots**: Overkill for single units; useful for collections.

### Rationale
- **Automatic deduplication**: Identical content → identical ID across all indices
- **Verifiable lineage**: Can prove unit X came from file Y at commit Z
- **Cache keys**: Embedding cache, cross-encoder cache keyed by SHA-256
- **Deterministic replay**: Re-ingesting produces bitwise-identical IDs
- **Tamper evidence**: Any modification changes the ID

### Consequences
- Canonicalization must be deterministic (whitespace, encoding, ordering)
- SHA-256 is slower than XXHash; acceptable for ingestion throughput

---

## DD-005: Local-First, LLM-Optional Critical Path

**Date**: 2024-01-15
**Status**: ✅ Accepted

### Decision
All critical-path operations (ingestion, indexing, retrieval, verification, planning) execute on local hardware with zero external API dependencies. LLMs are optional accelerators for planning, entity extraction, and synthesis.

### Alternatives Considered
1. **Cloud-first (OpenAI API, Pinecone, etc.)**: Lower local compute, but latency, cost, privacy, and availability concerns.
2. **Hybrid (local index, cloud LLM)**: Common pattern, but still depends on external API for synthesis.

### Rationale
- **Air-gapped deployment**: Works in secure environments with no internet
- **Data sovereignty**: Source code, docs never leave the machine
- **Predictable latency**: No network variance, rate limits, or cold starts
- **Zero marginal cost**: No per-token or per-query charges
- **Offline development**: Full functionality on airplane/train

### Consequences
- Requires local GPU/CPU for embeddings (ONNX Runtime) and optional LLMs (llama.cpp/Ollama)
- Model quality bounded by local hardware (mitigated by quantization, distillation)
- Synthesis quality lower than GPT-4-class models; mitigated by evidence gate

---

## DD-006: DAG Query Planner with Cost Model

**Date**: 2024-01-20
**Status**: ✅ Accepted

### Decision
Query planner compiles natural language into a DAG of executable subqueries (retrieval, graph traversal, tool calls, synthesis), optimized via a cost model over index statistics.

### Alternatives Considered
1. **Linear chain (ReAct, Chain-of-Thought)**: Simple but no parallel fan-out; rigid.
2. **Fixed templates**: Fast but inflexible; can't adapt to query complexity.
3. **LLM-only planning**: Flexible but unpredictable; hard to enforce budgets.

### Rationale
- **Parallel fan-out**: Independent subqueries execute concurrently (e.g., vector + keyword + graph)
- **Subquery decomposition**: Complex questions → multiple focused retrievals → synthesis
- **Strategy selection**: Planner chooses vector/graph/keyword per subquery based on cost model
- **Explainability**: DAG is inspectable; each step has estimated cost
- **Budget enforcement**: Cost model drives token/time/call limits at executor

### Consequences
- Requires accurate index statistics (cardinality, selectivity)
- Cost model needs training/calibration

---

## DD-007: Tree-sitter for Code Parsing

**Date**: 2024-01-20
**Status**: ✅ Accepted

### Decision
Use Tree-sitter for all code parsing (40+ languages), leveraging its incremental parsing and SCM query language for semantic unit extraction.

### Alternatives Considered
1. **Regex/heuristic chunking**: Fast but semantically blind; breaks on nested structures.
2. **Language-specific parsers (ASTroid, javalang, etc.)**: Fragmented APIs; maintenance burden.
3. **LLM-based parsing**: Flexible but slow, non-deterministic, expensive.

### Rationale
- **Incremental re-parsing**: O(log n) edits; only changed regions re-parsed
- **Unified query language**: SCM patterns work across all languages
- **Error recovery**: Produces valid CST even for malformed code
- **Battle-tested**: Used by GitHub, VS Code, Neovim
- **No runtime dependencies**: C library + Rust bindings; single binary

### Consequences
- SCM query writing required per language (maintenance)
- Tree-sitter grammars may lag behind latest language versions

---

## DD-008: ONNX Runtime for Embeddings

**Date**: 2024-01-20
**Status**: ✅ Accepted

### Decision
Embedders and cross-encoders run via ONNX Runtime for hardware-agnostic inference.

### Alternatives Considered
1. **PyTorch/TensorFlow**: Full frameworks; heavy dependencies; slow cold start.
2. **llama.cpp (GGUF)**: Great for LLMs; not optimized for BERT-style encoders.
3. **Custom C++ inference**: Maximum control; massive engineering effort.

### Rationale
- **Hardware-agnostic**: CPU, CUDA, CoreML, DirectML, OpenVINO via execution providers
- **Quantization support**: INT8, INT4, FP16 via ONNX Runtime quantization tools
- **No Python runtime**: Embed in Rust/Go/C++ binary; fast cold start (~50ms)
- **Model zoo**: BGE, E5, Nomic, Jina all export to ONNX
- **Standard format**: Portable across training/inference stacks

### Consequences
- Model export step required (PyTorch → ONNX)
- Some advanced ops (FlashAttention) may need custom ops

---

## DD-009: RocksDB for Graph Storage

**Date**: 2024-01-25
**Status**: ✅ Accepted

### Decision
Use embedded RocksDB with column families for graph storage (nodes, edges, properties, indices).

### Alternatives Considered
1. **Neo4j (embedded)**: License (AGPL/Commercial); heavy; JVM dependency.
2. **Kuzu / Redwood**: Promising but younger; less battle-tested.
3. **SQLite + recursive CTEs**: Simple but slow for deep traversals; no native graph indices.
4. **Custom B+tree on files**: Reinventing LSM trees; RocksDB is mature.

### Rationale
- **Embedded**: No separate process; single binary deployment
- **Column families**: Separate CFs for nodes, out-edges, in-edges, labels, properties
- **Prefix scans**: Adjacency lists via prefix iteration; efficient graph expansion
- **WAL + compaction**: Durability + space reclamation built-in
- **Proven at scale**: Used by Facebook, LinkedIn, TiKV, CockroachDB
- **Rust bindings**: `rocksdb` crate is well-maintained

### Consequences
- Write amplification from compaction; tune `max_write_buffer_number`
- Memory usage from block cache; configure `block_cache_size`

---

## DD-010: HNSW + Tantivy + Custom Adjacency Index

**Date**: 2024-01-25
**Status**: ✅ Accepted

### Decision
Hybrid semantic index combining: HNSW (vector ANN), Tantivy (BM25 keyword), and custom graph adjacency index—fused via Reciprocal Rank Fusion (RRF).

### Alternatives Considered
1. **Single vector index (FAISS/HNSW only)**: Misses exact keyword matches; poor for symbols/API names.
2. **Elasticsearch/OpenSearch**: Full-text + vector, but heavy; separate service.
3. **pgvector + pg_trgm**: Good integration, but PostgreSQL dependency; slower ANN.

### Rationale
- **HNSW**: State-of-the-art ANN; `hnswlib`/`faiss` are fast and mature
- **Tantivy**: Rust-native BM25; no JVM; used by Meilisearch, Quickwit
- **Graph adjacency**: Sub-millisecond neighbor expansion; enables GraphRAG patterns
- **RRF fusion**: Parameter-free rank aggregation; robust to score scale differences
- **All embedded**: Single process; no network hops between indices

### Consequences
- Three indices to maintain on ingestion; write amplification
- RRF weights need tuning per corpus (configurable)

---

## DD-011: Cross-Encoder with Isotonic Calibration

**Date**: 2024-01-25
**Status**: ✅ Accepted

### Decision
Evidence Gate uses a cross-encoder (e.g., `cross-encoder/ms-marco-MiniLM-L-6-v2`) with isotonic regression calibration for threshold selection.

### Alternatives Considered
1. **Bi-encoder dot product**: Fast but less accurate; no joint query-doc attention.
2. **Platt scaling (logistic)**: Parametric; assumes sigmoid shape; less flexible.
3. **Temperature scaling**: Single parameter; insufficient for complex score distributions.
4. **No calibration**: Raw scores not probabilities; threshold selection arbitrary.

### Rationale
- **Cross-encoder accuracy**: Joint encoding captures fine-grained relevance
- **Isotonic regression**: Non-parametric; fits any monotonic calibration curve
- **FDR control**: Calibrated scores enable threshold selection via Benjamini-Hochberg
- **Conformal prediction**: Can construct prediction sets with coverage guarantees

### Consequences
- Calibration dataset needed per domain (active learning can reduce labeling)
- Isotonic regression can overfit on small calibration sets; use CV

---

## DD-012: SSE Streaming Protocol

**Date**: 2024-01-30
**Status**: ✅ Accepted

### Decision
Agent runtime streams fine-grained events via Server-Sent Events (SSE): `plan_start`, `step_start`, `evidence_found`, `token`, `step_complete`, `plan_complete`, `budget_warning`.

### Alternatives Considered
1. **WebSocket**: Bidirectional but more complex; overkill for server→client streaming.
2. **Long polling / HTTP chunked**: Works but no standard event framing; harder to parse.
3. **JSON lines over HTTP**: Similar to SSE but no browser native support.

### Rationale
- **Browser native**: `EventSource` API; automatic reconnection
- **Simple framing**: `event: type\ndata: {}\n\n`; easy to parse in any language
- **HTTP/2 multiplexing**: Works over h2; no connection overhead
- **Firewall friendly**: Standard HTTP; no WebSocket upgrade issues
- **Bidirectional via separate WS**: SSE for streaming, WS for control if needed

### Consequences
- Unidirectional; client → server needs separate endpoint (REST/WS)
- Connection limits per browser (6 per host on HTTP/1.1); use HTTP/2

---

## DD-013: Single-Binary Deployment

**Date**: 2024-01-30
**Status**: ✅ Accepted

### Decision
Distribute as a single self-contained binary with embedded models, grammars, and configuration templates.

### Alternatives Considered
1. **Docker image**: Standard but requires Docker daemon; heavier; layer caching issues.
2. **Package managers (apt, brew, winget)**: Good for updates; but fragmentation across OS.
3. **Python/Rust crate**: Requires runtime; dependency hell; not air-gap friendly.

### Rationale
- **Air-gapped viable**: Copy binary + models directory; no registry pulls
- **Simple upgrades**: Replace binary; no migration scripts
- **Reproducible**: Same binary on dev, CI, prod
- **No container runtime**: Runs on bare metal, VMs, constrained environments
- **Cross-platform**: Rust `cargo build --release --target=x86_64-pc-windows-gnu` etc.

### Consequences
- Binary size larger (~100-200MB with embedded models)
- Models baked in or loaded from alongside; version sync needed

---

## DD-014: Budget Enforcement at Executor

**Date**: 2024-02-01
**Status**: ✅ Accepted

### Decision
Agent runtime executor enforces hard budgets (tokens, wall-clock time, tool calls, monetary cost) with configurable overflow behavior: `truncate | partial | error`.

### Alternatives Considered
1. **Soft limits (warnings only)**: No guarantee; runaway queries still possible.
2. **LLM-based budget awareness**: Unreliable; model may ignore/forget.
3. **No budgets**: Simpler but dangerous for production/automated use.

### Rationale
- **Predictable costs**: Hard ceiling on token/API spend
- **Latency SLA**: Wall-clock timeout prevents hung queries
- **Graceful degradation**: `truncate` returns partial answer + evidence; `partial` returns what completed
- **Observability**: Budget events in SSE stream (`budget_warning`, `budget_exceeded`)

### Consequences
- May cut off mid-synthesis; answer quality varies with budget
- Budget accounting must be accurate (token counting, wall-clock)

---

## DD-015: Regression Gates in CI

**Date**: 2024-02-01
**Status**: ✅ Accepted

### Decision
CI pipeline fails if any primary metric (Evidence F1, Attribution, Hallucination Rate) degrades >2% absolute vs. `main` branch baseline.

### Alternatives Considered
1. **No gates**: Regressions caught manually (or not at all).
2. **Alerting only (no block)**: Noise fatigue; regressions merge.
3. **Relative thresholds (e.g., 5%)**: Scale-dependent; absolute is clearer.

### Rationale
- **Quality ratchet**: Prevents silent degradation; "green means good"
- **2% absolute**: Meaningful but not noisy; calibrated on benchmark variance
- **Primary metrics only**: Evidence F1 (retrieval+verification), Attribution (citation quality), Hallucination (safety)
- **Bootstrap CI**: 1000 resamples for confidence intervals; Wilcoxon for significance

### Consequences
- Benchmark suite must be fast (<10 min) and deterministic
- Baseline stored in repo (or artifact); updated on intentional improvements
- Flaky benchmarks block merges; invest in stability

---

## DD-021: Rust Core with PyO3 Bindings (over Python/FastAPI Core)

**Date**: 2026-07-27
**Status**: ✅ Accepted

### Context
LLMWiki is greenfield as of this decision — there is no existing FastAPI/Python/Next.js implementation being replaced. This is a forward stack choice, not a migration, and is recorded here specifically because Vol. 09's Developer Guide commits to a Rust workspace (`crates/`) with PyO3 Python bindings and a React/Vite web UI, and that commitment deserves a recorded rationale rather than standing as an unexplained default.

### Alternatives Considered
1. **Python core (FastAPI + Python parsers/ML) with optional Rust hot paths**: Faster initial velocity, largest available contributor pool for an ML-heavy project, but the filesystem-watcher/parsing/indexing hot path (Vol. 01 §architecture:filesystem-wal, Vol. 02 parsing) is exactly the workload (many small files, tight loops, crash-consistency-sensitive atomic writes) where Python's GIL and per-call overhead show up first; would likely need a Rust or C extension for that path eventually anyway.
2. **Rust core, Python only for ML/eval (this decision)**: Core (WAL, graph, index, evidence gate, planner) in Rust for performance and memory safety on the crash-consistency-sensitive path (Vol. 01 §architecture:crash-consistency); PyO3 bindings expose the core to Python for evaluation scripting, notebook-driven experimentation, and any ML library that's Python-only. FFI boundary is narrow and one-directional: Python calls into Rust, not the reverse.
3. **Full Rust including ML (candle, burn, or ONNX Runtime bindings only)**: Avoids the FFI boundary entirely, but cuts off the Python ML ecosystem (most embedding/reranking model tooling, evaluation frameworks, and the research code most contributors will already know) — assessed as too narrow for a project whose evidence-gate research (Vol. 04, Vol. 11) leans on that ecosystem.

### Rationale
- **FFI boundary is narrow and explicit**: PyO3 bindings expose a small, versioned Python API surface (`python/llmwiki/`) over the Rust core; the core's internal crate boundaries (Vol. 09 §dev:structure) are not exposed to Python, so the FFI surface can be kept stable even as internals change.
- **Deployment impact**: the Rust core compiles to a single binary (Vol. 07 §deploy:modes, Embedded/Standalone/Air-gapped tiers) with no Python runtime required for those tiers; Python is only in the picture for `eval/` scripts and any deployment tier that explicitly opts into a Python-scriptable extension point (Vol. 09 §dev:env).
- **Since this is greenfield, there is no migration cost to amortize** — the usual ADR risk for this kind of decision (rewriting a working system) does not apply here. The risk that does apply is developer availability: Rust + PyO3 is a narrower hiring/contributor pool than pure Python, which is the main argument for the alternative and the main thing that would justify revisiting this decision.

### Consequences
- Core development requires Rust proficiency; Python-only contributors are limited to `python/`, `eval/`, and web UI work unless they cross-train.
- The FFI boundary (PyO3) is a real interface that must be versioned and tested like any other API, not treated as free.
- If contributor availability turns out to bottleneck on Rust specifically, the fallback is not "rewrite in Python" but "widen the set of extension points implementable in Python without touching the Rust core" (Vol. 09's stated extension points — parsers, chunkers, embedders, tools, auth providers — are designed as trait boundaries for exactly this reason).

---

## DD-022: Deployment Tier Separation — Local MVP / Team Server / Enterprise Cluster

**Date**: 2026-07-27
**Status**: ✅ Accepted

### Context
Vol. 07's deployment chapter specifies Kubernetes, Helm charts, and (via Vol. 09/acronyms) Vault, Consul, and Ceph/Longhorn-class storage as available deployment components. Presented undifferentiated, this reads as if a v1 local-first product requires cluster-operations complexity to run at all, which contradicts DD-005 (Local-First, LLM-Optional) and the single-binary deployment goal (DD-013). This decision makes explicit which components belong to which deployment tier so "LLMWiki supports Kubernetes" and "LLMWiki requires Kubernetes" are not conflated.

### Decision
Three deployment tiers, cumulative in complexity, each independently sufficient for its use case:

| Tier | Use case | Required components | Explicitly NOT required |
|------|----------|---------------------|--------------------------|
| **Local MVP** | Individual user, desktop app, CLI, air-gapped single machine | Single binary (Vol. 07 `llmwiki:cpu`/`llmwiki:full` image, or embedded library mode), local filesystem `.llmwiki/` | Docker, Kubernetes, Helm, Vault, Consul, Ceph/Longhorn, Redis, any network service |
| **Team Server** | Small team, shared server, single-writer repository | Standalone Server mode (Vol. 07 Table deploy:modes): API + workers, Docker container, optional shared read-replica index | Kubernetes, Helm, Vault, Consul, Ceph (a plain volume or NFS mount suffices at this scale per Vol. 07 §deploy — RWX shared PVC is an Enterprise Cluster concern, not a Team Server one) |
| **Enterprise Cluster** | High-availability production service, multi-writer, compliance requirements | Everything above, plus Kubernetes, Helm charts (Vol. 07 §deploy:helm), Vault/Consul for secrets and service discovery, Ceph/Longhorn-class RWX storage, load-balanced replicas | — (this is the tier the existing Vol. 07 content was written for) |

### Alternatives Considered
1. **Single undifferentiated deployment spec (status quo before this decision)**: Simplest to write, but conflates "supported at largest scale" with "required at every scale," which is the exact problem this decision fixes.
2. **Separate documents per tier**: Cleaner separation, but fragments the single-source-of-truth deployment chapter and risks the tiers drifting out of sync; rejected in favor of one chapter with explicit tier labeling on each component.

### Rationale
- **Local-First is the default, not an afterthought (DD-005)**: a new user's first experience with LLMWiki must not require reading the Kubernetes section.
- **Complexity should be opt-in and scale with actual need**: Team Server adds Docker; Enterprise Cluster adds cluster operations; neither is a prerequisite for the tier below it.
- **Testability**: each tier can be validated independently (Local MVP in CI without a cluster; Enterprise Cluster against a real or simulated K8s environment) rather than requiring full cluster infrastructure to validate a single-binary code path.

### Consequences
- Vol. 07 needs each component (Dockerfile, Helm chart, Vault/Consul integration, RWX storage) explicitly labeled with its minimum tier, not presented as uniform v1 scope.
- Documentation and onboarding must lead with Local MVP; Enterprise Cluster content moves later in the reading order.
- Feature parity across tiers is not assumed — e.g., multi-writer concurrency (Vol. 01 §architecture:filesystem-wal design tradeoff) is an Enterprise Cluster concern; Local MVP and Team Server assume single-writer.

---

## Future Decisions (Planned)

| ID | Title | Target |
|----|-------|--------|
| DD-016 | Incremental Graph Algorithms (PageRank, Communities) | v0.3 |
| DD-017 | Multi-Modal Units (Images, Diagrams) | v0.4 |
| DD-018 | Distributed Sync (CRDT/OpLog) | v1.0 |
| DD-019 | Query Plan Caching & Reuse | v0.3 |
| DD-020 | Active Learning for Evidence Gate Calibration | v0.3 |
