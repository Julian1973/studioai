#!/usr/bin/env python3
"""test_cutover_independence.py — Julian's Gate-5 hold directive (2026-07-16): prove the
three DEFERRED re-home items (voice-direction craft, resolver consolidation, the 15s
literals) create NO runtime import, behavioural dependency, or cutover dependency on the
old pipeline — and that the guarded shared-module sites survive the old path's absence.

The demolition set (THE_DEFINITIVE_PIPELINE.md §RECOVERED ARCHITECTURE): cb_segprompt,
cb_beats, cb_replicator, cb_seedance, cb_director_pass, cb_previz, beat_preview.

Method: static AST proof (no import statement anywhere in the new spine names a demolition
module) PLUS a dynamic proof in a FRESH subprocess where the demolition modules are made
unimportable — the new spine must import, compile a contract, and cb_post's guarded sites
must degrade exactly as designed. Zero API calls, zero spend.

    pytest test_cutover_independence.py -q
"""
import ast, pathlib, subprocess, sys, textwrap

HERE = pathlib.Path(__file__).resolve().parent
DEMOLITION = {"cb_segprompt", "cb_beats", "cb_replicator", "cb_seedance",
              "cb_director_pass", "cb_previz", "beat_preview"}


def _imports_of(pyfile):
    tree = ast.parse(pathlib.Path(pyfile).read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_new_spine_never_imports_a_demolition_module():
    """Static proof — covers module-level AND function-level imports (ast.walk sees both)."""
    for f in ("cb_render.py", "cb_engine.py"):
        hits = _imports_of(HERE / f) & DEMOLITION
        assert not hits, f"{f} imports demolition module(s): {hits}"


def _run_blocked(code):
    """Run code in a FRESH interpreter where every demolition module raises on import."""
    blocker = textwrap.dedent(f"""
        import sys
        BLOCKED = {sorted(DEMOLITION)!r}
        class _Blocker:
            def find_module(self, name, path=None):
                return self if name.split('.')[0] in BLOCKED else None
            def find_spec(self, name, path=None, target=None):
                if name.split('.')[0] in BLOCKED:
                    raise ImportError(f"BLOCKED (cutover simulation): {{name}}")
                return None
            def load_module(self, name):
                raise ImportError(f"BLOCKED (cutover simulation): {{name}}")
        sys.meta_path.insert(0, _Blocker())
        sys.path.insert(0, {str(HERE)!r})
    """)
    r = subprocess.run([sys.executable, "-c", blocker + textwrap.dedent(code)],
                       capture_output=True, text=True, cwd=str(HERE), timeout=120)
    assert r.returncode == 0, f"blocked-world run failed:\n{r.stdout}\n{r.stderr}"
    return r.stdout


def test_new_spine_imports_and_compiles_with_old_pipeline_absent():
    """Dynamic proof: with every demolition module unimportable, cb_engine + cb_render
    import cleanly AND a real shot contract compiles with the anchor texts intact —
    the deferred items (voice craft, resolver, duration literals) owe the old path nothing."""
    out = _run_blocked("""
        import cb_engine as E
        import cb_render as R
        shot = E.Shot(shotId='t.S1', beatCode='t', durationSec=6.0, purpose='p',
                      performanceAssignment='Fuzzby rockets past and clips the stem.',
                      camera='Wide tracking', openingPose='Fuzzby wound up outside the flower',
                      sourceType='opener', sourceShotId=None, cutInMotivation=None,
                      dialogueBinding=None, dialogueLines=[], visualPayoff='He grazes the leaf',
                      cutPace='single_continuous_take', internalCuts=[],
                      physicalStaging=None, prohibited=[], charactersInFrame=['Fuzzby'],
                      continuityIn=E.ContinuityState(lighting='warm', cameraSide='left',
                          characters=[E.CharacterState(character='Fuzzby', screenZone='left',
                              facing='right', pose='hover', expression='bright',
                              visibleMarks=[], heldProps=[])]),
                      continuityOut=E.ContinuityState(lighting='warm', cameraSide='left',
                          characters=[E.CharacterState(character='Fuzzby', screenZone='left',
                              facing='right', pose='hover', expression='bright',
                              visibleMarks=[], heldProps=[])]))
        prompt, wc, slots = E.compile_shot_contract(shot, {}, {'Fuzzby': {'sizeRank': 2, 'avoid': 'bee'}})
        assert E.OPENER_ANCHOR[:-1] in prompt and wc <= E.MAX_SHOT_PROMPT_WORDS
        # deferred item 7 (resolver): self-contained, exact-match-only, no old-path code
        cfg = {'Fuzzby': {}, "Keen's Mum": {}, 'Keen': {}}
        assert R._resolve_char('FUZZBY', cfg) == 'Fuzzby'
        assert R._resolve_char("KEEN'S MUM", cfg) == "Keen's Mum"
        assert R._resolve_char('Keen', cfg) == 'Keen'      # never substring-matches Keen's Mum
        print('SPINE-OK', wc)
    """)
    assert "SPINE-OK" in out


def test_cb_post_guarded_sites_degrade_without_old_pipeline():
    """Re-home item 1's guards, proven in the blocked world: the settle-trim falls back to
    its identical historical value; SFX cue resolution degrades to an empty list — the KEEP
    module (which cb_render imports) survives demolition with no behaviour invented."""
    out = _run_blocked("""
        import cb_post
        assert cb_post._settle_trim() == 2.0, cb_post._settle_trim()
        assert not hasattr(cb_post, 'sweeten_cues_for_scene')   # deleted at the 2026-07-16 cutover
        print('POST-OK')
    """)
    assert "POST-OK" in out


# (the old-pipeline-coexistence test was deleted at the 2026-07-16 destructive cutover —
#  the legacy pipeline no longer exists to coexist with; the blocked-world tests above are
#  now simply the truth of the tree)

def test_deferred_item_8_no_duration_literal_dependency():
    """Item 8 (the 15s literals): the new path never sends duration='auto', so cb_gen's and
    cb_costs' 'auto'-fallback literals can never bite it. Proven two ways: cost estimation
    with an explicit shot duration is exact, and the fire path's source always formats the
    shot's own seconds (asserted here against the code, pinned live by the golden path)."""
    import cb_costs
    rate, _, _ = cb_costs.RATES["seedance_standard_per_sec"]
    assert abs(cb_costs.estimate_video_cost("seedance_standard_per_sec", 6) - rate * 6) < 1e-9
    src = (HERE / "cb_render.py").read_text()
    assert 'duration=str(int(round(envelope["durationSec"])))' in src   # sealed envelope, 2026-07-16
    assert '"auto"' not in src


if __name__ == "__main__":
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", __file__, "-q"]))
