++ # Contributing to LLMWiki
++ 
++ Thank you for contributing! This document outlines the process and standards for contributing to LLMWiki.
++ 
++ ---
++ 
++ ## Code of Conduct
++ 
++ This project follows the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/version/2/1/code_of_conduct/). By participating, you agree to uphold this code.
++ 
++ ---
++ 
++ ## Ways to Contribute
++ 
++ 1. **Core Implementation** (Rust): Parser, graph, index, planner, runtime
++ 2. **Language Support**: Tree-sitter grammars + SCM queries for new languages
++ 3. **Models**: ONNX export/quantization of embedders, cross-encoders
++ 4. **Benchmarks**: Datasets, evaluation scripts, metric implementations
++ 5. **Documentation**: Specification volumes, API docs, tutorials
++ 6. **Tooling**: CI/CD, packaging, IDE extensions, SDKs
++ 7. **Research**: Experiments, ablation studies, paper writing
++ 
++ ---
++ 
++ ## Development Setup
++ 
++ ### Prerequisites
++ - Rust 1.75+ (MSRV)
++ - Python 3.10+ (for benchmarking, ONNX export)
++ - Cargo tools: `cargo-nextest`, `cargo-deny`, `cargo-audit`, `cargo-tarpaulin`
++ - LLVM/Clang (for tree-sitter compilation)
++ 
++ ### Quick Start
++ ```bash
++ git clone https://github.com/jungmingyu/llmwiki
++ cd llmwiki
++ cargo build --release
++ ./target/release/llmwiki --help
++ ```
++ 
++ ### Running Tests
++ ```bash
++ # Unit + integration tests
++ cargo nextest run
++ 
++ # With coverage
++ cargo tarpaulin --out html
++ 
++ # Fuzzing (requires nightly)
++ cargo fuzz run
++ 
++ # Benchmarks
++ cargo bench
++ ```
++ 
++ ---
++ 
++ ## Architecture Principles (Non-Negotiable)
++ 
++ Before proposing changes, read and understand:
++ 
++ 1. **PROJECT_VISION.md** — What we're building and why
++ 2. **SYSTEM_PHILOSOPHY.md** — 8 foundational principles
++ 3. **DESIGN_DECISIONS.md** — 15 recorded decisions with rationale
++ 4. **ARCHITECTURE.md** — High-level system map
++ 
++ **Do not propose changes that violate these principles without explicit architecture review.**
++ 
++ ---
++ 
++ ## Contribution Workflow
++ 
++ ### 1. Discuss First
++ - Open an issue for bugs, features, or design discussions
++ - For significant changes (>100 lines or architectural), open a **Design Discussion** issue
++ - Tag with `design-review` for maintainer attention
++ 
++ ### 2. Fork & Branch
++ - Fork the repo
++ - Branch from `main`: `git checkout -b feat/your-feature`
++ - Use conventional commit prefixes: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `bench:`
++ 
++ ### 3. Implement
++ - Follow Rust idioms (Clippy clean, rustfmt)
++ - Add tests for new functionality
++ - Update documentation (code + markdown)
++ - Run `cargo deny check` for license/security audit
++ 
++ ### 4. Test Locally
++ ```bash
++ cargo nextest run --all-targets
++ cargo fmt --all --check
++ cargo clippy --all-targets -- -D warnings
++ cargo deny check
++ ```
++ 
++ ### 5. Submit PR
++ - Fill out the PR template
++ - Link related issues
++ - Include benchmark results if performance-related
++ - Ensure CI passes
++ 
++ ---
++ 
++ ## Code Standards
++ 
++ ### Rust
++ - Edition 2021
++ - MSRV: 1.75
++ - `#[deny(clippy::all, clippy::pedantic)]` (allow list in Clippy.toml)
++ - `rustfmt` with default config
++ - Error handling: `eyre` for applications, `thiserror` for libraries
++ - Async: `tokio` (latest), prefer structured concurrency
++ - Serialization: `serde` + `serde_json` (human) / `bincode` (internal)
++ - Logging: `tracing` (structured, OTel compatible)
++ 
++ ### Tree-sitter SCM Queries
++ - One `.scm` file per language in `grammars/`
++ - Follow `tree-sitter` query conventions
++ - Test against real-world code samples
++ - Document node types extracted in parser documentation
++ 
++ ### Documentation
++ - Public APIs: rustdoc with examples
++ - Architecture changes: update relevant Volume in `docs/`
++ - Design decisions: add entry to `DESIGN_DECISIONS.md`
++ - User-facing: `docs/user/` (separate from spec)
++ 
++ ---
++ 
++ ## Testing Requirements
++ 
++ ### Unit Tests
++ - Target: ≥80% coverage for core crates (`llmwiki-core`, `llmwiki-graph`, `llmwiki-index`)
++ - Property-based testing for parsers, chunkers, hash functions
++ 
++ ### Integration Tests
++ - End-to-end: ingest → query → verify citations
++ - Golden-file tests for deterministic replay
++ - Cross-platform: Linux, macOS, Windows (CI)
++ 
++ ### Benchmarks
++ - Criterion benchmarks for hot paths (parsing, embedding, index search)
++ - LLMWikiBench suite for retrieval quality
++ - Regression threshold: 2% absolute on primary metrics
++ 
++ ### Fuzzing
++ - `cargo-fuzz` targets for parsers, WAL parser, query planner
++ - Run in CI nightly
++ 
++ ---
++ 
++ ## Adding a New Language Parser
++ 
++ 1. Add tree-sitter grammar as submodule in `grammars/`
++ 2. Write SCM queries in `grammars/{lang}.scm`
++ 3. Implement `Parser` trait in `crates/llmwiki-parsers/src/{lang}.rs`
++ 4. Add integration test with real code samples
++ 5. Update `SUPPORTED_LANGUAGES.md` and docs
++ 6. Benchmark parsing throughput
++ 
++ ---
++ 
++ ## Adding a New Embedder / Cross-Encoder
++ 
++ 1. Export model to ONNX (FP32 → INT8 quantization)
++ 2. Place in `models/` with metadata JSON
++ 3. Implement `Embedder` / `CrossEncoder` trait
++ 4. Add calibration dataset + script
++ 5. Benchmark latency/accuracy tradeoff
++ 6. Update config schema defaults
++ 
++ ---
++ 
++ ## Adding a New Tool
++ 
++ 1. Define JSON schema in `schemas/tools/{tool}.json`
++ 2. Implement `Tool` trait in `crates/llmwiki-runtime/src/tools/`
++ 3. Register in tool registry
++ 4. Add integration test
++ 5. Document in Volume 08 (API Reference) and Volume 09 (Developer Guide)
++ 
++ ---
++ 
++ ## Pull Request Review Criteria
++ 
++ Maintainers will verify:
++ 
++ - [ ] **Architectural alignment**: Consistent with SYSTEM_PHILOSOPHY.md
++ - [ ] **Tests pass**: All CI checks green
++ - [ ] **No regressions**: Benchmark gate passes
++ - [ ] **Documentation updated**: Code + relevant Volume
++ - [ ] **Design decision logged** (if applicable): DD-XXX entry
++ - [ ] **Security**: `cargo deny check` clean; no new vulnerabilities
++ - [ ] **Licenses**: All deps compatible (Apache-2.0 / MIT / BSD-3)
++ - [ ] **Performance**: No significant regression without justification
++ - [ ] **Cross-platform**: Builds on Linux/macOS/Windows
++ 
++ ---
++ 
++ ## Release Checklist (Maintainers)
++ 
++ See [CHANGELOG.md](CHANGELOG.md#release-process).
++ 
++ ---
++ 
++ ## Security
++ 
++ Report security vulnerabilities to `security@llmwiki.example.com` (not public issues).
++ 
++ ---
++ 
++ ## License
++ 
++ By contributing, you agree that your contributions will be licensed under the
++ [Apache License 2.0](LICENSE) (or MIT, at your option), consistent with the project license.
++ 
++ ---
++ 
++ ## Questions?
++ 
++ - Open a Discussion on GitHub
++ - Email: `maintainers@llmwiki.example.com`
++ - See `DESIGN_DECISIONS.md` for context on why things are the way they are
++ 
++ ---
++ *Welcome to the LLMWiki community! Building a semantic operating layer is ambitious work — thank you for being part of it.*
