"""Repository-wide protection against tests mutating live production state."""
from __future__ import annotations

import os
import pathlib
import sys

import pytest


# The suite's own fixtures and golden data are the first project's. paths.* resolves the active
# project at IMPORT time, so this has to be set here, before collection imports anything — with
# the studio switched to another production (cb-studio/data/active-project.json, T59) the whole
# suite otherwise ran against that project and ~90 tests failed on a cast and package names that
# were never theirs. An explicit STUDIO_PROJECT still wins; the second-project isolation test
# passes its own to a subprocess and is unaffected.
os.environ.setdefault("STUDIO_PROJECT", "crystal-bears")

ROOT = pathlib.Path(__file__).resolve().parent
ENGINE = ROOT / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))


@pytest.fixture(autouse=True)
def isolate_mutable_production_state(monkeypatch, tmp_path):
    """Route every test's database and learning writes into its own scratch tree."""
    monkeypatch.setenv(
        "CB_STUDIO_STATE_DB", str(tmp_path / "state" / "studio.sqlite3")
    )

    # T64: a full run used to append test prompts to the real prompt bank and re-register the
    # real assets at this machine's paths, so `git status` came back dirty every time (the
    # committed prompt_bank.jsonl already carries pytest tmp paths from the Mac). Both are plain
    # module constants read at call time, so the same redirection the learning store already
    # uses closes it: a test that wants the real files still patches them itself.
    import cb_asset_registry
    import cb_prompt_bank

    registry = tmp_path / "asset-registry"
    monkeypatch.setattr(cb_asset_registry, "REGISTRY_DIR", registry)
    monkeypatch.setattr(cb_asset_registry, "REGISTRY_PATH", registry / "assets.json")
    monkeypatch.setattr(
        cb_prompt_bank, "DEFAULT_BANK_PATH", tmp_path / "prompt-bank" / "prompt_bank.jsonl"
    )

    import cb_learning

    learning = tmp_path / "learning"
    monkeypatch.setattr(cb_learning, "LEARNING", learning)
    monkeypatch.setattr(cb_learning, "EVIDENCE_P", learning / "EVIDENCE_LIBRARY.json")
    monkeypatch.setattr(cb_learning, "PATTERNS_P", learning / "PATTERN_LIBRARY.json")
    monkeypatch.setattr(
        cb_learning, "ACTIVE_P", learning / "ACTIVE_CREATIVE_MEMORY.json"
    )
