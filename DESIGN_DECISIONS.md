++ # LLMWiki Design Decisions Log
++ 
++ This document records all significant architectural and design decisions for the LLMWiki project.
++ Each entry follows the format: Decision ID, Decision, Alternatives Considered, Rationale, Status.
++ 
++ ---
++ 
++ ## Decision Index
++ 
++ | ID | Title | Status |
++ |----|-------|--------|
++ | DD-001 | Graph as Source of Truth (Vectors as Projections) | ✅ Accepted |
++ | DD-002 | Filesystem as Write-Ahead Log | ✅ Accepted |
++ | DD-003 | Mandatory Evidence Gate (Not Reranker) | ✅ Accepted |
++ | DD-004 | Content-Addressed Units (SHA-256) | ✅ Accepted |
++ | DD-005 | Local-First, LLM-Optional Critical Path | ✅ Accepted |
++ | DD-006 | DAG Query Planner with Cost Model | ✅ Accepted |
++ | DD-007 | Tree-sitter for Code Parsing | ✅ Accepted |
++ | DD-008 | ONNX Runtime for Embeddings | ✅ Accepted |
++ | DD-009 | RocksDB for Graph Storage | ✅ Accepted |
++ | DD-010 | HNSW + Tantivy + Custom Adjacency Index | ✅ Accepted |
++ | DD-011 | Cross-Encoder with Isotonic Calibration | ✅ Accepted |
++ | DD-012 | SSE Streaming Protocol | ✅ Accepted |
++ | DD-013 | Single-Binary Deployment | ✅ Accepted |
++ | DD-014 | Budget Enforcement at Executor | ✅ Accepted |
++ | DD-015 | Regression Gates in CI | ✅ Accepted |
++ 
++ ---
++ 
++ ## DD-001: Graph as Source of Truth (Vectors as Projections)
++ 
++ **Date**: 2024-01-15
++ **Status**: ✅ Accepted
++ 
++ ### Decision
++ The property knowledge graph is the canonical knowledge representation. Vector indices are derived projections optimized for similarity search—not the primary store.
++ 
++ ### Alternatives Considered
++ 1. **Vector-first (e.g., FAISS/Milvus as primary)**: Simpler for semantic search, but loses structural relationships, multi-hop reasoning, and explainability.
++ 2. **Document store (e.g., Elasticsearch)**: Good for keyword search, but no native graph traversal or entity resolution.
++ 3. **Relational DB (PostgreSQL + pgvector)**: Mature, but graph queries require recursive CTEs; poor performance for deep traversals.
++ 
++ ### Rationale
++ - Enables structural queries (CONTAINS, CALLS, INHERITS, REFERENCES) that vectors cannot express
++ - Supports multi-hop reasoning and graph algorithms (PageRank, community detection)
++ - Deterministic updates: graph mutations are explicit, not implicit via re-embedding
++ - Vectors remain useful as one of several retrieval signals (hybrid search)
++ - Aligns with Semantic OS vision: knowledge as connected structure, not bag of embeddings
++ 
++ ### Consequences
++ - Requires dedicated graph storage (RocksDB) and query engine
++ - Vector indices must be rebuilt from graph on schema changes
++ - More complex than pure vector RAG
++ 
++ ---
++ 
++ ## DD-002: Filesystem as Write-Ahead Log
++ 
++ **Date**: 2024-01-15
++ **Status**: ✅ Accepted
++ 
++ ### Decision
++ The local filesystem directory structure `.llmwiki/wal/` serves as the sole durability mechanism. No auxiliary transaction log service (Kafka, Redis Streams, etc.) is required.
++ 
++ ### Alternatives Considered
++ 1. **Kafka/Redis Streams**: Battle-tested, but adds operational complexity; overkill for single-node local-first.
++ 2. **SQLite WAL mode**: Good, but still a database dependency; filesystem is more transparent.
++ 3. **Custom binary log**: Reinventing the wheel; JSONL on POSIX is human-readable and tool-friendly.
++ 
++ ### Rationale
++ - **Zero operational dependencies**: Works on any POSIX filesystem; no broker to run
++ - **Content-addressed deduplication**: Identical units produce identical WAL entries
++ - **`rsync`/`git` replay**: Backup = directory copy; replay = re-apply JSONL in order
++ - **POSIX `rename()` atomicity**: Durable commits without fsync storms
++ - **Auditability**: Human-readable JSONL; `jq`/`grep` for debugging
++ 
++ ### Consequences
++ - Not horizontally scalable (single-writer assumed); clustering would need a log service
++ - Large WAL files need rotation/compaction strategy
++ 
++ ---
++ 
++ ## DD-003: Mandatory Evidence Gate (Not Reranker)
++ 
++ **Date**: 2024-01-15
++ **Status**: ✅ Accepted
++ 
++ ### Decision
++ Retrieval results must pass a mandatory cross-encoder verification stage before synthesis. This is an **evidence filter**, not a reranker: it may reject *all* candidates (empty evidence set), triggering "insufficient evidence" response.
++ 
++ ### Alternatives Considered
++ 1. **Reranker only (Cohere Rerank, BGE-Reranker)**: Reorders but always returns top-k; no explicit quality gate.
++ 2. **LLM-as-judge**: Flexible but slow, non-deterministic, expensive; unsuitable for critical path.
++ 3. **Heuristic filters (BM25 score, length, recency)**: Fast but brittle; no semantic understanding.
++ 
++ ### Rationale
++ - **Evidence Closure Invariant**: Every citation must be verified (`∀c∈citations: verify(c) ≥ τ`)
++ - **Calibrated probabilities**: Isotonic regression maps cross-encoder scores → true P(relevant)
++ - **FDR control**: Threshold `τ` chosen to bound False Discovery Rate (e.g., 5%)
++ - **Empty set = honest "I don't know"**: Better than hallucinated answer from weak evidence
++ - **Conformal prediction**: Can provide prediction sets with coverage guarantees
++ 
++ ### Consequences
++ - Adds latency (~50-200ms per query for cross-encoder)
++ - Requires calibration dataset for each domain
++ - May reduce recall if threshold too aggressive
++ 
++ ---
++ 
++ ## DD-004: Content-Addressed Units (SHA-256)
++ 
++ **Date**: 2024-01-15
++ **Status**: ✅ Accepted
++ 
++ ### Decision
++ Every semantic unit is identified by SHA-256 of its canonical representation: `id(u) = SHA256(canonical(u))`.
++ 
++ ### Alternatives Considered
++ 1. **UUIDv4**: Simple, but no deduplication; same content → different IDs.
++ 2. **UUIDv5 (namespace + name)**: Better, but requires stable naming; canonical form still needed.
++ 3. **Merkle tree roots**: Overkill for single units; useful for collections.
++ 
++ ### Rationale
++ - **Automatic deduplication**: Identical content → identical ID across all indices
++ - **Verifiable lineage**: Can prove unit X came from file Y at commit Z
++ - **Cache keys**: Embedding cache, cross-encoder cache keyed by SHA-256
++ - **Deterministic replay**: Re-ingesting produces bitwise-identical IDs
++ - **Tamper evidence**: Any modification changes the ID
++ 
++ ### Consequences
++ - Canonicalization must be deterministic (whitespace, encoding, ordering)
++ - SHA-256 is slower than XXHash; acceptable for ingestion throughput
++ 
++ ---
++ 
++ ## DD-005: Local-First, LLM-Optional Critical Path
++ 
++ **Date**: 2024-01-15
++ **Status**: ✅ Accepted
++ 
++ ### Decision
++ All critical-path operations (ingestion, indexing, retrieval, verification, planning) execute on local hardware with zero external API dependencies. LLMs are optional accelerators for planning, entity extraction, and synthesis.
++ 
++ ### Alternatives Considered
++ 1. **Cloud-first (OpenAI API, Pinecone, etc.)**: Lower local compute, but latency, cost, privacy, and availability concerns.
++ 2. **Hybrid (local index, cloud LLM)**: Common pattern, but still depends on external API for synthesis.
++ 
++ ### Rationale
++ - **Air-gapped deployment**: Works in secure environments with no internet
++ - **Data sovereignty**: Source code, docs never leave the machine
++ - **Predictable latency**: No network variance, rate limits, or cold starts
++ - **Zero marginal cost**: No per-token or per-query charges
++ - **Offline development**: Full functionality on airplane/train
++ 
++ ### Consequences
++ - Requires local GPU/CPU for embeddings (ONNX Runtime) and optional LLMs (llama.cpp/Ollama)
++ - Model quality bounded by local hardware (mitigated by quantization, distillation)
++ - Synthesis quality lower than GPT-4-class models; mitigated by evidence gate
++ 
++ ---
++ 
++ ## DD-006: DAG Query Planner with Cost Model
++ 
++ **Date**: 2024-01-20
++ **Status**: ✅ Accepted
++ 
++ ### Decision
++ Query planner compiles natural language into a DAG of executable subqueries (retrieval, graph traversal, tool calls, synthesis), optimized via a cost model over index statistics.
++ 
++ ### Alternatives Considered
++ 1. **Linear chain (ReAct, Chain-of-Thought)**: Simple but no parallel fan-out; rigid.
++ 2. **Fixed templates**: Fast but inflexible; can't adapt to query complexity.
++ 3. **LLM-only planning**: Flexible but unpredictable; hard to enforce budgets.
++ 
++ ### Rationale
++ - **Parallel fan-out**: Independent subqueries execute concurrently (e.g., vector + keyword + graph)
++ - **Subquery decomposition**: Complex questions → multiple focused retrievals → synthesis
++ - **Strategy selection**: Planner chooses vector/graph/keyword per subquery based on cost model
++ - **Explainability**: DAG is inspectable; each step has estimated cost
++ - **Budget enforcement**: Cost model drives token/time/call limits at executor
++ 
++ ### Consequences
++ - Requires accurate index statistics (cardinality, selectivity)
++ - Cost model needs training/calibration
++ 
++ ---
++ 
++ ## DD-007: Tree-sitter for Code Parsing
++ 
++ **Date**: 2024-01-20
++ **Status**: ✅ Accepted
++ 
++ ### Decision
++ Use Tree-sitter for all code parsing (40+ languages), leveraging its incremental parsing and SCM query language for semantic unit extraction.
++ 
++ ### Alternatives Considered
++ 1. **Regex/heuristic chunking**: Fast but semantically blind; breaks on nested structures.
++ 2. **Language-specific parsers (ASTroid, javalang, etc.)**: Fragmented APIs; maintenance burden.
++ 3. **LLM-based parsing**: Flexible but slow, non-deterministic, expensive.
++ 
++ ### Rationale
++ - **Incremental re-parsing**: O(log n) edits; only changed regions re-parsed
++ - **Unified query language**: SCM patterns work across all languages
++ - **Error recovery**: Produces valid CST even for malformed code
++ - **Battle-tested**: Used by GitHub, VS Code, Neovim
++ - **No runtime dependencies**: C library + Rust bindings; single binary
++ 
++ ### Consequences
++ - SCM query writing required per language (maintenance)
++ - Tree-sitter grammars may lag behind latest language versions
++ 
++ ---
++ 
++ ## DD-008: ONNX Runtime for Embeddings
++ 
++ **Date**: 2024-01-20
++ **Status**: ✅ Accepted
++ 
++ ### Decision
++ Embedders and cross-encoders run via ONNX Runtime for hardware-agnostic inference.
++ 
++ ### Alternatives Considered
++ 1. **PyTorch/TensorFlow**: Full frameworks; heavy dependencies; slow cold start.
++ 2. **llama.cpp (GGUF)**: Great for LLMs; not optimized for BERT-style encoders.
++ 3. **Custom C++ inference**: Maximum control; massive engineering effort.
++ 
++ ### Rationale
++ - **Hardware-agnostic**: CPU, CUDA, CoreML, DirectML, OpenVINO via execution providers
++ - **Quantization support**: INT8, INT4, FP16 via ONNX Runtime quantization tools
++ - **No Python runtime**: Embed in Rust/Go/C++ binary; fast cold start (~50ms)
++ - **Model zoo**: BGE, E5, Nomic, Jina all export to ONNX
++ - **Standard format**: Portable across training/inference stacks
++ 
++ ### Consequences
++ - Model export step required (PyTorch → ONNX)
++ - Some advanced ops (FlashAttention) may need custom ops
++ 
++ ---
++ 
++ ## DD-009: RocksDB for Graph Storage
++ 
++ **Date**: 2024-01-25
++ **Status**: ✅ Accepted
++ 
++ ### Decision
++ Use embedded RocksDB with column families for graph storage (nodes, edges, properties, indices).
++ 
++ ### Alternatives Considered
++ 1. **Neo4j (embedded)**: License (AGPL/Commercial); heavy; JVM dependency.
++ 2. **Kuzu / Redwood**: Promising but younger; less battle-tested.
++ 3. **SQLite + recursive CTEs**: Simple but slow for deep traversals; no native graph indices.
++ 4. **Custom B+tree on files**: Reinventing LSM trees; RocksDB is mature.
++ 
++ ### Rationale
++ - **Embedded**: No separate process; single binary deployment
++ - **Column families**: Separate CFs for nodes, out-edges, in-edges, labels, properties
++ - **Prefix scans**: Adjacency lists via prefix iteration; efficient graph expansion
++ - **WAL + compaction**: Durability + space reclamation built-in
++ - **Proven at scale**: Used by Facebook, LinkedIn, TiKV, CockroachDB
++ - **Rust bindings**: `rocksdb` crate is well-maintained
++ 
++ ### Consequences
++ - Write amplification from compaction; tune `max_write_buffer_number`
++ - Memory usage from block cache; configure `block_cache_size`
++ 
++ ---
++ 
++ ## DD-010: HNSW + Tantivy + Custom Adjacency Index
++ 
++ **Date**: 2024-01-25
++ **Status**: ✅ Accepted
++ 
++ ### Decision
++ Hybrid semantic index combining: HNSW (vector ANN), Tantivy (BM25 keyword), and custom graph adjacency index—fused via Reciprocal Rank Fusion (RRF).
++ 
++ ### Alternatives Considered
++ 1. **Single vector index (FAISS/HNSW only)**: Misses exact keyword matches; poor for symbols/API names.
++ 2. **Elasticsearch/OpenSearch**: Full-text + vector, but heavy; separate service.
++ 3. **pgvector + pg_trgm**: Good integration, but PostgreSQL dependency; slower ANN.
++ 
++ ### Rationale
++ - **HNSW**: State-of-the-art ANN; `hnswlib`/`faiss` are fast and mature
++ - **Tantivy**: Rust-native BM25; no JVM; used by Meilisearch, Quickwit
++ - **Graph adjacency**: Sub-millisecond neighbor expansion; enables GraphRAG patterns
++ - **RRF fusion**: Parameter-free rank aggregation; robust to score scale differences
++ - **All embedded**: Single process; no network hops between indices
++ 
++ ### Consequences
++ - Three indices to maintain on ingestion; write amplification
++ - RRF weights need tuning per corpus (configurable)
++ 
++ ---
++ 
++ ## DD-011: Cross-Encoder with Isotonic Calibration
++ 
++ **Date**: 2024-01-25
++ **Status**: ✅ Accepted
++ 
++ ### Decision
++ Evidence Gate uses a cross-encoder (e.g., `cross-encoder/ms-marco-MiniLM-L-6-v2`) with isotonic regression calibration for threshold selection.
++ 
++ ### Alternatives Considered
++ 1. **Bi-encoder dot product**: Fast but less accurate; no joint query-doc attention.
++ 2. **Platt scaling (logistic)**: Parametric; assumes sigmoid shape; less flexible.
++ 3. **Temperature scaling**: Single parameter; insufficient for complex score distributions.
++ 4. **No calibration**: Raw scores not probabilities; threshold selection arbitrary.
++ 
++ ### Rationale
++ - **Cross-encoder accuracy**: Joint encoding captures fine-grained relevance
++ - **Isotonic regression**: Non-parametric; fits any monotonic calibration curve
++ - **FDR control**: Calibrated scores enable threshold selection via Benjamini-Hochberg
++ - **Conformal prediction**: Can construct prediction sets with coverage guarantees
++ 
++ ### Consequences
++ - Calibration dataset needed per domain (active learning can reduce labeling)
++ - Isotonic regression can overfit on small calibration sets; use CV
++ 
++ ---
++ 
++ ## DD-012: SSE Streaming Protocol
++ 
++ **Date**: 2024-01-30
++ **Status**: ✅ Accepted
++ 
++ ### Decision
++ Agent runtime streams fine-grained events via Server-Sent Events (SSE): `plan_start`, `step_start`, `evidence_found`, `token`, `step_complete`, `plan_complete`, `budget_warning`.
++ 
++ ### Alternatives Considered
++ 1. **WebSocket**: Bidirectional but more complex; overkill for server→client streaming.
++ 2. **Long polling / HTTP chunked**: Works but no standard event framing; harder to parse.
++ 3. **JSON lines over HTTP**: Similar to SSE but no browser native support.
++ 
++ ### Rationale
++ - **Browser native**: `EventSource` API; automatic reconnection
++ - **Simple framing**: `event: type\ndata: {}\n\n`; easy to parse in any language
++ - **HTTP/2 multiplexing**: Works over h2; no connection overhead
++ - **Firewall friendly**: Standard HTTP; no WebSocket upgrade issues
++ - **Bidirectional via separate WS**: SSE for streaming, WS for control if needed
++ 
++ ### Consequences
++ - Unidirectional; client → server needs separate endpoint (REST/WS)
++ - Connection limits per browser (6 per host on HTTP/1.1); use HTTP/2
++ 
++ ---
++ 
++ ## DD-013: Single-Binary Deployment
++ 
++ **Date**: 2024-01-30
++ **Status**: ✅ Accepted
++ 
++ ### Decision
++ Distribute as a single self-contained binary with embedded models, grammars, and configuration templates.
++ 
++ ### Alternatives Considered
++ 1. **Docker image**: Standard but requires Docker daemon; heavier; layer caching issues.
++ 2. **Package managers (apt, brew, winget)**: Good for updates; but fragmentation across OS.
++ 3. **Python/Rust crate**: Requires runtime; dependency hell; not air-gap friendly.
++ 
++ ### Rationale
++ - **Air-gapped viable**: Copy binary + models directory; no registry pulls
++ - **Simple upgrades**: Replace binary; no migration scripts
++ - **Reproducible**: Same binary on dev, CI, prod
++ - **No container runtime**: Runs on bare metal, VMs, constrained environments
++ - **Cross-platform**: Rust `cargo build --release --target=x86_64-pc-windows-gnu` etc.
++ 
++ ### Consequences
++ - Binary size larger (~100-200MB with embedded models)
++ - Models baked in or loaded from alongside; version sync needed
++ 
++ ---
++ 
++ ## DD-014: Budget Enforcement at Executor
++ 
++ **Date**: 2024-02-01
++ **Status**: ✅ Accepted
++ 
++ ### Decision
++ Agent runtime executor enforces hard budgets (tokens, wall-clock time, tool calls, monetary cost) with configurable overflow behavior: `truncate | partial | error`.
++ 
++ ### Alternatives Considered
++ 1. **Soft limits (warnings only)**: No guarantee; runaway queries still possible.
++ 2. **LLM-based budget awareness**: Unreliable; model may ignore/forget.
++ 3. **No budgets**: Simpler but dangerous for production/automated use.
++ 
++ ### Rationale
++ - **Predictable costs**: Hard ceiling on token/API spend
++ - **Latency SLA**: Wall-clock timeout prevents hung queries
++ - **Graceful degradation**: `truncate` returns partial answer + evidence; `partial` returns what completed
++ - **Observability**: Budget events in SSE stream (`budget_warning`, `budget_exceeded`)
++ 
++ ### Consequences
++ - May cut off mid-synthesis; answer quality varies with budget
++ - Budget accounting must be accurate (token counting, wall-clock)
++ 
++ ---
++ 
++ ## DD-015: Regression Gates in CI
++ 
++ **Date**: 2024-02-01
++ **Status**: ✅ Accepted
++ 
++ ### Decision
++ CI pipeline fails if any primary metric (Evidence F1, Attribution, Hallucination Rate) degrades >2% absolute vs. `main` branch baseline.
++ 
++ ### Alternatives Considered
++ 1. **No gates**: Regressions caught manually (or not at all).
++ 2. **Alerting only (no block)**: Noise fatigue; regressions merge.
++ 3. **Relative thresholds (e.g., 5%)**: Scale-dependent; absolute is clearer.
++ 
++ ### Rationale
++ - **Quality ratchet**: Prevents silent degradation; "green means good"
++ - **2% absolute**: Meaningful but not noisy; calibrated on benchmark variance
++ - **Primary metrics only**: Evidence F1 (retrieval+verification), Attribution (citation quality), Hallucination (safety)
++ - **Bootstrap CI**: 1000 resamples for confidence intervals; Wilcoxon for significance
++ 
++ ### Consequences
++ - Benchmark suite must be fast (<10 min) and deterministic
++ - Baseline stored in repo (or artifact); updated on intentional improvements
++ - Flaky benchmarks block merges; invest in stability
++ 
++ ---
++ 
++ ## Future Decisions (Planned)
++ 
++ | ID | Title | Target |
++ |----|-------|--------|
++ | DD-016 | Incremental Graph Algorithms (PageRank, Communities) | v0.3 |
++ | DD-017 | Multi-Modal Units (Images, Diagrams) | v0.4 |
++ | DD-018 | Distributed Sync (CRDT/OpLog) | v1.0 |
++ | DD-019 | Query Plan Caching & Reuse | v0.3 |
++ | DD-020 | Active Learning for Evidence Gate Calibration | v0.3 |
