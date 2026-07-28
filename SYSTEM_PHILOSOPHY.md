# LLMWiki System Philosophy

This document captures the foundational philosophical commitments that distinguish LLMWiki from other systems. Every architectural decision must be evaluated against these principles.

---

## 1. Graph-First, Vectors-Second

**Principle**: The property knowledge graph is the canonical knowledge representation. Vector indices are derived projections optimized for similarity search — not the primary store.

**Why**: 
- Vectors are lossy projections; they discard structure, causality, and explicit relationships
- Graph enables structural queries (CONTAINS, CALLS, INHERITS, REFERENCES) impossible in vector space
- Multi-hop reasoning requires explicit edges, not implicit similarity
- Deterministic updates: graph mutations are explicit, not implicit via re-embedding

**Contrast**: Most "GraphRAG" systems treat the graph as an auxiliary index. LLMWiki treats vectors as the auxiliary index.

---

## 2. Filesystem as Write-Ahead Log

**Principle**: The local filesystem directory structure `.llmwiki/` serves as the sole durability mechanism. No auxiliary transaction log service (Kafka, Redis Streams, etcd) is required.

**Why**:
- Zero operational dependencies: runs on any POSIX filesystem
- Content-addressed deduplication: identical units → identical WAL entries
- `rsync`/`git` replay: backup = directory copy; replay = re-apply JSONL in order
- POSIX `rename()` atomicity: durable commits without fsync storms
- Auditability: human-readable JSONL; `jq`/`grep` for debugging

**Contrast**: Traditional systems require separate log infrastructure. LLMWiki makes the filesystem the log.

---

## 3. Content Addressability as Identity

**Principle**: Every semantic unit is identified by SHA-256 of its canonical representation: `id(u) = SHA256(canonical(u))`.

**Why**:
- Automatic deduplication across all indices (graph, vector, keyword)
- Verifiable lineage: can prove unit X came from file Y at commit Z
- Cache keys: embedding cache, cross-encoder cache keyed by SHA-256
- Deterministic replay: re-ingestion produces bitwise-identical IDs
- Tamper evidence: any modification changes the ID

**Contrast**: UUID-based systems require explicit deduplication logic; content addressing makes it intrinsic.

---

## 4. Evidence Gate: Filter, Not Reranker

**Principle**: Retrieval candidates must pass a mandatory cross-encoder verification stage before synthesis. This is an **evidence filter** with a calibrated threshold — not a reranker. It may reject *all* candidates (empty evidence set), triggering "insufficient evidence."

**Why**:
- **Evidence Closure Invariant**: `∀c∈citations: verify(c) ≥ τ`
- **Calibrated probabilities**: Isotonic regression maps scores → true P(relevant)
- **FDR control**: Threshold τ chosen to bound False Discovery Rate (e.g., 5%)
- **Honest uncertainty**: Empty set → "I don't know" = better than hallucination
- **Conformal prediction**: Can construct prediction sets with coverage guarantees

**Contrast**: Rerankers always return top-k; they reorder but never say "none are good enough."

---

## 5. Local-First, LLM-Optional Critical Path

**Principle**: All critical-path operations (parsing, chunking, embedding, graph update, indexing, evidence verification, planning) execute on local hardware with zero external API dependencies. LLMs are optional accelerators for planning, entity extraction, and synthesis.

**Why**:
- **Air-gapped deployment**: Works in SCIFs, offline, secure enclaves
- **Data sovereignty**: Source code, docs, configs never leave the machine
- **Predictable latency**: No network variance, rate limits, cold starts
- **Zero marginal cost**: No per-token or per-query charges
- **Offline development**: Full functionality on airplane/train

**Contrast**: Most RAG frameworks assume cloud LLM + cloud vector DB. LLMWiki works fully local.

---

## 6. DAG Query Planner with Cost Model

**Principle**: Query planner compiles natural language into a DAG of executable subqueries (retrieval, graph traversal, tool calls, synthesis), optimized via a cost model over index statistics.

**Why**:
- **Parallel fan-out**: Independent subqueries execute concurrently (vector + keyword + graph)
- **Subquery decomposition**: Complex questions → multiple focused retrievals → synthesis
- **Strategy selection**: Planner chooses vector/graph/keyword per subquery based on cost model
- **Explainability**: DAG is inspectable; each step has estimated cost
- **Budget enforcement**: Cost model drives token/time/call limits at executor

**Contrast**: Linear chains (ReAct) or fixed templates lack parallelism and adaptivity.

---

## 7. Incremental Consistency

**Principle**: After any ingestion, system state (G, I, U) — graph, index, units — satisfies: a query against live state produces same result as replaying the ingestion log.

**Why**:
- No "eventual consistency" surprises
- CI reproducibility: test ingest → query matches log replay
- Backup/restore = copy `.llmwiki/` directory

**Contrast**: Systems with async index updates have stale reads; LLMWiki is strongly consistent by design.

---

## 8. Deterministic Replay

**Principle**: Given identical `.llmwiki/` directory and identical query `q`, two executions produce bitwise-identical results (modulo non-deterministic LLM sampling, confined to planning/synthesis).

**Why**:
- Debugging: reproduce exact state from customer environment
- Testing: golden-file tests for retrieval/planning
- Auditing: prove answer came from specific evidence at specific time
- Science: reproducible experiments

---

## 9. Preserve Evidence, Compress the Envelope

**Principle**: Context shaping may select fewer verified units and remove
repeated metadata, but it never summarizes, abbreviates, normalizes, or rewrites
the evidence text that a citation claims to support.

**Why**:
- Human reviewers must compare cited text directly with the source artifact
- Model-visible integer handles keep UUID cost off the wire while the host
  retains exact `content_id`/occurrence/span resolution
- Deterministic selection and serialization preserve replay
- Token savings are evaluated jointly with answer quality, never alone

**Contrast**: Learned prompt compressors can reduce more tokens but modify the
evidence and add a model to the critical path. LLMWiki compresses the transport
envelope and treats evidence selection as an explicitly measured budget policy.

---

## Summary: The LLMWiki Difference

LLMWiki is not "RAG with a graph." It is a **semantic operating layer** with these invariants:

1. **Graph is truth** → vectors are views
2. **Filesystem is WAL** → no extra infra
3. **SHA-256 is identity** → dedup/lineage/cache for free
4. **Evidence Gate is mandatory** → calibrated, can say "I don't know"
5. **Local-first** → air-gap, sovereignty, cost, latency
6. **DAG planner** → parallel, explainable, budgeted
7. **Incremental consistency** → no stale reads
8. **Deterministic replay** → debug, test, audit, science
9. **Evidence-preserving context** → compact transport without unauditable citations

---
*These principles are non-negotiable. Proposals violating them require explicit architecture review.*
