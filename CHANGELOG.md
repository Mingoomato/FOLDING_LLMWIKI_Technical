# LLMWiki Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased] - Main Branch

### Added
- Initial technical specification (11 Volumes + 6 Appendices)
- PROJECT_VISION.md, SYSTEM_PHILOSOPHY.md, ARCHITECTURE.md, ROADMAP.md
- DESIGN_DECISIONS.md (15 decisions logged)
- CONTRIBUTING.md, CHANGELOG.md
- Makefile for LaTeX PDF compilation
- Acronyms (100+), Glossary (40+), Bibliography (12 key references)

### Changed
- Fixed appendix include paths in main LLMWiki.tex

---

## Release Process (Maintainers)

### Versioning
- **Patch** (0.0.x): Bug fixes only, no API changes
- **Minor** (0.x.0): New features, backward compatible
- **Major** (x.0.0): Breaking changes

### Pre-Release Checklist
- [ ] All CI checks pass (tests, benchmarks, security, docs)
- [ ] CHANGELOG.md updated with all changes since last release
- [ ] Version bumped in `Cargo.toml` / `pyproject.toml` / `package.json`
- [ ] Git tag created: `v{major}.{minor}.{patch}`
- [ ] GitHub Release drafted with changelog
- [ ] Binary artifacts uploaded (Linux/macOS/Windows)
- [ ] Homebrew tap updated (if applicable)
- [ ] Docker image pushed to registry
- [ ] Announcement drafted (Discord, Twitter, Discussions)

### Post-Release
- [ ] Update `main` branch version to next dev version (e.g., 0.2.0-dev)
- [ ] Close milestone on GitHub
- [ ] Sync with package managers (crates.io, PyPI, npm, Homebrew)
- [ ] Monitor error rates for 48h

### Hotfix Process
1. Branch from release tag: `git checkout -b hotfix/0.1.1 v0.1.0`
2. Apply minimal fix
3. Bump patch version
4. Run full CI
5. Fast-track review (single maintainer approval)
6. Tag and release
7. Cherry-pick to `main` if applicable

---

## [0.1.0] - TBD (Milestone 1 Target)

### Added
- Core ingestion pipeline (WAL, units, parser, chunker, embedder)
- Knowledge graph (RocksDB, entity resolution v1)
- Hybrid index (HNSW + Tantivy + Adjacency)
- Evidence Gate (cross-encoder + isotonic calibration)
- DAG query planner + agent runtime (SSE)
- REST API + CLI
- Python/JS/TS/Rust/Go parsers
- Single binary release

---

## Template for Future Releases

## [X.Y.Z] - YYYY-MM-DD

### Added
- 

### Changed
- 

### Deprecated
- 

### Removed
- 

### Fixed
- 

### Security
- 

### Performance
- 

---

*See `ROADMAP.md` for planned milestones and `DESIGN_DECISIONS.md` for architectural rationale.*
