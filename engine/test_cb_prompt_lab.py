import hashlib
import json
import pathlib

import pytest

import cb_db
import cb_prompt_lab
import cb_render


ANIMATION_PROMPT = (
    "Exact opening frame: @图1 preserves Fuzzby's canon identity and relative scale in a "
    "wide foreground composition. Fuzzby reaches for the box because it tips, then blinks "
    "and holds a worried breath before pulling it back. The locked 50mm camera begins still, "
    "then makes one slow dolly as his shoulders soften. Warm rim lighting defines the fur "
    "and polished wood material. The shot ends on a clean final frame with Fuzzby screen left."
)


def test_animation_analysis_is_deterministic_and_clause_grounded():
    first = cb_prompt_lab.analyze_prompt(ANIMATION_PROMPT, "animation")
    second = cb_prompt_lab.analyze_prompt(ANIMATION_PROMPT, "animation")

    assert first == second
    assert first["promptHash"] == hashlib.sha256(ANIMATION_PROMPT.encode()).hexdigest()
    assert first["providerCalled"] is False
    assert first["features"]["hasOpening"] is True
    assert first["features"]["hasLanding"] is True
    assert first["dimensions"]["physicalCausality"]["score"] == 2
    assert first["dimensions"]["identityAndReferenceUse"]["score"] == 2
    assert all(item["evidence"] for item in first["dimensions"].values()
               if item["applicable"])


def test_keyframe_analysis_marks_motion_only_dimensions_not_applicable():
    result = cb_prompt_lab.analyze_prompt(
        "Exact opening frame: @图1 preserves canon identity in a medium composition. "
        "A worried glance and raised shoulder hold against soft rim lighting.",
        "keyframe",
    )

    assert result["dimensions"]["physicalCausality"]["applicable"] is False
    assert result["dimensions"]["physicalCausality"]["score"] is None
    assert result["dimensions"]["timingAndReaction"]["applicable"] is False
    assert result["maximum"] == 12


def test_analysis_flags_conflicts_density_and_locked_dialogue_leak():
    prompt = (
        "Camera is locked with no camera movement. Camera zooms and pans. "
        "No glow, never drift, avoid changes, do not alter identity, without extra props, "
        "no text, never add wings. Zenny says I trust my sight."
    )
    result = cb_prompt_lab.analyze_prompt(
        prompt, "animation", [{"exactText": "I trust my sight"}])
    codes = {item["code"] for item in result["warnings"]}

    assert {"camera-conflict", "negative-density", "dialogue-leak",
            "missing-opening", "missing-landing"}.issubset(codes)


def test_seedance_authoring_contract_accepts_role_mapped_stages_and_audio_lock():
    prompt = """ENGLISH DIALOGUE ONLY, spoken in English. @Audio1 is the sole source of dialogue, voice, performance and timing. Fuzzby is the only speaker; Zenny's mouth stays closed.
[Generation Goal]
Generate a comic reference-to-video shot in which Fuzzby's proud flight becomes a wobble and a recovered pose.
[Reference Roles]
@图1 only defines the exact first-frame composition, poses and camera direction; do not use any text labels.
@图2 only defines Fuzzby's identity and scale; do not use its background or composition.
@图3 only defines Zenny's identity and scale; do not use its background or composition.
@Audio1 is the sole source of Fuzzby's English dialogue, voice, performance and timing.
[Stage 1]
Initial state: begin on @图1 with Fuzzby left and Zenny right.
Primary event: Fuzzby drives forward, clips the flower because he overcommits, and the bending stem redirects him.
End state: Fuzzby hangs off balance above the bent flower while Zenny remains on her original bloom.
[Stage 2]
Continue from the previous stage: identities, positions and the bent flower remain unchanged.
Primary event: the stem rebounds, Fuzzby recovers into a proud pose, and Zenny answers with a restrained eye movement.
End state: Fuzzby holds the pose screen left while Zenny remains screen right with her mouth closed.
[Maintain Consistency]
Keep both identities, relative scale, flower ownership, screen direction, light direction and audio relationships stable.
[Audio]
Use @Audio1 exactly. Fuzzby speaks in English; Zenny remains silent and her mouth stays closed. Preserve ambience and action effects. The track has cues at 1.6-3.9s and 8.2-9.1s; these are audio cues, not storyboard stages."""
    references = [
        {"assetTag": "@图1", "role": "opening_frame"},
        {"assetTag": "@图2", "role": "character_identity"},
        {"assetTag": "@图3", "role": "character_identity"},
        {"assetTag": "@Audio1", "role": "audio"},
    ]
    result = cb_prompt_lab.analyze_seedance_prompt_contract(
        prompt, reference_contract=references, duration_sec=12,
        dialogue_lines=[{"speaker": "FUZZBY", "exactText": "Nailed it."}],
        stage_plan=[{"stageNumber": 1}, {"stageNumber": 2}],
    )

    assert result["status"] == "ready"
    assert result["score"] == result["maximum"]
    assert result["referenceCount"] == 4
    assert result["stageCount"] == 2
    assert result["providerCalled"] is False
    assert next(check for check in result["checks"] if check["code"] == "pacing")["status"] == "pass"


def test_seedance_contract_accepts_official_lark_30_second_grammar_with_studio_locks():
    prompt = """ENGLISH DIALOGUE ONLY. @Audio1 is the sole source of English dialogue, voice, performance and timing. Fuzzby is the only speaker; Zenny stays silent with her mouth closed.
[Multimodal Reference Layer]
@Image1 only defines the exact first-frame composition and character positions; do not use its text labels.
@Image2 only defines Fuzzby's identity, proportions and materials; do not use its background.
@Audio1 is the sole source of Fuzzby's English voice, performance and timing.
[One-Sentence Summary]
Fuzzby's confident meadow flight becomes a physical wobble and a proudly disguised recovery in a cinematic comic shot.
[Global Settings]
Environment and texture: tactile flower meadow in clear morning light.
Visual style: premium stylised 3D animation with readable depth and restrained lighting.
Camera language: one motivated wide follow with a gentle push for the reaction.
Character styling: preserve the approved Fuzzby design from @Image2.
Performance core: bright confidence tightens into a tiny private flinch.
Prohibited items: no extra dialogue, subtitles, default BGM, duplicate characters or prop drift.
[Timestamp Script Storyboard]
Stage 1: 0-8s [Confident approach]
Initial state: begin exactly on @Image1 with Fuzzby screen left.
Action/Expression: Fuzzby accelerates, overcommits and loads the flower stem with his paw.
Emotion/Camera Analysis: the held wide frame lets the audience understand the physical cause before he does.
End state: the bent flower holds Fuzzby visibly off balance.
Stage 2: 8-18s [Recovery and denial]
Continue from the previous stage: identity, bent flower and screen direction remain unchanged.
Action/Expression: the stem rebounds, Fuzzby catches himself and converts the mistake into a proud pose.
Emotion/Camera Analysis: a restrained push and delayed eye flick reveal that he knows exactly what happened.
End state: Fuzzby holds the readable pose screen left while Zenny remains silent off his eyeline.
[Global Supplement]
Throughout, keep identity, relative scale, flower ownership, axis, light direction and the final handoff stable.
[Audio]
Use @Audio1 exactly for Fuzzby. Zenny remains silent with her mouth closed; preserve meadow ambience and action effects."""
    result = cb_prompt_lab.analyze_seedance_prompt_contract(
        prompt,
        reference_contract=[
            {"assetTag": "@Image1", "role": "opening_frame"},
            {"assetTag": "@Image2", "role": "character_identity"},
            {"assetTag": "@Audio1", "role": "audio"},
        ],
        duration_sec=18,
        dialogue_lines=[{"speaker": "FUZZBY", "exactText": "Nailed it."}],
        stage_plan=[{"stageNumber": 1}, {"stageNumber": 2}],
    )

    assert result["status"] == "ready"
    assert result["stageCount"] == 2
    assert result["source"]["lastUpdated"] == "2026-08-07"
    assert result["source"]["url"].startswith("https://docs.byteplus.com/")
    assert result["source"]["larkUrl"].startswith("https://bytedance.larkoffice.com/")
    assert result["guideLimits"]["maxImages"] == 30
    assert result["guideLimits"]["maxCombinedInputs"] == 50
    assert result["guideLimits"]["betaLongVideoDurationSec"]["maximum"] == 180
    assert "not a frame-accurate" in result["guideSemantics"]["timestampControl"]
    assert "not a qualified Studio API route" in result["guideSemantics"]["longVideoRoute"]
    assert "requires at least one image or video" in result["guideSemantics"]["audioOnly"]
    assert result["authorityScores"]["official-guide"]["score"] == result["authorityScores"]["official-guide"]["maximum"]
    assert result["authorityScores"]["studio-policy"]["score"] == result["authorityScores"]["studio-policy"]["maximum"]


def test_seedance_authoring_contract_returns_specific_repairs_without_gating():
    result = cb_prompt_lab.analyze_seedance_prompt_contract(
        "@图1 appears here. Shot 1: Make it cinematic. Duration: 30 seconds at 16:9.",
        reference_contract=[{"assetTag": "@图1", "role": "opening_frame"}],
        duration_sec=31,
    )
    failed = {item["code"] for item in result["checks"]
              if item["status"] == "needs-work"}

    assert result["status"] == "needs-work"
    assert {"goal", "reference-roles", "stages", "stage-end-states",
            "consistency", "audio", "request-parameters", "guide-duration"}.issubset(failed)
    assert result["repairActions"]
    assert result["advisoryOnly"] is True


def test_rating_contract_requires_every_applicable_dimension():
    scores = {name: 2 for name in cb_prompt_lab.KEYFRAME_DIMENSIONS}
    clean, overall, note = cb_prompt_lab.validate_rating(
        "keyframe", scores, "lands", "Strong silhouette")
    assert clean == scores and overall == "lands" and note == "Strong silhouette"

    quick_scores, quick_overall, quick_note = cb_prompt_lab.validate_rating(
        "keyframe", {}, "partial", "The expression is close.")
    assert quick_scores == {}
    assert quick_overall == "partial"
    assert quick_note == "The expression is close."

    with pytest.raises(ValueError, match="missing"):
        cb_prompt_lab.validate_rating("keyframe", {"beatDelivery": 2}, "lands")
    with pytest.raises(ValueError, match="0 to 2"):
        cb_prompt_lab.validate_rating(
            "keyframe", {**scores, "beatDelivery": 3}, "lands")


def test_keyframe_prompt_contract_detects_record_tampering():
    pkg = {"continuityLedger": [{
        "shotId": "S1", "departmentWork": {"cinematography": {"approved": {
            "output": {"providerPrompt": "Exact approved keyframe prompt"}}}},
    }]}
    shot = {"shotId": "S1", "keyframePrompt": "fallback"}
    contract = cb_render._keyframe_prompt_contract(
        pkg, shot, "Exact approved keyframe prompt")
    assert cb_render._prompt_contract_is_exact(contract) is True

    changed = {**contract, "promptSource": "changed-after-generation"}
    assert cb_render._prompt_contract_is_exact(changed) is False


def test_evidence_summary_refuses_to_overclaim_from_one_shot():
    records = [
        {"shotId": "S1", "promptHash": "a", "scores": {"beatDelivery": 0},
         "createdAt": "2026-01-01"},
        {"shotId": "S1", "promptHash": "b", "scores": {"beatDelivery": 2},
         "createdAt": "2026-01-02"},
    ]
    early = cb_prompt_lab.summarize_ratings(records, current_prompt_hash="b")
    assert early["evidenceStatus"] == "early-signal"
    assert early["causalClaim"] is False
    assert early["versionComparison"]["delta"] == 2.0

    records.append({"shotId": "S2", "promptHash": "b", "scores": {"beatDelivery": 1},
                    "createdAt": "2026-01-03"})
    repeated = cb_prompt_lab.summarize_ratings(records, current_prompt_hash="b")
    assert repeated["evidenceStatus"] == "repeatable-signal"
    assert repeated["distinctShots"] == 2

    records.append({"shotId": "S3", "promptHash": "", "scores": {"beatDelivery": 0},
                    "createdAt": "2026-01-04", "learningEligible": False})
    mixed = cb_prompt_lab.summarize_ratings(records, current_prompt_hash="b")
    assert mixed["ratingCount"] == 4
    assert mixed["promptLearningCount"] == 3
    assert mixed["qualityOnlyCount"] == 1
    assert mixed["distinctShots"] == 2


def test_historical_feedback_is_tagged_but_never_scored():
    ledger = {
        "rejections": [{
            "batchId": "batch-1", "correction": "Wrong angle and the deadpan smile is too warm",
            "reviewed_by": "Julian", "at": "2026-01-01", "category": "action-timing",
        }],
        "departmentWork": {"animation": {"approved": {
            "reviewedBy": "Julian", "decisionAt": "2026-01-02",
            "note": "Delay the reaction by one second.",
        }}},
    }

    feedback = cb_render._prompt_lab_feedback(ledger, "animation")

    assert len(feedback) == 2
    assert all(item["scoreInferred"] is False for item in feedback)
    assert "camera-and-composition" in feedback[1]["topics"]
    assert "acting-and-emotion" in feedback[1]["topics"]


def test_direction_correlation_never_mixes_outcomes_between_batches():
    shot = {
        "purpose": "The joke lands when Fuzzby thinks the crash was a triumph.",
        "performanceAssignment": "He checks who saw, then strikes a superhero pose.",
        "physicalStaging": {"contactAndWeight": "The flower bows and rebounds."},
        "dialogueTimingProse": "@Audio1 lands on the pose.",
        "camera": "Hold wide, then dolly to Zenny.",
        "openingPose": "Both bees share the opening frame.",
        "referenceRolesProse": "Use the Fuzzby and Zenny identity references.",
        "visualPayoff": "Zenny stays deadpan, then one mouth corner lifts.",
    }
    analysis = cb_prompt_lab.analyze_prompt(ANIMATION_PROMPT, "animation")
    selected = {
        "candidateId": "C1", "state": "approved",
        "promptAttributionExact": True, "attributionExact": False,
        "promptContract": {"batchId": "batch-2"},
    }
    feedback = [
        {"feedbackId": "old", "kind": "render-comment", "batchId": "batch-1",
         "note": "The crash has no weight.", "topics": ["action-and-physics"]},
        {"feedbackId": "current", "kind": "render-comment", "batchId": "batch-2",
         "note": "Zenny's deadpan is too warm.", "topics": ["acting-and-emotion"]},
    ]
    ledger = {"approval": {"approved": True, "candidate": 1,
                           "reviewed_by": "Julian", "at": "2026-01-02"}}

    correlation = cb_prompt_lab.build_direction_correlation(
        shot, analysis, "animation", selected=selected, ledger=ledger,
        feedback=feedback, prompt_applies_to_render=True,
        prompt_plan_summary="The prompt spends the pace, then lands on Zenny's deadpan.")

    assert correlation["scope"]["batchId"] == "batch-2"
    assert correlation["scope"]["outcomeBinding"] == "commented"
    assert [item["feedbackId"] for item in correlation["linkedComments"]] == ["current"]
    assert [item["feedbackId"] for item in correlation["priorAttempts"]] == ["old"]
    physics = next(item for item in correlation["rows"] if item["key"] == "physics")
    finish = next(item for item in correlation["rows"] if item["key"] == "finish")
    assert physics["observedResult"]["status"] == "not-rated"
    assert finish["observedResult"]["status"] == "commented"
    assert finish["observedResult"]["scoreInferredFromComment"] is False
    assert correlation["creativeLoop"]["directorWants"]["text"] == shot["purpose"]
    assert correlation["creativeLoop"]["promptBuiltToDeliver"]["text"].startswith(
        "The prompt spends the pace")
    assert correlation["causalClaim"] is False


def test_render_rating_is_append_only_and_bound_to_prompt_and_asset_bytes(
        tmp_path, monkeypatch):
    database = tmp_path / "state.sqlite3"
    monkeypatch.setenv("CB_STUDIO_STATE_DB", str(database))
    engine = tmp_path / "engine"
    engine.mkdir()
    monkeypatch.setattr(cb_render, "HERE", engine)
    asset = tmp_path / "candidate.mp4"
    asset.write_bytes(b"first-render-bytes")
    prompt_hash = hashlib.sha256(ANIMATION_PROMPT.encode()).hexdigest()
    contract = {
        "prompt": ANIMATION_PROMPT,
        "promptHash": prompt_hash,
        "promptSource": "animation-director-approved",
        "provider": "fal",
        "providerModelId": "seedance-test",
        "modelVersion": "test-1",
        "attributionExact": True,
    }
    expected_asset_hash = hashlib.sha256(asset.read_bytes()).hexdigest()

    def snapshot(*_args, **_kwargs):
        return {
            "selected": {
                "candidateId": "C1", "path": str(asset),
                "attributionExact": True, "promptContract": contract,
                "expectedAssetHash": expected_asset_hash,
            },
            "promptContract": contract,
            "shot": {"dialogueLines": []},
        }

    monkeypatch.setattr(cb_render, "_prompt_lab_snapshot", snapshot)
    scores = {name: 2 for name in cb_prompt_lab.ANIMATION_DIMENSIONS}
    first = cb_render.rate_prompt_render(
        "1", "1.B1.S1", "animation", "C1", scores, "lands", episode="EpT")
    second = cb_render.rate_prompt_render(
        "1", "1.B1.S1", "animation", "C1", scores, "partial", episode="EpT")

    stored = cb_db.list_render_ratings(
        engine.parent, episode="EpT", scene="1", shot_id="1.B1.S1",
        artifact_type="animation")
    assert len(stored) == 2
    assert first["ratingId"] != second["ratingId"]
    assert first["promptHash"] == second["promptHash"] == prompt_hash
    assert first["assetHash"] == second["assetHash"] == expected_asset_hash
    assert stored[0]["overallRead"] == "partial"

    asset.write_bytes(b"altered-after-generation")
    with pytest.raises(cb_render.Refused, match="render bytes no longer match"):
        cb_render.rate_prompt_render(
            "1", "1.B1.S1", "animation", "C1", scores, "miss", episode="EpT")


def test_render_rating_saves_legacy_media_as_quality_only(tmp_path, monkeypatch):
    monkeypatch.setenv("CB_STUDIO_STATE_DB", str(tmp_path / "state.sqlite3"))
    engine = tmp_path / "engine"
    engine.mkdir()
    monkeypatch.setattr(cb_render, "HERE", engine)
    asset = tmp_path / "old.png"
    asset.write_bytes(b"surviving-legacy-render")
    monkeypatch.setattr(cb_render, "_prompt_lab_snapshot", lambda *_args, **_kwargs: {
        "selected": {"candidateId": "approved", "path": str(asset),
                     "attributionExact": False, "promptContract": None,
                     "provenanceGrade": "asset-only", "expectedAssetHash": None},
        "shot": {"dialogueLines": []},
    })
    record = cb_render.rate_prompt_render(
        "1", "1.B1.S1", "keyframe", "approved", {}, "partial",
        "The overall image is close.", episode="EpT")

    assert record["learningEligible"] is False
    assert record["provenanceGrade"] == "asset-only"
    assert record["promptSource"] == "unattributed-legacy-render"
    assert record["scores"] == {}
    stored = cb_db.list_render_ratings(engine.parent, episode="EpT")
    assert len(stored) == 1 and stored[0]["learningEligible"] is False


def test_prompt_lab_status_uses_the_sealed_animation_prompt_without_provider_calls(
        tmp_path, monkeypatch):
    monkeypatch.setenv("CB_STUDIO_STATE_DB", str(tmp_path / "state.sqlite3"))
    engine = tmp_path / "engine"
    engine.mkdir()
    monkeypatch.setattr(cb_render, "HERE", engine)
    asset = tmp_path / "take.mp4"
    asset.write_bytes(b"render")
    envelope = {
        "prompt": ANIMATION_PROMPT,
        "promptSource": "animation-director-approved",
        "provider": "fal",
        "providerModelId": "seedance-test",
        "modelVersion": "test-1",
    }
    envelope_hash = hashlib.sha256(json.dumps(
        envelope, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    asset_hash = hashlib.sha256(asset.read_bytes()).hexdigest()
    pkg = {
        "shots": [{"shotId": "1.B1.S1", "sourceType": "opener",
                   "purpose": "Fuzzby saves the box and tries to look brave.",
                   "dialogueLines": [], "seedancePrompt": "newer working prompt"}],
        "continuityLedger": [{
            "shotId": "1.B1.S1", "status": "candidates-pending",
            "candidatePaths": [str(asset)], "batchId": "batch-1",
            "batch": {"batchId": "batch-1", "envelope": envelope,
                      "envelopeHash": envelope_hash,
                      "candidateHashes": [{"path": str(asset), "sha256": asset_hash}]},
        }],
    }
    monkeypatch.setattr(cb_render, "load_pkg", lambda *_args, **_kwargs: (pkg, tmp_path / "pkg.json"))
    monkeypatch.setattr(
        cb_render.cb_providers, "video_model",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("provider registry should not be consulted for a sealed render")))

    status = cb_render.prompt_lab_status(
        "1", "1.B1.S1", "animation", "EpT", candidate_id="C1")

    assert status["canRate"] is True
    assert status["promptContract"]["prompt"] == ANIMATION_PROMPT
    assert status["promptContract"]["promptSource"] == "animation-director-approved"
    assert status["selectedCandidateId"] == "C1"
    assert status["canTeachPrompt"] is True
    assert status["zeroSpend"] is True and status["approvalChanged"] is False
    assert status["correlation"]["scope"]["batchId"] == "batch-1"
    assert status["correlation"]["scope"]["promptBinding"] == "sealed-batch-prompt"
    assert status["correlation"]["rows"][0]["directorWish"]["status"] == "recorded"
    assert status["seedancePromptContract"]["providerAvailabilityChecked"] is False


def test_studio_exposes_prompt_lab_without_replacing_approval_controls():
    root = pathlib.Path(__file__).resolve().parents[1]
    server = (root / "cb-studio" / "serve.py").read_text()
    app = (root / "cb-studio" / "app.html").read_text()

    assert 'urlsplit(self.path).path == "/api/prompt-lab"' in server
    assert 'self.path == "/api/prompt-lab-rate"' in server
    assert "function promptLabPanelHTML" in app
    assert "Quality evidence only" in app
    assert "Director wanted" in app
    assert "Prompt instruction" in app
    assert "Observed result" in app
    assert "Seedance prompt structure" in app
    assert "Seedance authoring contract" in app
    assert "Audit details" in app
    assert "Earlier attempt comments" in app
    assert "function plUseFeedback" in app
    assert "Render Review" in app and "function renderPromptReviewWorkspace" in app
    assert "openScene(scId,true)" in app and "await renderControl()" in app
    assert "shRun('approve'" in app and "shRun('approve-keyframe'" in app
    assert "Story · Prompt · Result · Next" in app
    assert 'if(asset.state==="rejected")' in app
    assert 'asset.state==="rejected"?"Build replacement"' in app
    assert "Build replacement keyframe" in app
    assert "function shRender(shotId)" in app
    assert '<button class="btn render-primary" onclick="shRender(' in app
    assert '<summary>Studio details</summary>' in app
    assert 'class="praildetails"' in app
    assert "Accept take" in app and ">Iterate</button>" in app
    assert "function referenceManifestHTML" in app
    assert "Keyframe references" in app and "Animation references" in app
    assert "/api/shot-references" in app and "/api/shot-references" in server
    assert "function storyReferenceCheckHTML" in app
    assert "Reference Check" in app and "Carried Scene 1 package" in app
    assert "loadStoryReferenceCheck(true,this.value)" in app
    assert '<summary>Prompt checks</summary>' in app
    assert '<summary>Review result</summary>' in app
