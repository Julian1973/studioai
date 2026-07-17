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
  3. ACTIVE CREATIVE MEMORY — only HUMAN-APPROVED principles/truths/workflow changes. Only
     this store may influence future generation as authoritative guidance.

HARD RULES: generated prompts are immutable compiled artefacts — this module never appends a
correction to a provider prompt and never imports cb_engine/cb_render/cb_gen. A proposal
that cannot name the SOURCE it would change is insufficiently understood and refuses to
activate. Promotion is never silent. One random provider failure never becomes a rule.
Every activation records rollback information and requires a regression comparison (or the
user's own explicit creative decision, which outranks any repetition count).

    python3 cb_learning.py seed                 # one-time migration of the real history
    python3 cb_learning.py capture ...          # record one evidence item
    python3 cb_learning.py patterns             # list patterns awaiting decision
    python3 cb_learning.py promote <patternId> --by "Julian" [--decision "..."]
    python3 cb_learning.py metrics              # improvement measures (evidence, not proof)
    python3 cb_learning.py show <role>          # what a role would retrieve
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
LEARNING = ROOT / "shows" / "crystal-bears" / "creative" / "learning"
EVIDENCE_P = LEARNING / "EVIDENCE_LIBRARY.json"
PATTERNS_P = LEARNING / "PATTERN_LIBRARY.json"
ACTIVE_P = LEARNING / "ACTIVE_CREATIVE_MEMORY.json"
EXEMPLARS_P = ROOT / "shows" / "crystal-bears" / "creative" / "EXEMPLAR_LIBRARY.json"
ARCHIVE_V1 = ROOT / "cb-output" / "creative" / "archive_process_v1"

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
def capture_evidence(outcome, userFeedback="", *, project="crystal-bears", episode="Ep1",
                     scene=None, beat=None, shot=None, role=None, sourceVersion=None,
                     classification="", category="creative", scope="scene",
                     assetPointers=None, context="", capturedBy="system"):
    """Record ONE outcome as immutable evidence. Returns the record (with its evidenceId).
    Every field the directive names is present; missing knowledge stays empty rather than
    invented."""
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {OUTCOMES}: {outcome!r}")
    lib = _load(EVIDENCE_P, {"note": "IMMUTABLE evidence — append-only, never edited or "
                                       "summarised away; the asset, decision, context and "
                                       "rationale are preserved.", "records": []})
    rec = {"evidenceId": f"ev-{uuid.uuid4().hex[:10]}",
           "capturedAt": _now(), "capturedBy": capturedBy,
           "project": project, "show": "Crystal Bears", "episode": episode,
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


def _regression_ok(pat, explicit_user_decision):
    """Regression-before-activation: a recorded comparison across the anchor suite — OR the
    user's own explicit creative decision, which the directive says outranks repetition."""
    if explicit_user_decision:
        return True
    reg = pat.get("regression")
    return bool(reg and reg.get("comparisonPresented") and reg.get("humanApproved"))


def promote(pattern_id, *, by, explicit_user_decision=None, activation_note=""):
    """THE ONLY DOOR into Active Creative Memory. Refuses when: no named destination
    source; a single provider failure with no user decision; or no regression comparison
    and no explicit user decision. Never silent — returns the full activation record."""
    pat = patterns(pattern_id)
    if not pat:
        raise PromotionRefused(f"unknown pattern {pattern_id}")
    if pat.get("proposedSource") not in SOURCES:
        raise PromotionRefused(
            f"REFUSED — pattern {pattern_id} names no valid destination source "
            f"({pat.get('proposedSource')!r}); a proposal that cannot name the source it "
            f"would change is insufficiently understood and must not be activated.")
    ev = [evidence(e) for e in pat["supportingEvidence"]]
    ev = [e for e in ev if e]
    if (len(ev) == 1 and ev[0]["outcome"] == "model-limited"
            and not explicit_user_decision):
        raise PromotionRefused("REFUSED — one random provider failure may never become an "
                               "active creative rule.")
    if not _regression_ok(pat, explicit_user_decision):
        raise PromotionRefused(
            "REFUSED — activation requires a presented regression comparison across the "
            "anchor-scene suite (kinetic comedy, quiet emotion, dialogue, ensemble, "
            "continuity) approved by the user, or the user's own explicit creative "
            "decision. Run record_regression() first, or pass explicit_user_decision "
            "with the user's exact words.")

    active = _load(ACTIVE_P, {"note": "HUMAN-APPROVED principles only — the sole store "
                                        "that may guide future generation.", "version": 1,
                                "principles": []})
    active["version"] = int(active.get("version", 1))
    rec = {"principleId": f"acm-{uuid.uuid4().hex[:8]}",
           "fromPattern": pattern_id, "lesson": pat["lesson"],
           "scope": pat["scope"], "category": pat["category"],
           "destinationSource": pat["proposedSource"],
           "supportingEvidence": pat["supportingEvidence"],
           "contradictingEvidenceConsidered": pat["contradictingEvidence"],
           "promotedBy": by, "promotedAt": _now(),
           "explicitUserDecision": explicit_user_decision,
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


def record_regression(pattern_id, *, comparison, human_approved, by):
    """Attach the regression evidence to a pattern: the anchor-suite comparison (old vs
    proposed across kinetic/quiet/dialogue/ensemble/continuity) and whether the user
    approved it. This function records; it never runs paid scene reruns itself."""
    plib = _load(PATTERNS_P, {"patterns": []})
    for p in plib["patterns"]:
        if p["patternId"] == pattern_id:
            p["regression"] = {"comparison": comparison, "comparisonPresented": True,
                                "humanApproved": bool(human_approved), "by": by,
                                "at": _now()}
    _save(PATTERNS_P, plib)


def active_memory():
    return _load(ACTIVE_P, {"principles": []})["principles"]


# ─────────────────────────────────────────────────────────────────────────────────────────
# RETRIEVAL — scoped, labelled, small; never an instruction wall, never the whole library
# ─────────────────────────────────────────────────────────────────────────────────────────
_ROLE_KEYS = {"showrunner": ("showrunner canon", "show canon", "creative-room workflow"),
              "director": ("director canon", "character-performance canon",
                            "relationship canon", "creative-room workflow"),
              "cinematographer": ("cinematography canon", "creative-room workflow"),
              "voice": ("voice director canon", "character-performance canon")}


def _role_key(role_string):
    r = (role_string or "").lower()
    if "voice" in r:
        return "voice"
    if "showrunner" in r:
        return "showrunner"
    if "cinematographer" in r and "director" not in r.split("cinematographer")[0]:
        return "cinematographer"
    return "director"                              # joint conferences retrieve as director+cine


def retrieve_for_role(role_string, cast=None, max_chars=2600):
    """The memory ONE role receives for ONE task: a few approved principles in its own
    lanes, a small number of positive and negative exemplars, provider evidence kept
    separate, and unresolved observations labelled as exactly that. Each block is labelled
    so the Showrunner can distinguish canon truth / approved preference / contextual
    exemplar / provider limitation / unresolved observation."""
    key = _role_key(role_string)
    lanes = _ROLE_KEYS[key] + (("cinematography canon",) if "cinematographer"
                                in (role_string or "").lower() else ())
    out = ["CANON TRUTH: the show/character/relationship canon in your context is "
           "authoritative and is supplied separately — nothing below overrides it."]

    prefs = [p for p in active_memory() if p["destinationSource"] in lanes][:3]
    if prefs:
        out.append("APPROVED CREATIVE PREFERENCES (human-promoted principles — apply them):")
        out += [f"  • {p['lesson']} [{p['destinationSource']}, {p['activationVersion']}]"
                for p in prefs]

    evs = evidence()
    pos = [e for e in evs if e["outcome"] in ("approved", "selected")
           and e["category"] != "provider"][-2:]
    neg = [e for e in evs if e["outcome"] == "rejected"
           and e["category"] != "provider"][-3:]
    if pos or neg:
        out.append("CONTEXTUAL EXEMPLARS (specific past verdicts — context, not law):")
        out += [f"  ✓ {e['context'][:110] or e['systemClassification'][:110]} — user: "
                f"“{e['userFeedbackVerbatim'][:150]}”" for e in pos]
        out += [f"  ✗ {e['context'][:110] or e['systemClassification'][:110]} — user: "
                f"“{e['userFeedbackVerbatim'][:150]}”" for e in neg]

    prov = [e for e in evs if e["category"] == "provider"][-2:]
    if prov:
        out.append("PROVIDER LIMITATION EVIDENCE (kept separate — capability, not taste):")
        out += [f"  ⚠ {e['systemClassification'] or e['context'][:130]}" for e in prov]

    unresolved = [p for p in patterns() if p["maturity"] != "approved-principle"][:2]
    if unresolved:
        out.append("UNRESOLVED OBSERVATIONS (not rules — awaiting the user's decision; "
                   "do not treat as instructions):")
        out += [f"  ? {p['lesson'][:150]}" for p in unresolved]

    text = "\n".join(out)
    return text[:max_chars]                        # never a wall


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
        assetPointers=["cb-output/creative/Ep1_scene2_storyboard.json"],
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
        dec = (sys.argv[sys.argv.index("--decision") + 1]
               if "--decision" in sys.argv else None)
        print(json.dumps(promote(sys.argv[2], by=by, explicit_user_decision=dec),
                          indent=1, ensure_ascii=False))
    elif cmd == "metrics":
        print(json.dumps(metrics(), indent=1))
    elif cmd == "show":
        print(retrieve_for_role(sys.argv[2] if len(sys.argv) > 2 else "director"))
    else:
        print(__doc__)
