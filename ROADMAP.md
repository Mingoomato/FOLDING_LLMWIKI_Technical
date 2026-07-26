++ # LLMWiki Implementation Roadmap
++ 
++ This roadmap sequences implementation from foundation to production readiness.
++ Each milestone has clear exit criteria and deliverables.
++ 
++ ---
++ 
++ ## Milestone 0: Foundation (Weeks 1-3) ✅ SPECIFIED
++ 
++ **Status**: Documentation complete; implementation pending
++ 
++ ### Deliverables
++ - [x] Architecture specification (Volume 01)
++ - [x] Semantic parsing spec (Volume 02)
++ - [x] Knowledge graph spec (Volume 03)
++ - [x] Retrieval + Evidence Gate spec (Volume 04)
++ - [x] Agent runtime spec (Volume 05)
++ - [x] Evaluation spec (Volume 06)
++ - [x] Deployment spec (Volume 07)
++ - [x] API reference (Volume 08)
++ - [x] Developer guide (Volume 09)
++ - [x] Patent claims (Volume 10)
++ - [x] Research paper (Volume 11)
++ - [x] Bibliography + Acronyms + Glossary
++ - [x] Design decision log (DESIGN_DECISIONS.md)
++ - [x] PROJECT_VISION.md, SYSTEM_PHILOSOPHY.md, ARCHITECTURE.md
++ 
++ ### Exit Criteria
++ - All 11 volumes + appendices compile to PDF (latexmk clean)
++ - Design decisions traceable to requirements
++ - Patent claims distinguishable from prior art
++ 
++ ---
++ 
++ ## Milestone 1: Core Engine Prototype (Weeks 4-8)
++ 
++ **Goal**: End-to-end ingestion → graph → index → query on local files
++ 
++ ### Components
++ 
++ | Component | Tech | Effort |
++ |-----------|------|--------|
++ | Project scaffolding | Rust workspace (cargo) | 2 days |
++ | Filesystem WAL | std::fs, serde_json | 3 days |
++ | Content-addressed units | sha2 crate, canonicalization | 3 days |
++ | Tree-sitter parser framework | tree-sitter, tree-sitter-rust | 5 days |
++ | Python/JS/TS/Rust/Go grammars | 5 languages × 2 days | 10 days |
++ | AST-aware chunker | tree-sitter queries | 3 days |
++ | ONNX embedder (BGE-M3) | ort, tokenizers | 5 days |
++ | RocksDB graph store | rocksdb crate, column families | 5 days |
++ | Entity resolution (v1: exact) | — | 3 days |
++ | Hybrid index (HNSW + Tantivy) | hnswlib, tantivy | 5 days |
++ | Evidence Gate (cross-encoder) | ort, isotonic regression | 5 days |
++ | DAG Planner (LLM + cost model) | ort, custom | 5 days |
++ | Agent Runtime (SSE streaming) | axum, tokio | 5 days |
++ | CLI + REST API | clap, axum | 3 days |
++ 
++ ### Exit Criteria
++ - `llmwiki init` → `.llmwiki/` created
++ - `llmwiki ingest ./my-project` → parses, chunks, embeds, graphs, indexes
++ - `llmwiki query "How does X call Y?"` → returns answer with citations
++ - Ingestion re-run = no-op (content-addressed)
++ - WAL replay produces identical state
++ - All unit tests pass; integration tests pass
++ 
++ ---
++ 
++ ## Milestone 2: Quality & Hardening (Weeks 9-14)
++ 
++ **Goal**: Production-grade reliability, performance, extensibility
++ 
++ ### Components
++ 
++ | Area | Tasks |
++ |------|-------|
++ | **Parsing** | Error recovery, incremental diff, 20+ languages, custom SCM |
++ | **Chunking** | Respect token bounds, overlap, hierarchy, table-aware |
++ | **Embedding** | Quantization (INT8/INT4), batching, GPU providers, model swap |
++ | **Graph** | Column family tuning, compaction, prefix iterators, snapshots |
++ | **Index** | HNSW ef_search tuning, Tantivy analyzer config, RRF weight sweep |
++ | **Evidence Gate** | Calibration (isotonic/Platt), conformal, active learning loop |
++ | **Planner** | Cost model training, strategy selection, plan cache |
++ | **Runtime** | Budget enforcement, tool SDK, middleware, observability |
++ | **API** | Auth (OIDC/mTLS/API key), rate limiting, OpenAPI spec |
++ | **CLI** | Watch mode, progress, config profiles, shell completions |
++ | **Testing** | Property tests, fuzzing, chaos, benchmark CI gate |
++ | **Docs** | Tutorials, cookbook, migration guides, architecture diagrams |
++ 
++ ### Exit Criteria
++ - p95 query latency ≤ 2s (100K units, local CPU)
++ - Ingestion throughput ≥ 5K units/sec
++ - Evidence F1 ≥ 0.80 on LLMWikiBench
++ - Attribution Score ≥ 0.85
++ - Hallucination Rate ≤ 0.05
++ - 0 critical CVEs; `cargo deny check` clean
++ - Cross-platform builds (Linux/macOS/Windows)
++ - Single binary < 200MB (with embedded models)
++ 
++ ---
++ 
++ ## Milestone 3: Evaluation & Research (Weeks 15-20)
++ 
++ **Goal**: Rigorous benchmark, reproducible experiments, paper submission
++ 
++ ### Components
++ 
++ | Task | Details |
++ |------|---------|
++ | LLMWikiBench v1.0 | 10 repos × 100 questions × 5 languages |
++ | Baseline comparisons | GraphRAG, HippoRAG, LightRAG, RAPTOR, vanilla RAG |
++ | Ablation studies | -Gate, -Graph, -Hybrid, -Incremental, -Local |
++ | Statistical rigor | Bootstrap CI, Wilcoxon, FDR, effect sizes |
++ | Reproducibility | Docker + dataset hashes + exact commands |
++ | Paper draft | ARR / ICML / NeurIPS target |
++ | Patent filing | 14 claims (4 independent + 10 dependent) |
++ 
++ ### Exit Criteria
++ - Paper submitted (or preprint on arXiv)
++ - Patent application filed
++ - Benchmark results published with code
++ - All results reproducible from artifact
++ 
++ ---
++ 
++ ## Milestone 4: Ecosystem & Extensions (Weeks 21-28)
++ 
++ **Goal**: Developer experience, extension marketplace, community
++ 
++ ### Components
++ 
++ | Area | Tasks |
++ |------|-------|
++ | Extension SDK | Parser, Chunker, Embedder, Graph, Index, Tool traits |
++ | Example extensions | COBOL parser, PlantUML chunker, custom embedder |
++ | WASM plugins | Sandbox extensions, hot-reload |
++ | VS Code extension | Inline answers, graph view, query history |
++ | Language Server | LSP for semantic queries in IDE |
++ | Package registry | `llmwiki pkg add <name>` |
++ | CI/CD templates | `.github/workflows/llmwiki.yml` |
++ | Migration guides | From LangChain, LlamaIndex, GraphRAG |
++ 
++ ### Exit Criteria
++ - ≥ 5 community extensions published
++ - VS Code extension in marketplace
++ - Migration docs for top 3 frameworks
++ - ≥ 100 GitHub stars (early indicator)
++ 
++ ---
++ 
++ ## Milestone 5: Distributed & Multi-Modal (Weeks 29-40)
++ 
++ **Goal**: Horizontal scaling, multi-modal units, ecosystem maturity
++ 
++ ### Planned (Design Decisions DD-016 to DD-020)
++ 
++ | Decision | Title | Target |
++ |----------|-------|--------|
++ | DD-016 | Incremental Graph Algorithms (PageRank, Communities) | v0.3 |
++ | DD-017 | Multi-Modal Units (Images, Diagrams, Audio) | v0.4 |
++ | DD-018 | Distributed Sync (CRDT/OpLog) | v1.0 |
++ | DD-019 | Query Plan Caching & Reuse | v0.3 |
++ | DD-020 | Active Learning for Evidence Gate Calibration | v0.3 |
++ 
++ ### Architecture Evolution
++ 
++ - Shared-nothing graph shards
++ - CRDT-based WAL merge
++ - Central planner coordinator
++ - Multi-modal embedders (CLIP, AudioMAE)
++ - Vector search over multi-modal units
++ 
++ ---
++ 
++ ## Versioning & Release Cadence
++ 
++ | Version | Target | Focus |
++ |---------|--------|-------|
++ | 0.1.0 | Week 8 | Core prototype |
++ | 0.2.0 | Week 14 | Quality hardening |
++ | 0.3.0 | Week 20 | Research artifacts |
++ | 0.4.0 | Week 28 | Ecosystem |
++ | 1.0.0 | Week 40 | Production ready |
++ 
++ - **Monthly** patch releases (bug fixes only)
++ - **Quarterly** minor releases (features)
++ - **Annual** major releases (breaking changes)
++ - LTS: 1.0.x supported 2 years
++ 
++ ---
++ 
++ ## Resource Estimates
++ 
++ | Role | FTE (Milestones 1-3) | FTE (Milestones 4-5) |
++ |------|---------------------|---------------------|
++ | Rust Engineer (Core) | 2 | 2 |
++ | ML Engineer (Embeddings/Gate) | 1 | 1 |
++ | NLP/IR Researcher | 0.5 | 1 |
++ | DevOps/Release | 0.5 | 1 |
++ | Technical Writer | 0.5 | 1 |
++ | Community Manager | 0 | 1 |
++ 
++ ---
++ 
++ ## Risk Register
++ 
++ | Risk | Likelihood | Impact | Mitigation |
++ |------|------------|--------|------------|
++ | Tree-sitter grammar gaps | Medium | High | Fallback to heuristic chunker; contribute upstream |
++ | Cross-encoder latency | High | Medium | Quantization, distillation, batching, caching |
++ | RocksDB write amplification | Medium | Medium | Tune compaction; consider sled for metadata |
++ | LLM planner hallucination | Medium | High | Schema validation, fallback planner, budget limits |
++ | Patent prior art overlap | Low | High | Continuous prior art search; claim differentiation |
++ | Benchmark gaming | Medium | Medium | Hidden test set; bootstrap CI; independent replication |
++ | Single-binary size > 500MB | Low | Medium | Model pruning; optional model download |
++ 
++ ---
++ *This roadmap is a living document. Update with each milestone retrospective.*
++ *See `DESIGN_DECISIONS.md` for decision traceability.*
