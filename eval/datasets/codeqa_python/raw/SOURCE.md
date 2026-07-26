# Corpus provenance

`queue.py` and `heapq.py` are CPython standard library modules, fetched from
`https://raw.githubusercontent.com/python/cpython/main/Lib/` on 2026-07-27.
CPython is licensed under the PSF License; these files are included here as a
minimal, stable, real (not synthetic) proof-of-concept corpus slice for the
LLMWikiBench harness scaffold -- **not** as the actual CodeQA-Python
benchmark, which per Vol. 06 Table eval:internal requires 50 repos / 200K
units. See `eval/README.md` for what scaling this up to the real benchmark
requires.
