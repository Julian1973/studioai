#!/usr/bin/env python3
"""test_studio_artifact_cards.py — ONE ARTIFACT, ONE CARD, ONE DECISION.

Julian, 2026-07-27:

    "I want a UI and interface that allows me to generate upload or use from library /
     agree or reject / re run / and then move... it has to have the depth and complexity
     at the back but the simple intuitive interface at the front — at the moment a gate
     can have multiple things to sign off like approve director create scene plate etc etc."

The last clause is the defect. Nothing was ever MISSING: cb_render already exposes generate /
upload / library / approve / reject / re-run for every artifact in the show, and every one of
those verbs already reached app.html. What was wrong is that they were grouped by GATE rather
than by ARTIFACT, so one "Approve" could mean two different things depending where it sat.

`ARTIFACTS` in app.html is the regrouping. This file is its binding, and it is the same shape
as test_studio_chair_table.py's — because this project has shipped the "two tables, one truth"
bug twice already (the chair table, then the shot panel) and both times the second table was a
hand-written copy that silently drifted.

The engine is the authority in BOTH directions:
  · a card may not offer a verb cb_render does not implement (a button that can only fail);
  · an artifact cb_render implements may not be missing a card (a capability with no door —
    the exact "computed and thrown away" defect that hid advance_shot, the cost ledger and
    auto-prepare for weeks).

    pytest test_studio_artifact_cards.py -q
"""
import json
import pathlib
import re
import shutil
import subprocess

import pytest

HERE = pathlib.Path(__file__).resolve().parent
APP = HERE.parent / "cb-studio" / "app.html"
RENDER = HERE / "cb_render.py"
_NODE = shutil.which("node")


def _app():
    return APP.read_text(encoding="utf-8")


def _artifacts():
    """ARTIFACTS as the browser would actually evaluate it — parsed by node, never by a
    regex guessing at JS. A regex would pass on a table that does not parse."""
    if not _NODE:
        pytest.skip("node is not installed")
    src = _app()
    start = src.index("const ARTIFACTS={")
    end = src.index("\n};", start) + 3
    harness = pathlib.Path("/tmp/cb_artifacts_harness.js")
    harness.write_text(src[start:end] + "\nprocess.stdout.write(JSON.stringify(ARTIFACTS));",
                       encoding="utf-8")
    out = subprocess.run([_NODE, str(harness)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, f"ARTIFACTS does not parse: {out.stderr[-800:]}"
    return json.loads(out.stdout)


def _engine_verbs():
    """Every CLI verb cb_render actually dispatches on."""
    src = RENDER.read_text(encoding="utf-8")
    tail = src[src.index("if __name__"):]
    return set(re.findall(r'cmd\s*==\s*"([a-z0-9-]+)"', tail)) | set(
        re.findall(r'^\s*"([a-z0-9-]+)"', tail, re.M))


# ── 1 · EVERY CARD IS THE SAME SHAPE ─────────────────────────────────────────────────────

def test_every_artifact_offers_the_same_four_things():
    """The whole point of the regrouping. A card that is missing `agree` or `reject` puts
    Julian back in the position he described — looking at a finished artifact with no way to
    say yes or no to THAT artifact, only to some gate above it."""
    for key, a in _artifacts().items():
        assert a.get("name"), f"{key}: no human name — the card has nothing to head it"
        assert (a.get("make") or {}).get("generate"), (
            f"{key}: no way to MAKE it — the card can only ever show an empty box")
        assert a.get("agree"), f"{key}: no AGREE — this artifact cannot be signed off on its own"
        assert a.get("reject"), f"{key}: no REJECT — the only way out would be to approve it"
        assert a.get("redo"), f"{key}: no RE-RUN — a rejected artifact would be a dead end"


def test_a_card_never_offers_a_verb_the_engine_does_not_have():
    """A button that can only ever fail. This is how 02 · OPENING FRAME shipped a Generate
    with no path to satisfy the engine behind it (2026-07-26) — the UI offered something the
    backend would refuse."""
    verbs = _engine_verbs()
    for key, a in _artifacts().items():
        for role, cmd in list((a.get("make") or {}).items()) + [
                ("agree", a.get("agree")), ("reject", a.get("reject")), ("redo", a.get("redo"))]:
            if cmd:
                assert cmd in verbs, (
                    f"{key}.{role} fires {cmd!r}, which cb_render does not implement — "
                    f"that button can only ever fail")


# ── 2 · THE ENGINE CANNOT GROW A CAPABILITY WITH NO DOOR ─────────────────────────────────

def test_every_artifact_the_engine_can_approve_has_a_card():
    """The direction that actually bit. `advance_shot` has 8 passing tests and its only
    mention in the whole Studio is a COMMENT; the cost ledger had 340 entries and no reader;
    auto-prepare was wired to a collapsed disclosure. Each time the engine grew something and
    no screen ever offered it. An `approve-X` verb with no card is that same defect."""
    carded = {c for a in _artifacts().values()
              for c in [*(a.get("make") or {}).values(), a.get("agree"), a.get("reject"), a.get("redo")] if c}
    missing = sorted(v for v in _engine_verbs()
                     if v.startswith("approve-") and v not in carded)
    assert not missing, (
        f"the engine can approve these and no card offers it: {missing} — a capability with "
        f"no door, the exact defect that hid advance_shot for a month")


def test_the_job_watcher_is_derived_from_the_same_table():
    """STAGE_JOB_CMDS used to be a second hand-written list of the same verbs. Two tables,
    one truth — this project has shipped that bug twice. It must stay derived."""
    app = _app()
    decl = app[app.index("const STAGE_JOB_CMDS="):]
    decl = decl[:decl.index("\n})();") + 6]
    assert "ARTIFACTS" in decl, (
        "STAGE_JOB_CMDS is hand-written again — it will drift from ARTIFACTS the first time "
        "one of them is edited, exactly as the chair table did")
