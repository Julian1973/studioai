"""Repository-wide protection against tests mutating live production state."""
from __future__ import annotations

import pathlib
import sys
import socket

import pytest


ROOT = pathlib.Path(__file__).resolve().parent
ENGINE = ROOT / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))


def pytest_collection_finish(session):
    """Keep the imported application graph out of Python 3.14's costly GC rescans.

    Collection has imported the static production/test modules; no test fixtures have
    run yet. New test objects remain collectable, including pytest's unraisable-error
    checks. This mirrors the Studio server's existing immutable-graph freeze.
    """
    if sys.version_info[:2] == (3, 14):
        import gc
        gc.freeze()


@pytest.fixture(autouse=True)
def prohibit_external_test_network(monkeypatch):
    """A missed provider mock must fail locally, never create paid work."""
    original = socket.socket.connect

    def connect(sock, address):
        if isinstance(address, tuple) and address[0] not in {"127.0.0.1", "::1", "localhost"}:
            raise RuntimeError("External network is disabled in Studio tests; mock the provider.")
        return original(sock, address)

    monkeypatch.setattr(socket.socket, "connect", connect)


@pytest.fixture(autouse=True)
def isolate_mutable_production_state(monkeypatch, tmp_path):
    """Route every test's database and learning writes into its own scratch tree."""
    monkeypatch.setenv(
        "CB_STUDIO_STATE_DB", str(tmp_path / "state" / "studio.sqlite3")
    )

    monkeypatch.setenv("CB_EPISODE_BUDGET_ROOT", str(tmp_path / "episode-budgets"))

    import cb_learning

    learning = tmp_path / "learning"
    monkeypatch.setattr(cb_learning, "LEARNING", learning)
    monkeypatch.setattr(cb_learning, "EVIDENCE_P", learning / "EVIDENCE_LIBRARY.json")
    monkeypatch.setattr(cb_learning, "PATTERNS_P", learning / "PATTERN_LIBRARY.json")
    monkeypatch.setattr(
        cb_learning, "ACTIVE_P", learning / "ACTIVE_CREATIVE_MEMORY.json"
    )
