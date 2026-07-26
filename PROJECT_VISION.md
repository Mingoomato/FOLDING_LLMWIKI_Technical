++ # LLMWiki Project Vision
++ 
++ ## Mission
++ 
++ **LLMWiki is not a Retrieval-Augmented Generation framework. It is a semantic operating layer that continuously transforms heterogeneous digital artifacts into an evidence-aware knowledge space.**
++ 
++ ---
++ 
++ ## Goals
++ 
++ 1. **Transform all local files into an evidence-aware semantic graph**
++    - Source code, docs, configs, schemas, specs, notes → unified knowledge graph
++    - Every claim traceable to verified evidence units
++ 
++ 2. **Enable local-first, air-gapped operation with zero external dependencies**
++    - Critical path runs entirely on local hardware
++    - LLMs are optional accelerators, not requirements
++    - Single binary deployment
++ 
++ 3. **Provide deterministic, auditable, reproducible knowledge operations**
++    - Content-addressed units (SHA-256)
++    - Filesystem as write-ahead log
++    - Bitwise-replayable from ingestion log
++ 
++ 4. **Enforce evidence closure: every citation verified, or "insufficient evidence"**
++    - Cross-encoder verification gate (not reranker)
++    - Calibrated thresholds with FDR control
++    - Conformal prediction for coverage guarantees
++ 
++ 5. **Support complex multi-hop reasoning via DAG query planning**
++    - Parallel retrieval fan-out
++    - Strategy selection per subquery
++    - Budget-aware execution
++ 
++ ---
++ 
++ ## Non-Goals (Explicitly Out of Scope)
++ 
++ | Non-Goal | Rationale |
++ |----------|-----------|
++ | Chatbot / Conversational Agent | LLMWiki is a knowledge layer, not a chat UI |
++ | Pure Vector RAG | Graph is canonical; vectors are projections |
++ | Cloud-First / SaaS | Local-first is architectural principle |
++ | AutoML / Model Training | Consumes models, doesn't train them |
++ | General-Purpose Graph DB | Purpose-built for semantic code/docs knowledge |
++ | Replacement for Search Engines | Complements; focuses on structural + semantic hybrid |
++ 
++ ---
++ 
++ ## Principles
++ 
++ 1. **Graph as Source of Truth** — Vectors are derived views; structure is primary
++ 2. **Filesystem as WAL** — Zero operational dependencies; `rsync` = backup
++ 3. **Content Addressability** — SHA-256 identity enables dedup, cache, lineage
++ 4. **Evidence Gate Mandatory** — Filter with calibrated threshold; empty set = honest "I don't know"
++ 5. **Local-First, LLM-Optional** — Critical path has zero external calls
++ 6. **DAG Query Planner** — Parallel, explainable, budgeted
++ 7. **Incremental Consistency** — Live state = log replay state
++ 8. **Deterministic Replay** — Same input → same output (modulo LLM sampling)
++ 
++ ---
++ 
++ ## Target Users
++ 
++ - **Software Engineers**: Understand large codebases, trace calls, find patterns
++ - **Security Researchers**: Audit dependencies, find vulnerabilities, trace data flow
++ - **Technical Writers**: Maintain living documentation synced with code
++ - **Architects**: Visualize system structure, dependencies, evolution
++ - **Researchers**: Reproducible experiments on code/document corpora
++ - **Air-Gapped Environments**: Defense, finance, regulated industries
++ 
++ ---
++ 
++ ## Success Metrics
++ 
++ ### Technical
++ - Evidence F1 ≥ 0.85 on LLMWikiBench
++ - Attribution Score ≥ 0.90
++ - Hallucination Rate ≤ 0.02
++ - p95 Query Latency ≤ 2s (local, 100K units)
++ - Ingestion Throughput ≥ 5K units/sec
++ - Deterministic Replay: 100% bitwise match
++ 
++ ### Adoption
++ - Single-binary install < 30 seconds
++ - Index 1M LOC repo < 5 minutes
++ - Extension API: new parser in < 100 lines
++ 
++ ---
++ 
++ ## Long-Term Vision (3-5 Years)
++ 
++ 1. **Semantic OS Kernel**: LLMWiki becomes the knowledge substrate for local AI agents
++ 2. **Distributed Sync**: CRDT-based multi-node synchronization (DD-018)
++ 3. **Multi-Modal Units**: Images, diagrams, audio as first-class semantic units (DD-017)
++ 4. **Incremental Graph Algorithms**: Live PageRank, community detection (DD-016)
++ 5. **Active Learning**: Evidence Gate self-calibrates from user feedback (DD-020)
++ 6. **Standards Track**: Open specification for semantic unit interchange
++ 
++ ---
++ *This vision is the north star. All design decisions trace back to these principles.*
++ *See `DESIGN_DECISIONS.md` for the decision log.*
