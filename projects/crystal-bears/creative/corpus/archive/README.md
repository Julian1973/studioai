# POLLUTED_BY_TESTS_20260725.jsonl — archived, not deleted

90 fire records + 86 verdicts written 2026-07-25 16:25-16:28 by the standing test suite,
not by any real generation. The corpus had just been wired into `cb_render.fire_shot`, and
the suite exercises that real entry point with mocked providers — so every mocked fire
recorded itself as if it were production. Episode label `EpT`, shot ids `1.B1.S*`: all
synthetic fixtures, zero provider calls, zero spend.

Archived rather than deleted per this project's standing never-delete rule. It is NOT
corpus data and must never be read as evidence — nothing in it ever rendered.

Fixed the same hour: `cb_corpus._dir()` resolves `CB_CORPUS_DIR` at call time, and
`engine/conftest.py` points the whole test session at a scratch directory, so no test can
reach the production corpus again.
