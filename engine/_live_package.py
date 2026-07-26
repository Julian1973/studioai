#!/usr/bin/env python3
"""_live_package.py — TESTS THAT READ LIVE PRODUCTION DATA MUST BE DORMANT-SAFE.

Julian, 2026-07-26: "archive all the content and run the episode from a clean run under the
new system." The archive is a supported, deliberate operation — and it broke 15 tests, every
one with the same FileNotFoundError on the Scene 1 production package. They were not testing
the engine; they were testing against whatever happened to be in production.

That is the same fragility class as the cwd-dependent signature hash: a test whose result
depends on ambient state rather than on the code under test. And the house already ruled on
it once — cb_golden.py was made "dormant-safe when no beat package exists" for exactly this
reason. Same treatment here, in one shared place so the next reset does not rediscover it.

A skip is honest: with no package there is genuinely nothing to assert about a real shot. An
ERROR would claim the engine is broken when it is not.
"""
import pathlib

import pytest

HERE = pathlib.Path(__file__).resolve().parent
_CANDIDATES = (
    HERE.parent / "shows" / "crystal-bears" / "episodes" / "output"
    / "Ep1_scene1_production_package.json",
    HERE.parent / "cb-output" / "Ep1_scene1_production_package.json",
)


def live_package_path():
    """The canonical Scene 1 package, or None when the scene has been reset."""
    for p in _CANDIDATES:
        if p.exists():
            return p
    return None


def require_live_package():
    """Skip, never fail, when production has been deliberately cleared.

    Call at module import (`pytestmark = require_live_package()`) or inside a test.
    """
    if live_package_path() is None:
        return pytest.mark.skip(reason="no live Scene 1 production package — the scene has "
                                       "been archived for a clean run; these assertions need "
                                       "real production data and have nothing to check")
    return pytest.mark.skipif(False, reason="")
