#!/usr/bin/env python3
"""test_studio_recoverability.py — "I CAN'T GO BACK", and the two other places the Studio
computed the way back and then hid it.

Three findings from the 2026-07-26 UX assessment, all the same shape as its root finding —
the answer already existed and no screen carried it:

  · NAVIGATION. Measured on 2026-07-26: `pushState` × 0, `popstate` × 0, `replaceState` × 1.
    Every screen replaced the same single history entry, so the browser Back button, Cmd-[ and
    the trackpad back-swipe all LEFT the Studio. The URL already carried the whole context and
    `_restoreFromHash` already knew how to replay it; nothing ever pushed an entry for it to
    return to.
  · UN-APPROVE. `cb_render.unapprove_keyframe` / `unapprove_voice` / `unapprove_shot` have
    existed since 2026-07-25 and have been reachable at the HTTP boundary that whole time
    (serve.py's SHOT_CMDS). Their only buttons lived inside `renderShotStage`, which nothing
    had called since 2026-07-23 — so from an approved opening frame the only route backwards
    was to spend money on a new candidate. Un-approving is free; it must never be the harder
    door.
  · BEATS. `sceneContentsHTML` was a beat-grouped scene view written on 2026-07-22 in direct
    answer to Julian's own note ("i thought it was strange we had the opening shot then the
    storm") and orphaned the next day by a flat filmstrip. He works "S1.SH4 of 10" with no
    view of which of the scene's four beats it serves.

Static text checks by default — the same convention test_studio_chair_table.py and
test_studio_computed_truth.py already established, so this runs in the ordinary suite with no
server, no browser and no provider call. The one exception is clearly marked and runs the real
grouping function in node against a fixture, because "the function exists" and "it files every
shot exactly once" are different claims.

    pytest test_studio_recoverability.py -q
"""
import inspect
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile

import pytest

import cb_render as R

HERE = pathlib.Path(__file__).resolve().parent
APP = HERE.parent / "cb-studio" / "app.html"
STUDIO = HERE.parent / "cb-studio"


def _app():
    return APP.read_text(encoding="utf-8")


def _app_code():
    """app.html with its `//` line comments stripped. Every string these tests hunt for is also
    QUOTED IN THE COMMENT that explains why it is there, so a naive search finds its own
    documentation and passes on nothing."""
    return "\n".join(l for l in _app().splitlines() if not l.lstrip().startswith("//"))


def _fn_body(name, src=None):
    """The source of one top-level `function name(...)` in app.html, to its closing brace."""
    src = src if src is not None else _app_code()
    m = re.search(r"^(?:async )?function %s\(" % re.escape(name), src, re.M)
    assert m, f"{name} is not defined in app.html"
    i = m.start()
    depth, started, j = 0, False, i
    while j < len(src):
        if src[j] == "{":
            depth += 1
            started = True
        elif src[j] == "}":
            depth -= 1
            if started and depth == 0:
                return src[i:j + 1]
        j += 1
    raise AssertionError(f"{name} never closes")


# ── 1 · REAL HISTORY ─────────────────────────────────────────────────────────────────────

def test_navigation_pushes_a_history_entry():
    """The measured defect: replaceState × 1 and nothing else. A single entry that every screen
    overwrites is not history — it is one screen wearing a URL."""
    a = _app_code()
    assert "history.pushState(" in a, (
        "no navigation pushes a history entry — Back still leaves the Studio")
    assert 'window.addEventListener("popstate"' in a, (
        "nothing listens for Back/forward, so a pushed entry would change the URL and not "
        "the screen")


def test_back_replays_through_the_same_restorer_a_refresh_uses():
    """`_restoreFromHash` has existed since 2026-07-17 and is exercised on every refresh. Back
    must go through it, not through a second, differently-behaving path that can drift."""
    handler = _app_code()
    i = handler.index('window.addEventListener("popstate"')
    handler = handler[i:i + 900]
    assert "_restoreFromHash(" in handler, (
        "the popstate handler does not use the restorer a refresh already uses")


def test_a_repaint_never_grows_the_history():
    """The Studio re-renders constantly — a poll tick, a lazily-loaded department record, a
    job-status refresh. If every repaint pushed, Back would stop meaning 'the previous screen'
    and start meaning 'one of the last forty repaints'. The push must be conditional on the
    place ACTUALLY changing, and the unchanged case must still replace."""
    body = _fn_body("_syncHash")
    assert "history.replaceState(" in body, (
        "_syncHash no longer replaces for a same-place render — every repaint now pushes")
    push = re.search(r"if\s*\(([^)]*)\)\s*history\.pushState\(", body)
    assert push, "the pushState call is not guarded by a condition at all"
    cond = push.group(1)
    assert "!==" in cond or "!=" in cond, (
        f"the push guard does not compare the new place against the last one: {cond!r}")


def test_the_scene_pipe_node_is_carried_in_the_url():
    """PPIPE is what the scene screen is actually showing. It was the one piece of in-scene
    position the hash never carried, so clicking along the pipe changed the screen and left the
    URL identical — nothing to refresh back to, and nothing for Back to return to."""
    nav = _fn_body("_navHash")
    assert "PPIPE" in nav, "the pipe node is still missing from the URL"
    restore = _fn_body("_restoreFromHash")
    assert "'pipe'" in restore or '"pipe"' in restore, (
        "the pipe node is written to the URL and never read back out of it")


def test_restoring_does_not_push_the_history_it_is_walking():
    """A restore re-renders half the app; each of those renders calls _syncHash. Without a guard
    the act of going Back would push new entries on top of the ones it is walking through."""
    restore = _fn_body("_restoreFromHash")
    sync = _fn_body("_syncHash")
    assert re.search(r"_NAV_RESTORING\s*=\s*true", restore), (
        "_restoreFromHash never raises the guard, so going Back pushes new entries on top of "
        "the ones it is walking through")
    assert re.search(r"_NAV_RESTORING\s*=\s*false", restore), (
        "_restoreFromHash never lowers the guard — after one Back, nothing would push again")
    push = re.search(r"if\s*\(([^)]*)\)\s*history\.pushState\(", sync)
    assert push and "_NAV_RESTORING" in push.group(1), (
        "the push guard does not consult the restore flag")


def test_back_onto_the_front_door_is_not_a_dead_end():
    """Found 2026-07-26 by the verification pass, in the navigation fix itself.

    Walking Back onto the bare URL lands on Projects — and bootProjects() renders, and every
    render calls _syncHash, and _syncHash PUSHES when the hash changed. So the act of arriving
    pushed "pg=projects" straight back on, returning you to the entry you had just left. Back
    on the Studio's own front door did nothing, forever: measured idx=1/1 before this fix, on
    every press. That is strictly worse than the behaviour being replaced — Back used to leave
    the app; briefly, it did nothing at all.

    The branch must therefore RAISE the restore guard, not lower it, and must hold it across
    the whole async boot — bootProjects awaits a fetch before it renders, so raising the flag
    and returning immediately would clear it before the render that needs it ever runs."""
    code = _app_code()
    handler = re.search(r'addEventListener\(\s*["\']popstate["\'][\s\S]*?\n\}\);', code)
    assert handler, "the popstate handler is gone"
    branch = re.search(r"if\s*\(\s*!h\s*\|\|[\s\S]*?\n\s*\}", handler.group(0))
    assert branch, "the no-project branch of the popstate handler is gone"
    body = branch.group(0)

    assert not re.search(r"_NAV_RESTORING\s*=\s*false", body), (
        "arriving at the front door lowers the restore guard, so the render it triggers pushes "
        "the entry back on and Back becomes a permanent no-op")
    assert re.search(r"_NAV_RESTORING\s*=\s*true", body) or "_bootProjectsRestoring" in body, (
        "the front-door branch neither raises the guard nor delegates to something that does")

    helper = _fn_body("_bootProjectsRestoring")
    assert re.search(r"_NAV_RESTORING\s*=\s*true", helper), "the helper never raises the guard"
    assert ".finally(" in helper or ".then(" in helper, (
        "the helper lowers the guard synchronously — bootProjects awaits a fetch before it "
        "renders, so the flag would be gone by the time the render needs it")
    assert "_NAV_SEQ" in helper, (
        "nothing stops an older boot clearing a newer Back press's guard out from under it")


# ── 2 · THE UN-APPROVE CONTROLS, REACHABLE ───────────────────────────────────────────────

def _shot_run_cmds():
    """serve.py's own allowlist for the /api/shot-run route — the verbs the shot panel can
    actually send."""
    serve = (STUDIO / "serve.py").read_text(encoding="utf-8")
    block = serve[serve.index("SHOT_CMDS = ("):]
    block = block[:block.index("\n\n")]
    return set(re.findall(r'"([a-z-]+)"', block))


def _shot_unapprove_commands():
    """The shot-level un-approve verbs, derived from TWO independent sources and never typed
    here: a verb the shot-run route accepts, whose cb_render function takes a shot_id. The
    signature is what separates them — unapprove_scenelook is scene-level (no shot_id, its
    control lives on the Scene Look screen) and unapprove_department is not a shot-run verb at
    all (it has its own endpoint and its own panel). Both exclusions are read off the code
    rather than asserted."""
    out = []
    for cmd in _shot_run_cmds():
        if not cmd.startswith("unapprove-"):
            continue
        fn = getattr(R, cmd.replace("-", "_"), None)
        if not callable(fn):
            continue
        try:
            params = inspect.signature(fn).parameters
        except (TypeError, ValueError):
            continue
        if "shot_id" in params:
            out.append(cmd)
    assert out, "no shot-level un-approve is reachable at all — re-check this binding"
    return sorted(out)


def test_every_shot_level_un_approve_the_engine_exposes_has_a_button():
    """The finding, bound: three engine controls, reachable over HTTP, with no reachable button.
    Asserted against the LIVE panel — renderShotRunner — because a control inside a function
    nothing calls is exactly the defect."""
    runner = _fn_body("renderShotRunner")
    for cmd in _shot_unapprove_commands():
        assert f"'{cmd}'" in runner, (
            f"the engine exposes {cmd} for a shot and the live panel offers no way to reach "
            f"it — the only route backwards is a paid one")


def test_the_engine_still_backs_every_verb_the_studio_can_send():
    """The other direction: every un-approve verb the shot-run route accepts must resolve to a
    real cb_render function, or a button reaches the server and dies there."""
    for cmd in sorted(c for c in _shot_run_cmds() if c.startswith("unapprove-")):
        assert callable(getattr(R, cmd.replace("-", "_"), None)), (
            f"serve.py accepts {cmd} and cb_render has no function for it")


def test_the_free_way_back_sits_in_the_same_row_as_the_paid_one():
    """"Never hidden behind a paid action" is a claim about REACHABILITY, and in this panel a
    settled row collapses — so a control is only as reachable as the row it lives in. The
    binding that means something: for the approved opening frame, un-approve and the paid
    Generate are built into the SAME actions list, so opening that row reveals both or
    neither. A future edit that moves un-approve one caret deeper than Generate fails here."""
    runner = _fn_body("renderShotRunner")
    i = runner.index('unapproveBtn(\'unapprove-keyframe\'')
    acts = runner[runner.rindex("acts=[", 0, i):runner.index("]", i) + 1]
    assert "genBtn" in acts, (
        "the free un-approve and the paid Generate are no longer in the same row's controls")
    assert acts.index("unapproveBtn") < acts.index("genBtn"), (
        "the paid control is offered before the free one")


def test_a_settled_row_says_out_loud_that_the_way_back_is_free():
    """A collapsed row shows only its summary. "Approved" on its own reads as final, and that
    is the whole reason the existing controls went unnoticed for three days."""
    runner = _fn_body("renderShotRunner")
    for anchor in ('sum="Opening frame approved', 'sum="Take approved"'):
        i = runner.index(anchor)
        line = runner[i:runner.index("\n", i)]
        assert "free" in line, f"a settled row's summary never mentions the free way back: {line!r}"


def test_un_approving_is_never_presented_as_a_spend():
    """It costs nothing and deletes nothing. A control that is free must SAY it is free, and
    must never wear the class this file reserves for buttons that spend."""
    a = _app_code()
    btn = _fn_body("unapproveBtn")
    assert "btn spend" not in btn, "the un-approve control is styled as a spending control"
    assert "free" in btn.lower(), "the un-approve control does not say that it is free"
    # and no un-approve anywhere in the file is wired to a paid disclosure modal
    for m in re.finditer(r"<button[^>]*onclick=\"[^\"]*unapprove[^\"]*\"[^>]*>", a):
        assert "openDisclosureModal" not in m.group(0), (
            "an un-approve button opens the spend disclosure — un-approving never spends")


def test_a_landed_shot_still_has_the_free_way_back():
    """When the take is approved the panel deliberately quiets every row (the terminality pass).
    It must not quiet the one reversible control, or an approved shot's single remaining exit is
    the paid one."""
    runner = _fn_body("renderShotRunner")
    i = runner.index('if(r.id=="review"){')
    block = runner[i:i + 900]
    assert "unapprove-shot" in block, (
        "the terminality pass leaves an approved shot with only the paid way out")


# ── 3 · THE BEATS, IN THE VIEW WHERE HE WORKS ────────────────────────────────────────────

def test_the_filmstrip_groups_by_beat():
    a = _app_code()
    assert "function shBeatGroups(" in a, "no beat grouping exists for the strip"
    strip = _fn_body("filmstripHTML")
    assert "shBeatGroups(" in strip, (
        "shBeatGroups is defined and the filmstrip never calls it — the exact way the first "
        "beat-grouped view was lost")
    assert "fbeat" in strip, "the strip renders no beat header of any kind"


def test_the_beats_come_from_the_storyboard_never_from_a_list_in_the_ui():
    """Same rule the shot panel already lives under. A beat list typed into app.html silently
    stops matching the moment the creative room writes a different one."""
    groups = _fn_body("shBeatGroups")
    assert "PSB.beats" in groups, "the grouping does not read the storyboard's own beats"
    assert "beatIds" in groups, (
        "the grouping does not read the storyboard's own shot-to-beat filing")
    assert not re.search(r"[\"']\d+\.B\d+[\"']", groups), (
        "a beat id has been typed into the UI — the storyboard's own beats are the only source")


def test_a_scene_with_no_beats_still_gets_its_strip():
    """The grouping is an addition, never a precondition. A storyboard carrying no beats must
    fall back to the flat strip rather than rendering nothing."""
    groups = _fn_body("shBeatGroups")
    assert "return null" in groups, "no fallback when the storyboard carries no beats"
    strip = _fn_body("filmstripHTML")
    assert re.search(r"if\(!bg\)", strip), (
        "filmstripHTML does not handle the no-beats case the grouping returns")


_NODE = shutil.which("node")

_BEAT_HARNESS = r"""
const fs=require("fs"), app=fs.readFileSync(process.argv[2],"utf8");
function fn(name){const i=app.indexOf("function "+name+"(");
  if(i<0)throw new Error("not found: "+name);
  const j=app.indexOf("\nfunction ",i+10);return app.slice(i,j<0?app.length:j);}
const src=["pShots","shAllShotOrder","shBeatGroups"].map(fn).join("\n");
let PSB=null, SH_PKG=null;
eval(src);
const F=JSON.parse(process.argv[3]);
PSB=F.storyboard; SH_PKG=F.pkg;
const order=shAllShotOrder();
const bg=shBeatGroups(order);
const out={order:order.map(o=>o.shotId)};
if(bg===null){ out.grouped=false; }
else {
  out.grouped=true;
  out.groups=bg.groups.map(g=>({beat:g.beat.beatId, shots:g.items.map(i=>i.o.shotId),
                                 also:g.items.map(i=>i.alsoIn)}));
  out.unfiled=bg.unfiled.map(i=>i.o.shotId);
}
console.log(JSON.stringify(out));
"""


def _group(fixture):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(_BEAT_HARNESS)
        path = f.name
    try:
        r = subprocess.run(["node", path, str(APP), json.dumps(fixture)],
                           capture_output=True, text=True, timeout=30)
        assert r.returncode == 0, f"node exited {r.returncode}: {r.stderr[-2000:]}"
        return json.loads(r.stdout.strip().splitlines()[-1])
    finally:
        os.unlink(path)


@pytest.mark.skipif(not _NODE, reason="node is not installed")
def test_the_real_grouping_files_every_shot_exactly_once():
    """Executed for real, not read. Two failure modes matter and only one of them is obvious:
    a shot that falls out of the strip entirely, and a shot that appears TWICE — which the
    original beat view actually did for a shot spanning two beats, and which in a filmstrip
    reads as two shots rather than one."""
    fixture = {
        "storyboard": {
            "beats": [{"beatId": "1.B1"}, {"beatId": "1.B2"}, {"beatId": "1.B3"}],
            "shots": [
                {"shotId": "S1.SH1", "beatIds": ["1.B1"]},
                {"shotId": "S1.SH2", "beatIds": ["1.B1", "1.B2"]},   # spans two beats
                {"shotId": "S1.SH3", "beatIds": ["1.B2"]},
                {"shotId": "S1.SH4", "beatIds": ["9.B9"]},           # names a beat that isn't here
                {"shotId": "S1.SH5"},                                # names no beat at all
            ],
        },
        "pkg": {"shots": [{"shotId": "S1.SH1"}, {"shotId": "S1.SH3"}]},
    }
    out = _group(fixture)
    assert out["grouped"] is True
    placed = [s for g in out["groups"] for s in g["shots"]] + out["unfiled"]
    assert sorted(placed) == sorted(out["order"]), (
        f"the strip lost or invented a shot: filed {sorted(placed)} vs {sorted(out['order'])}")
    assert len(placed) == len(set(placed)), f"a shot is filed twice: {placed}"
    by_beat = {g["beat"]: g["shots"] for g in out["groups"]}
    assert by_beat["1.B1"] == ["S1.SH1", "S1.SH2"], by_beat
    assert by_beat["1.B2"] == ["S1.SH3"], by_beat
    assert by_beat["1.B3"] == [], "a beat with no shots must still appear, not vanish"
    assert sorted(out["unfiled"]) == ["S1.SH4", "S1.SH5"], (
        "a shot naming no beat this storyboard knows must be SHOWN, never dropped")
    # the second beat a shot serves is stated rather than silently lost
    also = [a for g in out["groups"] for a in g["also"]]
    assert ["1.B2"] in also, "a shot spanning two beats no longer names the second one"


@pytest.mark.skipif(not _NODE, reason="node is not installed")
def test_the_real_grouping_falls_back_when_the_storyboard_has_no_beats():
    out = _group({"storyboard": {"shots": [{"shotId": "S1.SH1"}]}, "pkg": {"shots": []}})
    assert out["grouped"] is False, (
        "a storyboard with no beats must fall through to the flat strip, not group on nothing")


# ── 4 · THE DEAD CODE IS ACTUALLY GONE ───────────────────────────────────────────────────

DELETED = ["renderShotStage", "renderStageRail", "sceneContentsHTML",
           "sceneContentsShotLabel", "productionWorkflowHTML"]


def test_the_dead_view_functions_are_deleted_not_merely_unreferenced():
    """Two of these held controls the panel needed (the three un-approve buttons, the beat
    grouping) and nobody noticed for days, because a function nobody calls has nothing to
    notice. They were harvested and removed on 2026-07-26; this refuses their return as
    defined-and-dead."""
    a = _app()
    for name in DELETED:
        assert not re.search(r"^(?:async )?function %s\(" % name, a, re.M), (
            f"{name} is defined again — if it is live, call it; if it is not, delete it")


def test_the_css_those_views_alone_used_went_with_them():
    a = _app()
    for cls in (".prail", ".pstage{", ".pstagehead", ".pwtrack", ".pwstep", ".wtree-",
                ".pshotnav"):
        assert cls not in a, f"{cls} is styling nothing — its only view was deleted"


def test_no_sedimentary_copies_of_the_interface_sit_beside_it():
    """Ten .bak files were how four vocabularies came to exist in the first place. They are in
    git history now (commit 'the .bak snapshots, into git before they leave the tree'); the
    working tree holds one interface."""
    stray = sorted(p.name for p in STUDIO.glob("*.bak*"))
    assert not stray, f"backup copies of the interface are back in the tree: {stray}"
