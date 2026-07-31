"""Repository-wide protection against tests mutating live production state."""
from __future__ import annotations

import pathlib
import sys

import pytest


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

    import cb_learning

    learning = tmp_path / "learning"
    monkeypatch.setattr(cb_learning, "LEARNING", learning)
    monkeypatch.setattr(cb_learning, "EVIDENCE_P", learning / "EVIDENCE_LIBRARY.json")
    monkeypatch.setattr(cb_learning, "PATTERNS_P", learning / "PATTERN_LIBRARY.json")
    monkeypatch.setattr(
        cb_learning, "ACTIVE_P", learning / "ACTIVE_CREATIVE_MEMORY.json"
    )
