# LLMWikiBench harness run (illustrative scaffold, not a benchmark result)

Generated: 2026-07-26T23:19:57.465855+00:00
Corpus: 49 SemanticUnits, 54 UnitOccurrences from ['heapq.py', 'queue.py']
Gold set: 5 questions -- single-reviewer illustrative sample -- NOT a validated benchmark; see PROTOCOL.md
Retrieval backend: BM25 (local, no external calls) -- see retrieval_baseline.py docstring for scope

## Metrics

| k | EvRecall@k | EvPrecision@k | Evidence F1@k |
|---|-----------|---------------|---------------|
| 5 | 0.600 | 0.120 | 0.200 |
| 10 | 1.000 | 0.100 | 0.182 |
| 20 | 1.000 | 0.050 | 0.095 |

Gate rejection rate: 0.000

## Per-query detail

- [HIT] `gen-8deab73c8802-0`: What does the function `heappush` do?
- [HIT] `gen-cedeac032c5a-2`: What does the function `heappop` do?
- [HIT] `gen-c55e67f024cd-8`: What does the function `heapify` do?
- [MISS] `gen-1825741bd48b-38`: What does the class `Queue` implement?
- [MISS] `gen-1825741bd48b-39`: Which module defines the class `Queue`?