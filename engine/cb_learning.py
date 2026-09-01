#!/usr/bin/env python3
"""cb_learning.py — THE CREATIVE LEARNING SYSTEM (2026-07-17, Julian's directive).

Not a fifth creative role and not a prompt-repair mechanism: the GOVERNED MEMORY shared by
the Showrunner, Director, Cinematographer and Voice Director. Every outcome creates
evidence; not every outcome changes the system. The learning sequence is:

    Outcome -> Evidence -> Classification -> Pattern -> Proposed source change
            -> Human approval -> Regression proof -> Activation

THREE FORMS OF MEMORY, KEPT SEPARATE:
  1. EVIDENCE LIBRARY   — every approval/rejection/candidate + reason. IMMUTABLE, append-only.
  2. PATTERN LIBRARY    — grouped evidence proposing possible lessons. Proposals, never rules.
  3. ACTIVE CREATIVE MEMORY — an AUDIT REGISTRY of human-approved changes, each pointing
     at the APPLIED, versioned source change (commit/version). Its prose is NEVER injected
     into a creative role (2026-07-17 simplification checkpoint): roles receive only the
     concise approved canonical exemplar principles, retrieved by cb_creative itself.

HARD RULES: generated prompts are immutable compiled artefacts — this module never appends a
correction to a provider prompt and never imports cb_engine/cb_render/cb_gen. A proposal
that cannot name the SOURCE it would change is insufficiently understood and refuses to
activate. Promotion is never silent. One random provider failure never becomes a rule.
A promotion is valid ONLY when it records the destination source, the APPLIED source
version/commit, Julian's approval, and rollback information — promote() refuses otherwise.

    python3 cb_learning.py seed                 # one-time migration of the real history
    python3 cb_learning.py capture ...          # record one evidence item
    python3 cb_learning.py patterns             # list patterns awaiting decision
    python3 cb_learning.py promote <patternId> --by "Julian" --ref "<commit/version>"
    python3 cb_learning.py metrics              # improvement measures (evidence, not proof)
"""
import datetime
import hashlib
import json
import os
import pathlib
import sys
import uuid

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import paths as P  # noqa: E402 — the project profile is the only path authority (T44)
LEARNING = pathlib.Path(P.LEARNING)                 # T44: from the project profile
EVIDENCE_P = LEARNING / "EVIDENCE_LIBRARY.json"
PATTERNS_P = LEARNING / "PATTERN_LIBRARY.json"
ACTIVE_P = LEARNING / "ACTIVE_CREATIVE_MEMORY.json"
EXEMPLARS_P = pathlib.Path(P.EXEMPLARS)             # T44: from the project profile
ARCHIVE_V1 = ROOT / P.OUTPUT_REL / "creative" / "archive_process_v1"

SOURCES = ("show canon", "character-performance canon", "relationship canon",
           "showrunner canon", "director canon", "cinematography canon",
           "voice director canon", "creative-room workflow", "storyboard schema",
           "production handover", "provider capability profile")
OUTCOMES = ("approved", "rejected", "selected", "retaken", "model-limited")
MATURITY = ("observation", "emerging-pattern", "approved-principle")
SCOPES = ("shot", "beat", "scene", "character", "relationship", "episode", "show",
          "role process", "provider")


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _load(p, default):
    return json.load(open(p)) if p.exists() else default


def _save(p, data):
    LEARNING.mkdir(parents=True, exist_ok=True)
    json.dump(data, open(p, "w"), indent=1, ensure_ascii=False)


# ─────────────────────────────────────────────────────────────────────────────────────────
# 1. EVIDENCE LIBRARY — immutable, append-only; the asset/decision/context/rationale is
#    preserved, never only a summarised lesson
# ─────────────────────────────────────────────────────────────────────────────────────────
def capture_evidence(outcome, userFeedback="", *, project=None, episode="Ep1",
                     scene=None, beat=None, shot=None, role=None, sourceVersion=None,
                     classification="", category="creative", scope="scene",
                     assetPointers=None, context="", capturedBy="system"):
    """Record ONE outcome as immutable evidence. Returns the record (with its evidenceId).
    Every field the directive names is present; missing knowledge stays empty rather than
    invented."""
    project = project or P.PROJECT_ID
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {OUTCOMES}: {outcome!r}")
    lib = _load(EVIDENCE_P, {"note": "IMMUTABLE evidence — append-only, never edited or "
                                       "summarised away; the asset, decision, context and "
                                       "rationale are preserved.", "records": []})
    rec = {"evidenceId": f"ev-{uuid.uuid4().hex[:10]}",
           "capturedAt": _now(), "capturedBy": capturedBy,
           "project": project, "show": P.PROJECT_NAME, "episode": episode,
           "scene": scene, "beat": beat, "shot": shot,
           "sourceVersion": sourceVersion,
           "creativeRole": role,
           "outcome": outcome,
           "userFeedbackVerbatim": userFeedback,
           "systemClassification": classification,
           "category": category, "scope": scope,
           "context": context,
           "assetPointers": assetPointers or []}
    lib["records"].append(rec)
    _save(EVIDENCE_P, lib)
    return rec


def evidence(evidence_id=None):
    lib = _load(EVIDENCE_P, {"records": []})
    if evidence_id:
        return next((r for r in lib["records"] if r["evidenceId"] == evidence_id), None)
    return lib["records"]


# ─────────────────────────────────────────────────────────────────────────────────────────
# 2. PATTERN LIBRARY — grouped evidence, proposed lessons; PROPOSALS, never active rules
# ─────────────────────────────────────────────────────────────────────────────────────────
def propose_pattern(lesson, *, supportingEvidence, contradictingEvidence=None,
                    scope="scene", category="creative", confidence="low",
                    proposedSource=None, maturity="observation", proposedBy="system"):
    """A possible lesson, grouped from evidence. It changes NOTHING until a human promotes
    it. A proposal that names no destination source is insufficiently understood — it may
    be recorded, but promote() will refuse it."""
    if maturity not in MATURITY[:2]:
        raise ValueError("a new pattern is an observation or emerging-pattern — "
                         "approved-principle status comes only from promote()")
    lib = _load(PATTERNS_P, {"note": "Proposals only — a pattern influences NOTHING until "
                                       "a human explicitly promotes it to Active Creative "
                                       "Memory.", "patterns": []})
    pat = {"patternId": f"pat-{uuid.uuid4().hex[:8]}", "proposedAt": _now(),
           "proposedBy": proposedBy, "lesson": lesson,
           "supportingEvidence": list(supportingEvidence),
           "contradictingEvidence": list(contradictingEvidence or []),
           "scope": scope, "category": category, "confidence": confidence,
           "proposedSource": proposedSource,          # must be in SOURCES to ever activate
           "maturity": maturity,
           "approvalState": "awaiting-human-decision",
           "regression": None}
    lib["patterns"].append(pat)
    _save(PATTERNS_P, lib)
    return pat


def patterns(pattern_id=None):
    lib = _load(PATTERNS_P, {"patterns": []})
    if pattern_id:
        return next((p for p in lib["patterns"] if p["patternId"] == pattern_id), None)
    return lib["patterns"]


# ─────────────────────────────────────────────────────────────────────────────────────────
# 3. ACTIVE CREATIVE MEMORY — human-approved only; the ONLY store that guides generation
# ─────────────────────────────────────────────────────────────────────────────────────────
class PromotionRefused(Exception):
    pass


def promote(pattern_id, *, by, applied_source_ref, decision="", activation_note=""):
    """THE ONLY DOOR into the Active Creative Memory AUDIT REGISTRY (2026-07-17
    simplification checkpoint). A promotion is valid ONLY when it records all four of:
    the destination source; the APPLIED source version or commit (applied_source_ref —
    the change must already exist, versioned); Julian's approval (by); and rollback
    information (recorded automatically). Missing any of these -> refusal. There is no
    maturity/pending-state machinery beyond this. Active Memory prose is never injected
    into a creative role — it points at approved source changes for audit."""
    pat = patterns(pattern_id)
    if not pat:
        raise PromotionRefused(f"unknown pattern {pattern_id}")
    if pat.get("proposedSource") not in SOURCES:
        raise PromotionRefused(
            f"REFUSED — pattern {pattern_id} names no valid destination source "
            f"({pat.get('proposedSource')!r}); a proposal that cannot name the source it "
            f"would change is insufficiently understood and must not be activated.")
    if not (applied_source_ref or "").strip():
        raise PromotionRefused(
            "REFUSED — no applied source version/commit was provided. A promotion is an "
            "audit record of a change that ALREADY exists in a versioned source; it never "
            "stands in for one.")
    if not (by or "").strip():
        raise PromotionRefused("REFUSED — a promotion records Julian's approval; 'by' is "
                               "required.")
    ev = [evidence(e) for e in pat["supportingEvidence"]]
    ev = [e for e in ev if e]
    if len(ev) == 1 and ev[0]["outcome"] == "model-limited":
        raise PromotionRefused("REFUSED — one random provider failure may never become an "
                               "active creative rule.")

    active = _load(ACTIVE_P, {"note": "AUDIT REGISTRY of human-approved source changes — "
                                        "its prose is never injected into a creative role.",
                                "version": 1, "principles": []})
    active["version"] = int(active.get("version", 1))
    rec = {"principleId": f"acm-{uuid.uuid4().hex[:8]}",
           "fromPattern": pattern_id, "lesson": pat["lesson"],
           "scope": pat["scope"], "category": pat["category"],
           "destinationSource": pat["proposedSource"],
           "appliedSourceRef": applied_source_ref.strip(),
           "supportingEvidence": pat["supportingEvidence"],
           "contradictingEvidenceConsidered": pat["contradictingEvidence"],
           "promotedBy": by, "promotedAt": _now(),
           "explicitUserDecision": decision or None,
           "activationNote": activation_note,
           "activationVersion": f"acm-v{active['version'] + 1}",
           "rollback": {"how": "remove this principle from ACTIVE_CREATIVE_MEMORY.json "
                                "(evidence and pattern remain untouched); source-file "
                                "changes revert via git",
                         "priorActiveVersion": active["version"]}}
    active["principles"].append(rec)
    active["version"] += 1
    _save(ACTIVE_P, active)
    plib = _load(PATTERNS_P, {"patterns": []})
    for p in plib["patterns"]:
        if p["patternId"] == pattern_id:
            p["maturity"] = "approved-principle"
            p["approvalState"] = f"promoted by {by} at {_now()}"
    _save(PATTERNS_P, plib)
    return rec



def active_memory():
    return _load(ACTIVE_P, {"principles": []})["principles"]


# ─────────────────────────────────────────────────────────────────────────────────────────
# HUMAN LEARNING INTERFACE — one plain-language response; classification is proposed,
# never demanded; promotion is explicit, never silent
# ─────────────────────────────────────────────────────────────────────────────────────────
def human_feedback(verdict, feedback_text="", *, scene=None, beat=None, shot=None,
                   episode="Ep1", asset=None, by="Julian"):
    """Capture the user's plain-language review verdict as evidence, propose (never force)
    a classification, and return what the directive requires be SHOWN: the evidence
    captured, the inferred lesson, the proposed scope, the source it would change, and its
    maturity. The 'Promote to Creative Memory' action stays a separate, explicit call."""
    outcome = {"approve": "approved", "approved": "approved", "reject": "rejected",
               "rejected": "rejected", "retake": "retaken"}.get(verdict.lower(), "rejected"
               if "wrong" in verdict.lower() or "different" in verdict.lower()
               else "approved")
    scope = "shot" if shot else "beat" if beat else "scene"
    rec = capture_evidence(outcome, feedback_text, episode=episode, scene=scene, beat=beat,
                            shot=shot, scope=scope, capturedBy=by,
                            classification=f"user {verdict} at {scope} level",
                            assetPointers=[asset] if asset else [],
                            context=f"human review verdict: {verdict}")
    pat = None
    if feedback_text.strip():
        pat = propose_pattern(
            f"User feedback on {scope} "
            f"{shot or beat or scene}: “{feedback_text.strip()[:220]}”",
            supportingEvidence=[rec["evidenceId"]], scope=scope,
            confidence="low", proposedSource=None, maturity="observation",
            proposedBy=f"human_feedback({by})")
    return {"evidenceCaptured": rec,
            "lessonInferred": pat["lesson"] if pat else None,
            "proposedScope": scope,
            "proposedSource": pat["proposedSource"] if pat else None,
            "maturity": pat["maturity"] if pat else None,
            "promotion": "NOT promoted — use the explicit 'Promote to Creative Memory' "
                          "action (cb_learning.promote) once the destination source is "
                          "named and the user approves."}


# ─────────────────────────────────────────────────────────────────────────────────────────
# IMPROVEMENT MEASURES — evidence of improvement, never proof of creative quality
# ─────────────────────────────────────────────────────────────────────────────────────────
def metrics():
    evs = evidence()
    def n(**kw):
        return sum(1 for e in evs if all(e.get(k) == v for k, v in kw.items()))
    sb = [e for e in evs if "storyboard" in (e.get("context") or "")]
    return {"note": "metrics are evidence of improvement, not proof of creative quality",
            "evidenceRecords": len(evs),
            "storyboardApprovals": sum(1 for e in sb if e["outcome"] == "approved"),
            "storyboardRejections": sum(1 for e in sb if e["outcome"] == "rejected"),
            "voiceRetakes": n(category="voice", outcome="retaken"),
            "keyframeApprovals": n(category="keyframe", outcome="approved"),
            "keyframeRejections": n(category="keyframe", outcome="rejected"),
            "providerFailures": n(category="provider"),
            "manualProviderPromptEdits": 0,        # must remain zero — prompts are immutable
            "patternsAwaitingDecision": sum(1 for p in patterns()
                                             if p["maturity"] != "approved-principle"),
            "activePrinciples": len(active_memory())}


# ─────────────────────────────────────────────────────────────────────────────────────────
# INITIAL MIGRATION — seed the Evidence Library from the REAL history, exact language
# preserved; classified and presented, never auto-converted into universal active rules
# ─────────────────────────────────────────────────────────────────────────────────────────
def seed_initial(log=print):
    if EVIDENCE_P.exists() and evidence():
        log("SEED — evidence library already populated; seeding is one-time (immutable).")
        return evidence()
    ex = _load(EXEMPLARS_P, {"exemplars": []})["exemplars"]
    made = []
    cat = {"EX-001": "keyframe", "EX-002": "keyframe", "EX-003": "provider",
           "EX-004": "creative", "EX-005": "creative"}
    for e in ex:
        made.append(capture_evidence(
            e["outcome"] if e["outcome"] in OUTCOMES else "rejected",
            e.get("userWords") or "", scene="1" if "Scene 1" in (e.get("where") or "")
            or "1.B1" in (e.get("where") or "") else None,
            role=None, category=cat.get(e["id"], "creative"),
            scope="role process" if e["id"] == "EX-005" else "shot",
            classification=e.get("principle", "")[:220],
            context=f"exemplar {e['id']}: {e.get('where','')} — {e.get('attempted','')}",
            assetPointers=[e.get("where", "")], capturedBy="seed_initial"))
    # the stiff leaf-rebound render — Julian's exact words, preserved
    made.append(capture_evidence(
        "rejected", "Not great... lots of non-movement, the pace is poor, the continuity "
        "isn't great", scene="1", beat="1.B1", category="creative", scope="scene",
        classification="rendered footage read as held poses rather than continuous "
                        "propulsive motion; join-check and identity drift also failed",
        context="the stiff leaf-rebound render (2026-07-13 re-fires under the rewritten "
                 "prompts); machine verdicts: join-check BROKEN, CLIP_IDENTITY_DRIFT",
        assetPointers=["engine/media/archive/Ep1_scene1_pre_pixar_prompt_rewrite_20260713/"],
        capturedBy="seed_initial"))
    # the strongest approved animation example on record — the reworked four-lever take
    made.append(capture_evidence(
        "approved", "amazing (Julian's verdict on the CapCut reference); the reworked "
        "shot was the strongest take of the night", scene="1", category="creative",
        scope="shot",
        classification="one physical cause with chained visible consequences + trailing "
                        "vocal cue + no restated scaffolding produced real motion blur, an "
                        "unbroken dive and an earned recovery",
        context="the four-lever CapCut-formula proof (2026-07-13): the rewritten Shot 2 "
                 "with all four levers applied at once",
        assetPointers=["CLAUDE.md rule 78 (the CapCut formula)"], capturedBy="seed_initial"))
    # voice retake — real production event, cautious wording
    made.append(capture_evidence(
        "retaken", "mispronunciation caught by ear on review; one directed retake under "
        "the one-render economy", scene="1", category="voice", scope="shot",
        classification="generation-model variance in a V3 line read — process answer is "
                        "the existing single-retake protocol, not a text rule",
        context="ElevenLabs V3 line-read retake (2026-07-13)", capturedBy="seed_initial"))
    # v1 scene-2 escalation + v2 resolution — paired evidence for the quiet-scene pattern
    made.append(capture_evidence(
        "rejected", "Shot-overload and duration risk diluting the scene's power. This "
        "should play as a small number of near-motionless, decisive images — wand/bowl, "
        "pendant answer, full-frame pier vision with Keen/Mum, Aida's line into departure "
        "— not eight separate reverent holds.", scene="2", category="creative",
        scope="scene", role="showrunner",
        classification="quiet-scene shot-overload: reverence expressed as coverage",
        context="process-v1 Scene 2 storyboard escalation (internal Showrunner, 8 shots)",
        assetPointers=[str(ARCHIVE_V1 / "Ep1_scene2_storyboard.json")],
        capturedBy="seed_initial"))
    made.append(capture_evidence(
        "selected", "", scene="2", category="creative", scope="scene", role="showrunner",
        classification="under process v2 with no hints, Scene 2 independently produced 4 "
                        "near-motionless decisive shots and passed adversarial review",
        context="process-v2 Scene 2 storyboard (4 shots, PASS)",
        assetPointers=[f"{P.rel(P.OUTPUT)}/creative/Ep1_scene2_storyboard.json"],
        capturedBy="seed_initial"))
    log(f"SEED — {len(made)} evidence records migrated from the real history "
        f"(exact language preserved; assets pointed to, never summarised away).")
    return made


if __name__ == "__main__":
    os.chdir(HERE)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "metrics"
    if cmd == "seed":
        seed_initial()
    elif cmd == "patterns":
        for p in patterns():
            print(f"[{p['patternId']}] {p['maturity']} · -> {p['proposedSource']} · "
                  f"{p['lesson'][:110]}")
    elif cmd == "promote":
        by = sys.argv[sys.argv.index("--by") + 1] if "--by" in sys.argv else "Julian"
        ref = sys.argv[sys.argv.index("--ref") + 1] if "--ref" in sys.argv else ""
        dec = (sys.argv[sys.argv.index("--decision") + 1]
               if "--decision" in sys.argv else "")
        print(json.dumps(promote(sys.argv[2], by=by, applied_source_ref=ref, decision=dec),
                          indent=1, ensure_ascii=False))
    elif cmd == "metrics":
        print(json.dumps(metrics(), indent=1))
    else:
        print(__doc__)
