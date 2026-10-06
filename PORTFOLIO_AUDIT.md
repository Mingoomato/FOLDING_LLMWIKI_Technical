# Portfolio Audit

| Repository | Problem | Severity | Proposed change | Reason | Verification method |
|---|---|---|---|---|---|
| FOLDING_LLMWIKI_Technical | Stale backup and generated/build artifacts are tracked | P1 | Remove unnecessary backup/build outputs and add intentional ignore rules | Keeps a specification repository source-focused | `git ls-files`, build workflow, and diff inspection |
| FOLDING_LLMWIKI_Technical | README does not clearly distinguish specification from runnable implementation | P1 | Add a short relationship statement and retain the runnable reference link | Prevents readers from mistaking the whitepaper for the shipped application | Review README links and repository structure |
| FOLDING_LLMWIKI_Technical | Benchmark-like figures require clear evidence status | P2 | Preserve measured evidence where identified and label targets/unreleased evaluations explicitly | Avoids presenting design targets as production results | Inspect benchmark context and build the PDF |
