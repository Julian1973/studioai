"""engine/conftest.py — SESSION-WIDE TEST ISOLATION.

The standing suite exercises the REAL production entry points with mocked providers —
which is the right way to test them, and exactly why any ledger those paths write to must
be redirected for the whole session rather than per-test. A new test cannot forget this;
there is nothing to remember.

Caught live 2026-07-25: wiring the verdict corpus into fire_shot immediately put 90
synthetic records into the production corpus on the very next test run.
"""
import os
import pathlib
import tempfile

import pytest


@pytest.fixture(autouse=True, scope="session")
def _isolate_corpus():
    with tempfile.TemporaryDirectory(prefix="cb-corpus-test-") as tmp:
        os.environ["CB_CORPUS_DIR"] = tmp
        yield
        os.environ.pop("CB_CORPUS_DIR", None)
