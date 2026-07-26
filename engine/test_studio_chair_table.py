#!/usr/bin/env python3
"""test_studio_chair_table.py — THE STUDIO SHOWS THE REAL CHAIRS (2026-07-25).

Julian moved the chairs (the Director to delivery: she stages the opening frame, directs
cadence with the Voice Director, owns the animation prompt, sits in the review) and then
asked the obvious question — "the studio pipeline now has to reflect this and we need to
test that this is now running."

It did not. The engine's table changed and the Studio kept showing the old titles, because
app.html hardcodes them client-side rather than reading the server's own roster. Worse, the
engine itself had TWO independent chair tables (cb_render._DEPARTMENT_WORKERS and
cb_departments.SKILLS/DEPARTMENTS) — re-pointing one changed nothing at all.

So this file is the binding: the labels a human reads must equal the table the code obeys.
It is a static text check on purpose — no server, no browser, no network — so it runs in
the ordinary suite and fails the moment anyone edits one side alone.

EXTENDED 2026-07-26 (UI_MUST_MATCH_THE_PROCESS.md) to bind the ROW SHAPE as well as the
labels. Binding the labels alone was not enough: every chair name on the screen was correct
while section "02 · OPENING FRAME" offered a Generate button and no way on that screen to
prepare or approve the direction the engine demands behind it — the one control it showed
could only ever refuse. See the block of tests further down. Those are still static, with one
exception clearly marked: a node harness that actually RUNS the shared prepare/approve block
in every state, because "the row calls the function" and "a human can get through the row"
are different claims. It skips where node isn't installed; it never touches the network.

    pytest test_studio_chair_table.py -q
"""
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

import pytest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cb_departments as D
import cb_render as R

APP = HERE.parent / "cb-studio" / "app.html"

# Every label retired by the restructure. A rendered occurrence of any of these means the
# Studio is telling Julian a chair holder who no longer holds that chair.
RETIRED = ("Animation Director / Camera",
           "Director Review / Continuity Supervisor")


def _app():
    return APP.read_text(encoding="utf-8")


def test_the_two_engine_chair_tables_agree_with_each_other():
    """The bug that started this: two tables, only one of which decided anything. Whatever
    else is true, they must not disagree about who holds a chair or which craft contract
    loads."""
    roster = {d["id"]: d for d in D.DEPARTMENTS}
    # animation is the one genuine transfer — the Director owns the prompt outright.
    assert R._DEPARTMENT_WORKERS["animation"][1] == "Director"
    assert R._DEPARTMENT_WORKERS["animation"][2] == "director"
    assert roster["animation"]["worker"] == "Director"
    assert roster["animation"]["skill"] == "crystal-bears-director"
    assert D.SKILLS["animation"].parent.name == "crystal-bears-director"

    # ...and the specialists keep their own craft contracts. "She sits in the review" is
    # not "she is the only one in the review": a chair move that collapsed two chairs into
    # one would satisfy every label assertion above and still be wrong.
    assert R._DEPARTMENT_WORKERS["cinematography"][2] == "cinematographer"
    assert R._DEPARTMENT_WORKERS["voice"][2] == "voice-director"
    assert R._DEPARTMENT_WORKERS["review-keyframe"][2] == "continuity"
    assert R._DEPARTMENT_WORKERS["review-animation"][2] == "continuity"


def test_the_loaded_animation_skill_is_not_the_stale_camera_document():
    """The camera SKILL.md the Director's chair displaced carried five stale markers —
    10-12s beats (retired by the 15s Handle Doctrine) and the retired FRAME CHAIN
    mechanism. Loading it would feed contradictions straight into a live prompt."""
    text = D.SKILLS["animation"].read_text(encoding="utf-8")
    stale = re.findall(r"10-12s|FRAME CHAIN", text)
    assert not stale, f"the animation chair loads a document with stale doctrine: {stale}"


def test_the_studio_never_renders_a_retired_chair_title():
    app = _app()
    for label in RETIRED:
        assert label not in app, (
            f"cb-studio/app.html still shows the retired chair title {label!r} — the Studio "
            f"is naming a holder who no longer holds that chair")


def test_every_studio_chair_label_matches_the_engine_table():
    """The real binding. For each production stage, the worker title app.html renders must
    be the one cb_render._DEPARTMENT_WORKERS actually obeys — checked by looking the exact
    engine string up in the page, so editing either side alone fails here."""
    app = _app()
    for stage in ("cinematography", "voice", "animation"):
        worker = R._DEPARTMENT_WORKERS[stage][1]
        assert worker in app, (
            f"the Studio never shows {stage}'s real worker title {worker!r} — app.html's "
            f"hardcoded chair labels have drifted from the engine's own table")


# ── THE ROW SHAPE, BOUND (2026-07-26, UI_MUST_MATCH_THE_PROCESS.md) ───────────────────────
# This file already bound the LABELS. It did not bind the SHAPE, and the shape is what broke:
# section "02 · OPENING FRAME" offered a Generate button behind an engine gate
# (_require_approved_department, stage cinematography) that nothing on that screen could
# satisfy — so the only control it showed could only ever refuse. Julian was unblocked from a
# command line. Sections 04 and 05 had each grown their own inline prepare/approve controls on
# their own day; 02 never did.
#
# The tests below fail if that can happen again: every stage the engine actually hard-gates
# must have a section that authorises it, that section must render a prepare AND an approve
# path in its own row, and no human-facing refusal may name an engine stage key.

GATE_CALL = re.compile(r"_require_approved_department\(\s*\n?\s*pkg,\s*scene,\s*[\"']([a-z-]+)[\"']")


def _engine_gated_stages():
    """The stages cb_render REALLY refuses a paid route on, read out of its own call sites.

    Deliberately parsed from the source rather than declared here: a declared list is a second
    table, and a second table is the defect this whole file exists to catch."""
    src = (HERE / "cb_render.py").read_text(encoding="utf-8")
    found = set(GATE_CALL.findall(src))
    # The two-argument form (`_require_approved_department(pkg, scene, stage, ...)` with the
    # stage in a variable) is the generic readiness check, not a stage-specific gate.
    return found


def _row_source(app, row_id):
    """One shot-panel row's own source span: from the previous row's push to its own."""
    end = app.index(f'rows.push({{id:"{row_id}"')
    prev = app.rfind("rows.push({id:", 0, end)
    start = app.rindex("// ── ", 0, prev if prev > 0 else end)
    return app[start:end]


def test_every_stage_the_engine_gates_has_a_section_that_authorises_it():
    gated = _engine_gated_stages()
    assert gated, "parsed no gate call sites out of cb_render.py — the regex has gone stale"
    for stage in sorted(gated):
        sec = D.panel_section(stage)
        assert sec, (
            f"cb_render hard-gates stage {stage!r} but no section of cb_departments.SHOT_PANEL "
            f"authorises it — a human has no place to prepare or approve it, which is exactly "
            f"how 02 · OPENING FRAME ended up with a fire button and no way to fire it")


def test_every_authorising_section_renders_prepare_and_approve_in_its_own_row():
    """The shape, not the label. Each gated section's own row must build the shared
    prepare -> read -> approve block; a Generate button with the authorisation two levels down
    inside a collapsed disclosure is what Julian actually hit."""
    app = _app()
    for stage in D.authorising_stages():
        sec = D.panel_section(stage)
        src = _row_source(app, sec["rowId"])
        assert f'panelAuthStage("{sec["rowId"]}")' in src, (
            f'section {sec["number"]} · {sec["name"]} does not ask the engine which stage '
            f'authorises it — app.html has gone back to deciding that for itself')
        assert "authBlockHTML(" in src, (
            f'section {sec["number"]} · {sec["name"]} does not render the shared '
            f'prepare/approve block — its row shape has drifted from the other gated sections')


def test_the_shared_block_offers_prepare_read_and_approve():
    """The block itself has to contain all three steps, or binding rows to it proves nothing."""
    app = _app()
    start = app.index("function authBlockHTML(")
    block = app[start:app.index("\nfunction ", start + 10)]
    assert "deptRun(" in block, "the shared block offers no way to PREPARE a direction"
    assert "shApproveStageAll(" in block, "the shared block offers no way to APPROVE a direction"
    assert "deptDecide(" in block and "rejected" in block, "the shared block offers no way to reject"
    assert "runDecideBlock(" in block, (
        "the shared block never renders the direction being approved — an Approve button over "
        "content nobody can see is the 2026-07-23 defect, restated")


def test_no_shot_panel_row_shows_a_fire_button_without_its_authorisation_path():
    """02 · OPENING FRAME, stated as its own test because it is the one that failed."""
    app = _app()
    src = _row_source(app, "frame")
    assert "openDisclosureModal('keyframe'" in src, "the opening-frame row no longer fires at all"
    assert "authBlockHTML(" in src, (
        "02 · OPENING FRAME offers a paid Generate with no prepare/approve path in the same "
        "row — the exact defect UI_MUST_MATCH_THE_PROCESS.md was written about")
    assert "deptLocksGeneration(" in src, (
        "the opening-frame Generate button is no longer wrapped in the engine's own readiness "
        "— the disabled state is the visible explanation, never the gate itself")


def test_the_studio_holds_no_stage_list_of_its_own():
    """Hardcoding is how the two sides drifted apart. The rows read the engine's table."""
    app = _app()
    for bad in ('["cinematography","voice","animation"]',
                "['cinematography','voice','animation']",
                '("cinematography","voice","animation")'):
        assert bad not in app, f"app.html has grown its own hardcoded stage list: {bad}"
    assert "function panelSection(" in app and "SH_PANEL" in app, (
        "app.html no longer reads the engine's shot-panel table")


def test_the_refusal_speaks_julians_numbers_and_names_never_an_engine_key():
    """His own correction: 'please refer to the numbers and the real stage names, stage three
    is opening frame.' These strings are not only exception text — department_readiness returns
    them as readiness.reasons.ready and the Studio prints them straight onto the row."""
    pkg = {"sceneNumber": 1,
           "shots": [{"shotId": "S1.SH1", "sourceType": "opener"}],
           "continuityLedger": [{"shotId": "S1.SH1"}]}
    for stage in D.authorising_stages():
        try:
            R._require_approved_department(pkg, 1, stage, "S1.SH1", "Ep1",
                                           action_label="this shot's own fire")
        except R.DepartmentNotApproved as e:
            msg = str(e)
        else:
            raise AssertionError(f"the gate did not refuse an unapproved {stage} — THE CORE LAW")
        assert D.panel_label(stage) in msg, (
            f"the refusal for {stage} never names the section {D.panel_label(stage)!r} the "
            f"human actually has to open")
        assert f"stage '{stage}'" not in msg, (
            f"the refusal for {stage} still names the engine's own stage key — an "
            f"implementation detail no human should have to translate")
        assert "requires an APPROVED" in msg, "the gate's own wording has moved; other suites match on it"


def test_the_readiness_reason_the_studio_prints_is_labelled_by_section():
    """department_readiness's refusal is not developer text — the Studio renders it straight
    onto the row (readiness.reasons.ready) and into the disabled Generate button's tooltip.
    Its own action label used to be f'{stage} readiness check', which put the engine's key on
    Julian's screen inside the very message telling him what to do about it. Checked here at
    the source, because building a package rich enough to run the real readiness path needs
    the full scratch world fixture — the live functional proof lives beside it, in
    test_cb_render_department_gate.py::test_the_readiness_reason_names_julians_section."""
    src = (HERE / "cb_render.py").read_text(encoding="utf-8")
    assert 'action_label=f"{stage} readiness check"' not in src, (
        "department_readiness has gone back to labelling its refusal with the engine's own "
        "stage key — that string is printed on Julian's screen")
    assert 'action_label=f"the paid step in {cb_departments.panel_label(stage)}"' in src


def test_the_http_layer_accepts_every_authorising_stage():
    """/api/shot-approve-stage was hardcoded to ('voice','animation') — the two sections that
    happened to have rows — so 02 · OPENING FRAME could not be approved from its own row even
    once the row offered to."""
    serve = (HERE.parent / "cb-studio" / "serve.py").read_text(encoding="utf-8")
    assert 'stage not in ("voice", "animation")' not in serve, (
        "the approve endpoint has gone back to a hardcoded two-stage list")
    assert "_CBD.authorising_stages()" in serve, (
        "the approve endpoint no longer reads the engine's own list of authorising stages")


def test_the_http_allowlist_still_matches_the_engine_table():
    """The third copy of the chair table, bound at last: serve.py's own DEPARTMENT_STAGES
    carried a comment admitting 'no test ties the two together yet'."""
    serve = (HERE.parent / "cb-studio" / "serve.py").read_text(encoding="utf-8")
    block = serve[serve.index("DEPARTMENT_STAGES = ("):]
    block = block[:block.index(")") + 1]
    listed = set(re.findall(r'"([a-z-]+)"', block))
    assert listed == set(R._DEPARTMENT_WORKERS), (
        f"serve.py's DEPARTMENT_STAGES and cb_render._DEPARTMENT_WORKERS disagree: "
        f"{listed ^ set(R._DEPARTMENT_WORKERS)}")


# The static tests above bind the WIRING — each gated section asks the engine which stage
# authorises it and renders the shared block. This one runs the shared block for real, in
# node, against every state a direction can be in, and proves all three sections behave
# identically. It is the difference between "the row calls the function" and "the row offers
# a human a way through". Skipped, never failed, where node isn't installed.
_NODE = shutil.which("node")

_ROW_HARNESS = r"""
const fs=require("fs"), app=fs.readFileSync(process.argv[2],"utf8");
function fn(name){const i=app.indexOf("function "+name+"(");
  if(i<0)throw new Error("not found: "+name);
  const j=app.indexOf("\nfunction ",i+10);return app.slice(i,j<0?app.length:j);}
const src=["panelSection","rowHeading","panelAuthStage","panelLabelForStage","authBlockHTML"].map(fn).join("\n");
const _esc=s=>String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const runDecideBlock=(h,i)=>`<DECIDE>${i}</DECIDE>`, rowMore=(i,k)=>i?`<MORE>${i}</MORE>`:"";
const deptKey=(st,sid)=>"K|"+st+"|"+sid;
let SH_DEPT_CACHE={},SH_DEPT_LAST={};
const shDeptRec=(st,sid)=>{const k=deptKey(st,sid),d=SH_DEPT_CACHE[k];
  return (d&&!d.loading&&!d.error)?d:(SH_DEPT_LAST[k]||d||null);};
let SH_PANEL=JSON.parse(process.argv[3]);
eval(src);
const SHOT="S1.SH1"; let fails=[];
const must=(c,m)=>{if(!c)fails.push(m);};
function set(st,rec){SH_DEPT_CACHE[deptKey(st,SHOT)]=rec;
  if(rec&&!rec.loading&&!rec.error)SH_DEPT_LAST[deptKey(st,SHOT)]=rec;}
for(const row of SH_PANEL.filter(s=>s.authorises&&s.stage)){
  const stage=row.stage, tag=row.number+" · "+row.name;
  must(panelAuthStage(row.rowId)===stage, tag+": row does not resolve to its engine stage");
  const out=o=>stage==="voice"?{lines:[{speaker:"F",performedText:o}]}:{providerPrompt:o};
  set(stage,{worker:"W",readiness:{readyForDisclosure:false,prepared:false,directionCurrent:false}});
  let b=authBlockHTML(stage,SHOT), a=()=>b.actions.join("");
  must(b.phase==="prepare",tag+": nothing prepared should offer PREPARE, got "+b.phase);
  must(a().includes("deptRun("),tag+": NO PREPARE BUTTON with nothing prepared — the original 02 defect");
  must(!a().includes("shApproveStageAll("),tag+": offers Approve over content that does not exist");
  set(stage,{worker:"W",candidate:{output:out("THE TEXT")},
    readiness:{readyForDisclosure:false,prepared:true,directionCurrent:false}});
  b=authBlockHTML(stage,SHOT);
  must(b.phase==="approve",tag+": a pending candidate should be approvable, got "+b.phase);
  must(a().includes("shApproveStageAll("),tag+": NO APPROVE BUTTON over a pending candidate");
  must(b.body.includes("THE TEXT"),tag+": the direction being approved is not on screen");
  set(stage,{worker:"W",approved:{output:out("APPROVED")},
    readiness:{readyForDisclosure:true,prepared:true,directionCurrent:true,approvalCurrent:true}});
  b=authBlockHTML(stage,SHOT);
  must(b.phase==="approved"&&b.ready===true,tag+": an approved+current direction reads as "+b.phase);
  set(stage,{worker:"W",approved:{output:out("OLD")},
    readiness:{readyForDisclosure:false,prepared:true,directionCurrent:false,reasons:{ready:"BECAUSE X"}}});
  b=authBlockHTML(stage,SHOT);
  must(b.phase==="stale",tag+": a stale approval reads as "+b.phase);
  must(b.body.includes("BECAUSE X"),tag+": the stale reason is not shown");
  must(a().includes("deptRun("),tag+": a stale approval offers no way to re-prepare");
  SH_DEPT_CACHE={};SH_DEPT_LAST={};
}
console.log(JSON.stringify(fails));
"""


@pytest.mark.skipif(_NODE is None, reason="node not installed")
def test_the_shared_block_behaves_identically_for_every_gated_section():
    harness = pathlib.Path(tempfile.gettempdir()) / "cb_rowshape_harness.js"
    harness.write_text(_ROW_HARNESS, encoding="utf-8")
    out = subprocess.run([_NODE, str(harness), str(APP), json.dumps(D.SHOT_PANEL)],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, f"harness crashed: {out.stderr[-1500:]}"
    fails = json.loads(out.stdout.strip().splitlines()[-1])
    assert not fails, "the gated sections no longer share one row shape:\n  " + "\n  ".join(fails)


def test_base_url_follows_the_page_origin():
    """Not a chair, but the same class of defect and it lands on the same screen: BASE was
    pinned to localhost while the studio was browsed at 127.0.0.1, so every fetch tripped
    CORS and the UI reported 'Can't reach the studio server' over a page that had loaded
    its data fine."""
    app = _app()
    assert 'const BASE="http://localhost:8765";' not in app, (
        "BASE is hardcoded to localhost again — browsing on 127.0.0.1 will break every call")
    assert "location.origin" in app


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
