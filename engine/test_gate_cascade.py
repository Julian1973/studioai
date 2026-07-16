#!/usr/bin/env python3
"""test_gate_cascade.py — the cascade assertion (BUG fix, 2026-07-02, Julian).

A Gate-1 deliverable change must automatically relock every downstream sign-off — the studio was caught showing a
scene's Gate 2 as "signed off" after a Scene-1 restructure (4 beats -> 5) that happened entirely outside any gate
UI action. Fixed with a lazy content-hash check (cb_pipeline._scene_beats_fingerprint / _relock_if_stale, mirrored
in cb-studio/serve.py's locked_state() since it is a separate process with no engine import). This script proves
BOTH copies actually cascade-clear on a Gate-1 change, using SCRATCH files only — it never touches the real
locked.json or any real beat package, so it is safe to run any time, including in CI.

    python3 test_gate_cascade.py     # exit 0 = both implementations pass; exit 1 = a regression was caught
"""
import os, sys, json, ast, tempfile, shutil, hashlib, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
SERVE_PY = os.path.join(os.path.dirname(HERE), "cb-studio", "serve.py")


def _scratch_scenes(scene_num=9):
    """THE MANIFEST (CLAUDE.md rule 37, 2026-07-06; sceneLook added rule 53, 2026-07-08): a manifest-compliant
    scratch scene entry — cb_pipeline.approve now gates on manifest_ok, so every scratch package this test
    fires approve() against needs one of these. pillar='heart' is a scratch shortcut, not a real story call —
    it trivially exempts this scene from the "laugh beat per non-Heart pillar" check, which has nothing to do
    with what THIS test actually verifies (cascade-relock mechanics), so there's no reason to also give the
    scratch beats a comedyMode. performanceThroughline is NOT set here (rule 58, 2026-07-08) — it is derived
    automatically from the scene's own beats' fidelityAllocation, never a hand-authored fixture value.
    time/weather ADDED 2026-07-15 (guardrail-fidelity audit, THE CONTEXT GATE): the SAME "test fixtures drift
    whenever a new gate/field starts being enforced" pattern rule 46 already documents — cb_context.check()'s
    own scene-completeness check ("scene missing time/weather") has always existed but was never wired into
    approve() until now, so this scratch scene never needed these fields before; now it does."""
    return [{"sceneNumber": scene_num, "ambientBed": "scratch test ambient bed — not real content",
             "parentLine": "scratch test parent-layer line — not real content",
             "sceneLook": "scratch test scene-look line — not real content",
             "time": "scratch test time of day", "weather": "scratch test weather",
             "pillar": "heart"}]


def _scratch_package(path, beats, scenes=None):
    json.dump({"beats": beats, "scenes": scenes if scenes is not None else _scratch_scenes()}, open(path, "w"))


def _sync_scratch_scene_cache(episode, scene_num, scene_dict):
    """FIXED 2026-07-06 (found live during THE DEFINITIVE BUILD's own dry-walk sweep): cb_preflight's scene-
    cache-sync check used to shell out to a wrongly-pathed script and silently never fire (rule 39's sibling
    fix in cb_preflight.py) — this test's approve() calls passed for months without ever actually exercising
    a real scene-cache check. Now that the check is wired correctly (cb_prompts.scene_cache_stale), a scratch
    episode/scene with no config/locations.json entry at all correctly BLOCKs — exactly as it should for a
    real, never-synced scene. This helper keeps the scratch scene in sync the same way tools/sync_scenes.py
    keeps a real one in sync, so this test still isolates CASCADE-RELOCK mechanics (its actual subject),
    never re-testing scene-cache sync (a different, already-covered concern)."""
    import cb_prompts
    # FIXED 2026-07-15 (guardrail-fidelity audit, THE CONTEXT GATE): used to write ONLY `_sourceHash` — but
    # cb_context.check() (now wired into approve(), see _scratch_scenes' own dated note) reads scene_cfg()'s
    # own time/weather fields directly from THIS cache dict, not from the beat-package scene_dict passed in
    # here. Now mirrors the real sync (SCENE_SYNC_FIELDS), matching what tools/sync_scenes.py actually copies
    # for a real scene, so a scratch scene's own time/weather genuinely reaches the check that reads it.
    entry = {k: scene_dict.get(k) for k in cb_prompts.SCENE_SYNC_FIELDS}
    entry["_sourceHash"] = cb_prompts._scene_source_hash(scene_dict)
    cb_prompts.LOCATIONS.setdefault(episode, {})[str(scene_num)] = entry


def _manifest_compliant_beat(code, scene_num, story_beat, is_opener=True):
    """THE MANIFEST (rule 37): fills every field cb_preflight's TECHNICAL/CREATIVE contracts require, so a
    scratch beat used ONLY to exercise the cascade-relock logic doesn't ALSO fail the (unrelated) content gate
    cb_pipeline.approve now enforces. Values are deliberately synthetic/scratch, never real creative content —
    this test's own assertions are about relock behaviour, not about these values meaning anything."""
    b = {
        "beatCode": code, "sceneNumber": scene_num, "storyBeat": story_beat,
        "endState": "scratch endState — not real content", "endStateStill": "scratch endStateStill",
        "carryMarks": "scratch carry marks", "pauseHold": "one hold only: under 1 second",
        "actingContrast": "scratch acting contrast", "humourLayer": 1, "kidRead": "scratch kid read",
        "adultRead": "scratch adult read", "want": "scratch want", "need": "scratch need",
        "emotionMechanic": "scratch emotion-as-mechanic statement",
        # THE FIDELITY-ALLOCATION LAW (rule 46/49, 2026-07-07) — required by check_beat_creative; added
        # 2026-07-08 (rule 53's contradiction sweep) after this fixture was found still missing it,
        # independently crashing the same approve() calls sceneLook's own gap did.
        "fidelityAllocation": {"primary": "Scratch", "secondary": "none", "economized": "none"},
    }
    if not is_opener:
        b["junctionType"] = "intentional_next_shot"
        b["opensOn"] = {"who": "Scratch", "action": "doing a scratch thing"}
    return b


def _base_beats():
    return [
        _manifest_compliant_beat("9.B1", 9, "original content", is_opener=True),
        _manifest_compliant_beat("9.B2", 9, "original content 2", is_opener=False),
    ]


def test_cb_pipeline(tmp):
    """Exercise the REAL cb_pipeline.py functions (imported directly — this is production code, not a copy)."""
    fails = []
    spec = importlib.util.spec_from_file_location("cb_pipeline_test", os.path.join(HERE, "cb_pipeline.py"))
    P = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(P)

    pkg = os.path.join(tmp, "Ep9_Test_beat_package.json")
    _scratch_package(pkg, _base_beats())
    P.PKG, P.LOCK, P.EP = pkg, os.path.join(tmp, "locked.json"), "Ep9"
    _sync_scratch_scene_cache("Ep9", 9, _scratch_scenes()[0])

    P.approve("1", "9"); P.approve("1.6", "9"); P.approve("2a", "9"); P.approve("2b", "9"); P.approve("3", "9")
    d = P._lock()
    d["Ep9"]["9"]["beats"] = {"9.B1": {"audio": True, "keyframe": True, "clip": True}}
    P._save(d)

    if not P._approved("9", "3"):
        fails.append("cb_pipeline: gate 3 should read approved before any beat-package change")

    # the Gate-1 deliverable changes — a beat is added, exactly like the Scene-1 restructure
    beats = _base_beats(); beats.append(_manifest_compliant_beat("9.B3", 9, "added by a restructure", is_opener=False))
    _scratch_package(pkg, beats)

    if P._approved("9", "3"):
        fails.append("cb_pipeline: gate 3 should auto-relock (read False) after the Gate-1 deliverable changed")
    sd = P._lock().get("Ep9", {}).get("9", {})
    for g in ("1", "1.6", "2a", "2b", "3"):
        if sd.get(g):
            fails.append(f"cb_pipeline: gate {g!r} should have been cascade-cleared, still {sd.get(g)!r}")
    if sd.get("beats"):
        fails.append(f"cb_pipeline: per-beat locks should have been cleared, still {sd.get('beats')!r}")
    if sd.get("1_fp"):
        fails.append("cb_pipeline: the stale fingerprint baseline should have been dropped too")

    # re-approving stamps a FRESH baseline that matches the NEW content, and gate 3 reads clean again once re-approved
    P.approve("1", "9"); P.approve("1.6", "9"); P.approve("2a", "9"); P.approve("2b", "9"); P.approve("3", "9")
    if not P._approved("9", "3"):
        fails.append("cb_pipeline: re-approving after the change should read approved again")
    return fails


def test_frame_chain_cascade(tmp):
    """FRAME CHAIN doctrine (2026-07-02, Julian; frame source updated 2026-07-03 — THE HARVEST, "ending frames
    are harvested, never composed"): a retake upstream (a new HARVESTED SETTLE FRAME) must mark every downstream
    beat's keyframe/clip dirty. Exercises the real cb_pipeline functions with a scratch package + scratch media/
    settle-frame files (arbitrary bytes — _beat_end_frame_hash only hashes bytes, it never decodes the PNG)."""
    fails = []
    spec = importlib.util.spec_from_file_location("cb_pipeline_test2", os.path.join(HERE, "cb_pipeline.py"))
    P = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(P)

    pkg = os.path.join(tmp, "Ep9_Chain_beat_package.json")
    beats = [
        _manifest_compliant_beat("9.B1", 9, "anchor", is_opener=True),
        _manifest_compliant_beat("9.B2", 9, "continuation one", is_opener=False),
        _manifest_compliant_beat("9.B3", 9, "continuation two", is_opener=False),
    ]
    for b, slug in zip(beats, ("b1", "b2", "b3")):
        b["slug"] = slug
    _scratch_package(pkg, beats)
    P.PKG, P.LOCK, P.EP = pkg, os.path.join(tmp, "locked_chain.json"), "Ep9"
    _sync_scratch_scene_cache("Ep9", 9, _scratch_scenes()[0])

    cwd = os.getcwd()
    media = os.path.join(tmp, "media"); os.makedirs(media, exist_ok=True)
    os.chdir(tmp)
    try:
        # 9.B1's harvested settle frame (what 9.B2 chained off) + 9.B2's (what 9.B3 chained off)
        open("media/Ep9_9.B1_b1_settle.png", "wb").write(b"settle-frame-v1")
        open("media/Ep9_9.B2_b2_settle.png", "wb").write(b"settle-frame-v1")

        # FIXED 2026-07-08 (independent-review find, approve()'s new GATE_SEQ order-check): this test used to
        # skip signing "1.6" before "2a" — harmless before approve() itself enforced gate order, but the new
        # order-check (matching fire()'s own pre-existing behaviour) would refuse approve("2a", "9") here since
        # "1.6" is 2a's immediate predecessor. Matches the sequence the other two approve() call sites in this
        # same file already use (test_cb_pipeline, test_serve_py).
        P.approve("1", "9"); P.approve("1.6", "9"); P.approve("2a", "9")
        for code in ("9.B1", "9.B2", "9.B3"):
            P._set_beat_lock("9", code, "keyframe", True)
            P._set_beat_lock("9", code, "clip", True)
        P.record_chain_source("9", "9.B2")   # stamps against 9.B1's CURRENT settle-frame hash
        P.record_chain_source("9", "9.B3")   # stamps against 9.B2's CURRENT settle-frame hash

        if P._relock_chain_if_dirty("9"):
            fails.append("frame chain: should NOT be dirty yet — nothing has changed")
        lk = P._lock().get("Ep9", {}).get("9", {}).get("beats", {})
        for code in ("9.B2", "9.B3"):
            if not lk.get(code, {}).get("keyframe"):
                fails.append(f"frame chain: {code} keyframe should still read locked before any retake")

        # a retake on 9.B1 harvests a NEW settle frame — everything chained through it is now stale
        open("media/Ep9_9.B1_b1_settle.png", "wb").write(b"settle-frame-v2-AFTER-A-RETAKE")

        if not P._relock_chain_if_dirty("9"):
            fails.append("frame chain: should detect 9.B1's changed ending frame and cascade-clear downstream")
        lk = P._lock().get("Ep9", {}).get("9", {}).get("beats", {})
        for code in ("9.B2", "9.B3"):
            bl = lk.get(code, {})
            if bl.get("keyframe") or bl.get("clip"):
                fails.append(f"frame chain: {code} keyframe/clip should have been cleared (built from the stale chain), still {bl!r}")
        if not lk.get("9.B1", {}).get("keyframe"):
            fails.append("frame chain: 9.B1 itself is upstream of the change, not downstream — its own lock must NOT be touched")
    finally:
        os.chdir(cwd)
    return fails


def _extract_functions(src_path, names):
    """Pull just the named top-level function defs out of a source file via ast (not a full import) — serve.py
    binds a live socket at module level with no __main__ guard, so it can't be imported directly in a test."""
    src = open(src_path, encoding="utf-8").read()
    tree = ast.parse(src, filename=src_path)
    wanted = {n: None for n in names}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in wanted:
            wanted[node.name] = ast.get_source_segment(src, node)
    missing = [n for n, v in wanted.items() if v is None]
    if missing:
        raise RuntimeError(f"{src_path}: could not find function(s) {missing} — has the cascade fix been moved/renamed?")
    return wanted


def _extract_module_const(src_path, name):
    """FIXED 2026-07-08 (independent-review find, discovered verifying an unrelated change): a companion to
    _extract_functions — needed because serve.py's _relock_stale_scenes was refactored (independently of this
    fix) to read the module-level GATE_SEQ constant instead of a hand-duplicated gate tuple, but
    _extract_functions only ever pulls the 3 named FUNCTION bodies via ast, never a module-level assignment
    those functions now depend on. Exec'd into test_serve_py's bare namespace (which has no GATE_SEQ), the
    extracted _relock_stale_scenes raised a bare NameError on `for g in list(GATE_SEQ) + [...]` — silently
    swallowed by locked_state()'s own fail-open `except Exception: pass` ("a relock error must never brick
    gate-status reads"), so the relock never ran and this test failed. Pulls GATE_SEQ's own literal value
    straight from serve.py's source via ast.literal_eval — never a second hand-typed copy of the list — so it
    can never itself drift from the constant it is testing against."""
    src = open(src_path, encoding="utf-8").read()
    tree = ast.parse(src, filename=src_path)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise RuntimeError(f"{src_path}: could not find module-level constant {name!r}")


def test_serve_py(tmp):
    """Exercise serve.py's MIRRORED copy — extracted via ast (not imported: serve.py binds a live socket at module
    level). If this ever fails while test_cb_pipeline passes, the two duplicated implementations have drifted."""
    fails = []
    if not os.path.exists(SERVE_PY):
        return [f"serve.py not found at {SERVE_PY} — skipped"]
    fns = _extract_functions(SERVE_PY, ["_scene_beats_fingerprint", "_relock_stale_scenes", "locked_state"])
    ns = {"json": json, "pathlib": __import__("pathlib"), "hashlib": hashlib,
          "GATE_SEQ": _extract_module_const(SERVE_PY, "GATE_SEQ")}
    for name in ("_scene_beats_fingerprint", "_relock_stale_scenes", "locked_state"):
        exec(compile(fns[name], SERVE_PY, "exec"), ns)
    ns["OUT"] = ns["pathlib"].Path(tmp)
    ns["CBGEN"] = ns["pathlib"].Path(tmp)

    pkg = os.path.join(tmp, "Ep9_Test_beat_package.json")
    _scratch_package(pkg, _base_beats())
    cur = ns["_scene_beats_fingerprint"]("Ep9", "9")
    json.dump({"Ep9": {"9": {"1": True, "1.6": True, "1_fp": cur}}}, open(os.path.join(tmp, "locked.json"), "w"))

    d = ns["locked_state"]()
    if not d.get("Ep9", {}).get("9", {}).get("1") or not d.get("Ep9", {}).get("9", {}).get("1.6"):
        fails.append("serve.py: gates 1 and 1.6 should still read approved before any beat-package change")

    beats = _base_beats(); beats.append({"beatCode": "9.B3", "sceneNumber": 9, "storyBeat": "added by a restructure"})
    _scratch_package(pkg, beats)

    d2 = ns["locked_state"]()
    sd = d2.get("Ep9", {}).get("9", {})
    if sd.get("1") or sd.get("1.6") or sd.get("1_fp"):
        fails.append(f"serve.py: gates 1 + 1.6 + the fingerprint should have been cascade-cleared, still {sd!r}")
    return fails


def test_manifest_refusal_blocks_approve(tmp):
    """THE MANIFEST (CLAUDE.md rule 37): approve() has always refused to arm a gate while a BLOCK-kind gap
    exists in the scene's data (via _manifest_gate_scene -> cb_preflight.manifest_ok) — but until now this
    file's own test suite only ever exercised that choke-point's PASS-through branch (every scratch fixture
    above is manifest-compliant by construction, per _manifest_compliant_beat's own docstring). This proves the
    REFUSAL branch directly: a beat missing a required TECHNICAL field (carryMarks — 'required on every beat',
    cb_preflight.py) must make P.approve('1', scene) return False, and must NOT write a lock entry for that
    gate. Mirrors test_cb_preflight.py's own test_missing_technical_field_caught pattern (del beat['carryMarks'])."""
    fails = []
    spec = importlib.util.spec_from_file_location("cb_pipeline_test3", os.path.join(HERE, "cb_pipeline.py"))
    P = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(P)

    pkg = os.path.join(tmp, "Ep9_ManifestRefusal_beat_package.json")
    beat = _manifest_compliant_beat("9.B1", 9, "original content", is_opener=True)
    del beat["carryMarks"]   # a required TECHNICAL field, deliberately removed -> a named BLOCK
    _scratch_package(pkg, [beat])
    P.PKG, P.LOCK, P.EP = pkg, os.path.join(tmp, "locked_manifest_refusal.json"), "Ep9"
    _sync_scratch_scene_cache("Ep9", 9, _scratch_scenes()[0])

    if P.approve("1", "9"):
        fails.append("manifest refusal: approve('1', '9') with a missing carryMarks field should return False")
    sd = P._lock().get("Ep9", {}).get("9", {})
    if sd.get("1"):
        fails.append(f"manifest refusal: gate '1' should NOT have been written to the lock, found {sd.get('1')!r}")
    return fails


def test_continuity_refusal_blocks_approve(tmp):
    """THE CONTINUITY GATE (2026-07-14, closing a real gap found by the full-pipeline verification audit):
    cb_continuity.run() has always FIRED at every generative gate but nothing ever READ its return value —
    a real canon-violation BLOCK could be computed and then silently signed off anyway. approve() now checks
    cb_continuity.check() itself, scoped conservatively: a BLOCK whose own `scene` field matches the scene
    being approved (or is genuinely global, scene=="-") refuses; a BLOCK about a DIFFERENT scene must NOT
    block this one, since cb_continuity is deliberately cross-scene by design (its own docstring: "catches
    what a single-scene build can't see") — that finding gates the OTHER scene's own approval instead."""
    import cb_continuity
    fails = []
    spec = importlib.util.spec_from_file_location("cb_pipeline_test4", os.path.join(HERE, "cb_pipeline.py"))
    P = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(P)

    pkg = os.path.join(tmp, "Ep9_ContinuityRefusal_beat_package.json")
    beat = _manifest_compliant_beat("9.B1", 9, "original content", is_opener=True)
    _scratch_package(pkg, [beat])
    lockpath = os.path.join(tmp, "locked_continuity_refusal.json")
    P.PKG, P.LOCK, P.EP = pkg, lockpath, "Ep9"
    _sync_scratch_scene_cache("Ep9", 9, _scratch_scenes()[0])
    # gate "2a" needs its predecessors ("1" and "1.6") already signed — matches this file's own established
    # shortcut (test_frame_chain_cascade, line 241) of seeding the lock directly rather than re-approving each.
    json.dump({"Ep9": {"9": {"1": True, "1.6": True}}}, open(lockpath, "w"))

    orig_check = cb_continuity.check
    try:
        # same-scene BLOCK -> refused, nothing written
        cb_continuity.check = lambda pkg, ep: [{"level": "BLOCK", "scene": "9", "shot": "9.B1", "msg": "scratch same-scene block"}]
        if P.approve("2a", "9"):
            fails.append("continuity refusal: approve('2a','9') with a same-scene continuity BLOCK should return False")
        sd = P._lock().get("Ep9", {}).get("9", {})
        if sd.get("2a"):
            fails.append(f"continuity refusal: gate '2a' should NOT have been written to the lock, found {sd.get('2a')!r}")

        # a BLOCK for a DIFFERENT scene must not refuse THIS scene's approval
        cb_continuity.check = lambda pkg, ep: [{"level": "BLOCK", "scene": "3", "shot": "3.B1", "msg": "scratch other-scene block"}]
        if not P.approve("2a", "9"):
            fails.append("continuity refusal: a BLOCK for a DIFFERENT scene must not refuse this scene's approve('2a','9')")

        # a genuinely global BLOCK (scene=="-") must refuse regardless of which scene is being approved
        cb_continuity.check = lambda pkg, ep: [{"level": "BLOCK", "scene": "-", "shot": "-", "msg": "scratch global block"}]
        if P.approve("2b", "9"):
            fails.append("continuity refusal: approve('2b','9') with a global (scene=='-') continuity BLOCK should return False")

        # gate "1" is exempt (the manifest's own content is still being produced at that stage)
        json.dump({"Ep9": {"9": {}}}, open(lockpath, "w"))
        cb_continuity.check = lambda pkg, ep: [{"level": "BLOCK", "scene": "9", "shot": "9.B1", "msg": "scratch block, should be ignored for gate 1"}]
        if not P.approve("1", "9"):
            fails.append("continuity refusal: gate '1' must be EXEMPT from the continuity check (bootstrap reasoning)")
    finally:
        cb_continuity.check = orig_check
    return fails


def test_foundation_gate_order_blocks_regen_anchor_and_build_master(tmp):
    """THE FOUNDATION GATE-ORDER FIX (2026-07-14, full-pipeline verification audit): regen_anchor() and
    build_master() were the two functions CLAUDE.md rule 66's own 2026-07-11 sweep claimed were fixed
    (alongside build_beat/gen_audio/render_beat/approve_beat/relay_prepare/relay_approve) but actually
    weren't — both are live, billed generation entry points (plate/charsheet/establishing-shot rebuilds)
    that only ever checked manifest CONTENT, never that Gate 1.6 (their real predecessor — the gate that
    unlocks Gate 2a, whose own foundation content these two functions regenerate on demand) was signed.
    Proves both now refuse with "1.6" unsigned and both get PAST that specific check (reach their own real
    generation call, here stubbed to zero cost) once "1.6" is signed."""
    import cb_scene, cb_qa
    fails = []
    spec = importlib.util.spec_from_file_location("cb_pipeline_test5", os.path.join(HERE, "cb_pipeline.py"))
    P = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(P)

    pkg = os.path.join(tmp, "Ep9_FoundationGateOrder_beat_package.json")
    beat = _manifest_compliant_beat("9.B1", 9, "original content", is_opener=True)
    _scratch_package(pkg, [beat])
    lockpath = os.path.join(tmp, "locked_foundation_gate_order.json")
    P.PKG, P.LOCK, P.EP = pkg, lockpath, "Ep9"
    _sync_scratch_scene_cache("Ep9", 9, _scratch_scenes()[0])
    import cb_prompts
    cb_prompts.LOCATIONS["Ep9"]["9"]["location"] = "scratch test location"   # regen_anchor's own sc["location"] read

    orig_build_plate, orig_check_plate = cb_scene.build_plate, cb_qa.check_plate
    orig_check = __import__("cb_continuity").check
    cb_scene.build_plate = lambda pkg, scene, ep, note="": f"media/{ep}_S{scene}_plate.png"
    cb_qa.check_plate = lambda plate, loc, master: {"ok": True, "verdict": "PASS (stubbed)"}
    __import__("cb_continuity").check = lambda pkg, ep: []   # isolate this test from the continuity gate above
    try:
        # "1.6" NOT signed -> both must refuse before reaching any real generation call
        json.dump({"Ep9": {"9": {}}}, open(lockpath, "w"))
        if P.regen_anchor("9", "plate") is not False:
            fails.append("foundation gate order: regen_anchor('9','plate') with '1.6' unsigned should return False")
        if P.build_master("9") is not False:
            fails.append("foundation gate order: build_master('9') with '1.6' unsigned should return False")

        # "1.6" signed -> both get PAST the gate-order check (the manifest check still passes, since the
        # fixture is manifest-compliant by construction) and reach the (stubbed) real generation call
        json.dump({"Ep9": {"9": {"1": True, "1.6": True}}}, open(lockpath, "w"))
        r = P.regen_anchor("9", "plate")
        if r is False:
            fails.append("foundation gate order: regen_anchor('9','plate') with '1.6' signed should NOT be refused by the gate-order check")
    finally:
        cb_scene.build_plate, cb_qa.check_plate = orig_build_plate, orig_check_plate
        __import__("cb_continuity").check = orig_check
    return fails


def test_context_refusal_blocks_approve(tmp):
    """THE CONTEXT GATE (2026-07-15, guardrail-fidelity audit): cb_context.run() has always fired at every
    generative gate purely as printed, discarded output — the same "computed but discarded" bug class already
    closed for cb_continuity above, just missed for this sibling check. approve() now checks cb_context.check()
    itself; unlike cb_continuity, cb_context is already single-scene-scoped via its own `scene=` parameter, so
    no same-scene/different-scene distinction is needed — any BLOCK it returns for the scene being approved
    refuses."""
    import cb_context
    fails = []
    spec = importlib.util.spec_from_file_location("cb_pipeline_test5", os.path.join(HERE, "cb_pipeline.py"))
    P = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(P)

    pkg = os.path.join(tmp, "Ep9_ContextRefusal_beat_package.json")
    beat = _manifest_compliant_beat("9.B1", 9, "original content", is_opener=True)
    _scratch_package(pkg, [beat])
    lockpath = os.path.join(tmp, "locked_context_refusal.json")
    P.PKG, P.LOCK, P.EP = pkg, lockpath, "Ep9"
    _sync_scratch_scene_cache("Ep9", 9, _scratch_scenes()[0])
    json.dump({"Ep9": {"9": {"1": True, "1.6": True}}}, open(lockpath, "w"))

    orig_check = cb_context.check
    orig_continuity_check = __import__("cb_continuity").check
    try:
        __import__("cb_continuity").check = lambda pkg, ep: []   # isolate this test from the continuity gate above
        cb_context.check = lambda pkg, ep, scene: [{"shot": "9.B1", "level": "BLOCK", "msg": "scratch context block"}]
        if P.approve("2a", "9"):
            fails.append("context refusal: approve('2a','9') with a context BLOCK should return False")
        sd = P._lock().get("Ep9", {}).get("9", {})
        if sd.get("2a"):
            fails.append(f"context refusal: gate '2a' should NOT have been written to the lock, found {sd.get('2a')!r}")

        # a NOTE-level finding (never a BLOCK) must not refuse
        cb_context.check = lambda pkg, ep, scene: [{"shot": "9.B1", "level": "NOTE", "msg": "scratch context note"}]
        if not P.approve("2a", "9"):
            fails.append("context refusal: a NOTE-only cb_context.check() result must not refuse approve('2a','9')")

        # gate "1" is exempt (no reference stack exists yet to check at that stage)
        json.dump({"Ep9": {"9": {}}}, open(lockpath, "w"))
        cb_context.check = lambda pkg, ep, scene: [{"shot": "9.B1", "level": "BLOCK", "msg": "scratch block, should be ignored for gate 1"}]
        if not P.approve("1", "9"):
            fails.append("context refusal: gate '1' must be EXEMPT from the context check (bootstrap reasoning)")
    finally:
        cb_context.check = orig_check
        __import__("cb_continuity").check = orig_continuity_check
    return fails


def main():
    tmp = tempfile.mkdtemp(prefix="cb_gate_cascade_test_")
    try:
        fails = (test_cb_pipeline(tmp) + test_serve_py(tmp) + test_frame_chain_cascade(tmp)
                  + test_manifest_refusal_blocks_approve(tmp) + test_continuity_refusal_blocks_approve(tmp)
                  + test_context_refusal_blocks_approve(tmp)
                  + test_foundation_gate_order_blocks_regen_anchor_and_build_master(tmp))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if fails:
        print("CASCADE ASSERTION FAILED:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("CASCADE ASSERTION PASSED — a Gate-1 deliverable change correctly cascade-relocks every downstream "
          "sign-off (cb_pipeline.py + its serve.py mirror), an upstream ending-frame retake correctly marks "
          "every downstream beat's keyframe/clip dirty (the FRAME CHAIN doctrine), and a manifest BLOCK "
          "correctly refuses a gate approval without writing a lock entry (THE MANIFEST).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
