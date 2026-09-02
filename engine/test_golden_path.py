#!/usr/bin/env python3
"""test_golden_path.py — THE GOLDEN PATH, outcome-based, zero cost.

WHAT THESE TESTS PROVE — AND WHAT THEY NEVER PROVE (Julian's probabilistic-model
correction, 2026-07-16): this suite proves ORCHESTRATION, VALIDATION, SPENDING CONTROL and
STATE TRANSITIONS. Seedance is a probabilistic generator; nothing here is, or can be,
evidence of creative render quality — the product is an approved shot selected from a
controlled candidate set by a human, never a "perfect prompt".

Runs the entire hybrid pipeline end to end against a synthetic 3-shot scene with every
provider mocked: design-package -> voice -> timing slate -> keyframe -> candidate batch ->
select -> relay batch (off the harvested frame) -> Director Review -> post master -> final
approval. Asserts:

  1. every locked dialogue line reaches the voice provider exactly once, and the render
     receives one attributed placement marker while @Audio1 owns performance authority
  2. a candidate batch REFUSES without explicit spend approval, and with it generates N
     candidates from the IDENTICAL prompt/references/audio, anchor first, in slot order
  3. approval selects ONE candidate, archives the rest, harvests its final frame; a relay
     batch fires from that frame — and refuses when the source is not approved
  4. a failed-validation package cannot fire anything
  5. a pending batch cannot be re-fired past
  6. batch rejection archives everything, the reroll uses the UNCHANGED package, and two
     failed batches hard-stop the shot as model-limited
  7. the QC-passed final master contains every approved shot, in order, and is not final
     until a separate human review approves it

    pytest test_golden_path.py -q
"""
import hashlib, json, os, pathlib, shutil, threading
import pytest

import cb_engine as E
import cb_render as R
import cb_canon
import cb_departments
import cb_voice_director


TEST_CANON_DIGESTS = {name: (name[0] * 64) for name in (
    "story", "storyboard", "look", "cinematography", "voice",
    "animation", "review", "post")}


def _voice_direction_output(shot):
    lines = []
    for idx, line in enumerate(shot.get("dialogueLines") or []):
        exact = line["exactText"]
        occurrence_id = line.get("dialogueOccurrenceId") or (
            f"{shot['shotId']}.dialogue.{idx + 1}")
        source_event_id = line.get("sourceEventId") or occurrence_id
        lines.append({
            "dialogueOccurrenceId": occurrence_id,
            "sourceEventId": source_event_id,
            "speaker": line["speaker"], "character": line["speaker"],
            "exactDialogue": exact, "performedText": exact,
            "dramaticIntention": "Make the listener accept the action.",
            "subtext": "The body carries the hidden truth.",
            "cadenceAndBreath": "Character-specific and breath-led.",
            "timingAndBody": "Speech follows the physical beat.",
            "archetypeId": "false-triumph-button",
            "performanceQuestions": {
                "intention": "Make the listener accept the action.",
                "subtext": "The body carries the hidden truth.",
                "thoughtBefore": "Commit to the action.",
                "changeDuring": "Certainty becomes exposed.",
                "operativeWords": [exact.split()[0]],
            },
            "physicalState": "The approved body action is already in progress.",
            "emotionalState": {"entry": "Committed", "exit": "Exposed"},
            "listener": "The scene partner",
            "bodyVoiceRelationship": "The voice follows and interprets the body action.",
            "previousText": "The approved preceding action supplies context.",
            "startsAtSec": 0.5, "estimatedDurationSec": 1.0,
            "pauseReasons": (["Fixture punctuation carries a motivated thought pause."]
                             if "…" in exact or "—" in exact else []),
            "tagPurposes": {},
            "takeRecipes": [{"recipeId": "fixture", "label": "Fixture",
                             "performedText": exact, "primary": True,
                             "takesCount": 2 if len(exact.split()) <= 4 else 1}],
        })
    return {"shotId": shot["shotId"], "sceneIntention": "Fixture direction.",
            "lines": lines}


def _test_canon_status(episode=None, cast=None, root=None):
    return {
        "current": True, "episodeReady": bool(episode),
        "manifestDigest": "m" * 64, "profileDigests": TEST_CANON_DIGESTS,
        "blockers": [], "episodeBlockers": [], "warnings": [],
    }


def _test_seedance_25_contract(**kwargs):
    """Explicit zero-network 2.5 contract for orchestration tests only."""
    assert kwargs.get("model_id") in (None, "fal-seedance-2.5")
    duration = int(kwargs["duration"])
    assert 4 <= duration <= 30
    return {
        "providerModelId": "fal-seedance-2.5",
        "provider": "fal",
        "modelVersion": "2.5",
        "transport": "fal-subscribe",
        "mode": "reference-to-video",
        "endpoint": "bytedance/seedance-2.5/reference-to-video",
        "resolution": kwargs.get("resolution", "720p"),
        "duration": duration,
        "costRateKey": "seedance_25_fal_720p_per_sec",
        "capabilityVerifiedAt": "2026-08-07-test-fixture",
        "capabilitySource": "test-fixture",
    }


def _keyframe_conformance_output(context=None, verdict="pass"):
    context = context or {}
    expected = list(context.get("expectedCharacters") or ["Fuzzby", "Zenny"])
    score = 2 if verdict == "pass" else 0
    dimension = {
        "score": score,
        "visibleEvidence": ("The synthetic fixture passes." if score == 2 else
                            "The synthetic fixture visibly fails."),
        "correction": "" if score == 2 else "Restore the locked identities and 14:12 scale.",
    }
    return R.cb_departments.KeyframeConformanceReview.model_validate({
        "verdict": verdict,
        "expectedCharacters": expected,
        "detectedCharacters": (expected if verdict == "pass" else expected[:1]),
        "expectedSubjectCount": len(expected),
        "subjectCount": len(expected) if verdict == "pass" else min(1, len(expected)),
        "summary": ("Synthetic identity and scale pass." if verdict == "pass" else
                    "Zenny is missing and relative scale is wrong."),
        "identityAndDistinguishability": dimension,
        "relativeScaleAndGeography": dimension,
        "anatomyAndSilhouette": dimension,
        "actionReadyComposition": dimension,
        "forbiddenContent": dimension,
        "recommendedCorrection": ("" if verdict == "pass" else
                                  "Restore Zenny and the locked 14:12 size relationship."),
    })


@pytest.fixture(autouse=True)
def isolated_canon(monkeypatch):
    monkeypatch.setattr(cb_canon, "status", _test_canon_status)
    monkeypatch.setattr(cb_canon, "require_locked", _test_canon_status)
    monkeypatch.setattr(cb_canon, "profile_digest",
                        lambda profile, **kwargs: TEST_CANON_DIGESTS[profile])
    monkeypatch.setattr(cb_canon, "source_hashes",
                        lambda profile, root=None: {"fixture": TEST_CANON_DIGESTS[profile]})
    monkeypatch.setattr(cb_canon, "story_context", lambda cast, episode, root=None: {
        "canonProfile": "story",
        "canonProfileDigest": TEST_CANON_DIGESTS["story"],
        "sourceHashes": {"fixture": TEST_CANON_DIGESTS["story"]},
    })
    monkeypatch.setattr(R.cb_providers, "request_contract", _test_seedance_25_contract)
    cards = cb_voice_director.voice_cards()
    cards["characters"]["Fuzzby"]["voiceId"] = "voice-fuzzby"
    cards["characters"]["Zenny"]["voiceId"] = "voice-zenny"
    monkeypatch.setattr(R.cb_voice_director, "voice_cards", lambda: cards)
    monkeypatch.setattr(
        R.cb_departments, "review_keyframe_conformance",
        lambda context, images, **kwargs: _keyframe_conformance_output(context, "pass"))


# ── the synthetic scene: opener w/ dialogue, relay w/ dialogue, silent relay ────────────
CFG = {"Fuzzby": {"sizeRank": 2, "heightIn": 14, "avoid": "bee", "voiceId": "voice-fuzzby",
                   "anchor": "media/refs/CB_Fuzzby.jpeg"},
       "Zenny": {"sizeRank": 3, "heightIn": 12, "avoid": "bee", "voiceId": "voice-zenny",
                  "anchor": "media/refs/CB_Zenny.jpeg"}}


def _install_provider_identity_fixture(monkeypatch, engine):
    """Keep orchestration tests isolated from the real show's provider identity art."""
    identity_paths = {}
    packs = {
        "Fuzzby": {
            "schemaVersion": 1, "source": "fixture",
            "providerViews": {"default": {"view": "front", "crop": [0, 0, 1, 1]}},
            "distinguishingFeatures": ["tan nose", "larger 14-inch proportions"],
            "mustNotBorrow": ["Zenny eyelashes or blush"],
        },
        "Zenny": {
            "schemaVersion": 1, "source": "fixture",
            "providerViews": {"default": {"view": "front", "crop": [0, 0, 1, 1]}},
            "distinguishingFeatures": ["long eyelashes", "smaller 12-inch proportions"],
            "mustNotBorrow": ["Fuzzby's tan nose"],
        },
    }
    for name in packs:
        path = engine / "media" / "refs" / f"{name}_provider_front.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(("PROVIDER-SAFE-" + name).encode())
        identity_paths[name] = path

    monkeypatch.setattr(R, "_identity_packs_cfg", lambda: packs)

    def provider_record(name, characters_cfg, usage="keyframe", **kwargs):
        canonical = R._resolve_char(name, characters_cfg)
        pack = packs[canonical]
        return {
            "character": canonical, "usage": usage, "view": "front",
            "path": str(identity_paths[canonical]),
            "fileName": identity_paths[canonical].name,
            "derived": True, "providerSafe": True, "singleSubject": True,
            "contractHash": "fixture-" + canonical.lower(),
            "sourceSha256": hashlib.sha256(identity_paths[canonical].read_bytes()).hexdigest(),
            "distinguishingFeatures": pack["distinguishingFeatures"],
            "mustNotBorrow": pack["mustNotBorrow"],
        }

    monkeypatch.setattr(R, "_provider_identity_record", provider_record)

BEATS = [
    {"beatCode": "1.B1", "comedyMode": "BIG", "storyBeat": "The crash gag.",
     "cuts": [{"framing": "wide", "action": "Fuzzby rockets.",
               "dialogue": "FUZZBY: Nailed it.", "delivery": "proud"},
              {"framing": "two", "action": "Zenny deadpans.",
               "dialogue": "ZENNY: Fuzzby… why are you humming?", "delivery": "dry"}]},
]


def _state(chars, marks=()):
    return E.ContinuityState(lighting="warm", cameraSide="left", characters=[
        E.CharacterState(character=c, screenZone="frame-left", facing="right",
                          pose="hover", expression="bright",
                          visibleMarks=list(marks), heldProps=[]) for c in chars])


def _mkshot(shot_id, source, src_id, lines, binding, staging=None):
    return E.Shot(shotId=shot_id, beatCode="1.B1", durationSec=6.0, purpose="the gag",
                  performanceAssignment="Fuzzby rockets past, clips the leaf, rebounds proudly.",
                  camera="Wide tracking, bee height", openingPose="Fuzzby outside the flower, wound up",
                  sourceType=source, sourceShotId=src_id,
                  cutInMotivation=None if src_id is None and source == "opener" and shot_id.endswith("S1") else "matched action",
                  dialogueBinding=binding, dialogueLines=lines,
                  visualPayoff="He nearly grazes the leaf", physicalStaging=staging,
                  prohibited=[], charactersInFrame=["Fuzzby", "Zenny"],
                  continuityIn=_state(["Fuzzby", "Zenny"]),
                  continuityOut=_state(["Fuzzby", "Zenny"], marks=["pollen dust"])
                  if shot_id.endswith("S1") else
                  E.ContinuityState(lighting="warm", cameraSide="left", characters=[
                      E.CharacterState(character=c, screenZone="frame-left", facing="right",
                                        pose="hover", expression="bright",
                                        visibleMarks=["pollen dust"], heldProps=[])
                      for c in ["Fuzzby", "Zenny"]]))


def _line(speaker, text, start, end):
    return E.DialogueLine(speaker=speaker, exactText=text, delivery="in character",
                          startSec=start, endSec=end)


STAGING = E.PhysicalStaging(staysVisible="full silhouette", contactAndWeight="chest to leaf",
                             payoffShape="upward pop", prohibitedStaging=["vanishing"])


def _cinematography_output(shot):
    """Typed current DP direction used by the direct stage-anchor compiler."""
    cast = list(shot.get("charactersInFrame") or [])
    placements = [
        {"character": "Fuzzby", "centerX": 0.36, "centerY": 0.43,
         "apparentScale": 1.0, "depthPlane": 1, "bodyAngleDegrees": -24.0,
         "facing": "screen-right", "pose": "committed climbing flight"},
        {"character": "Zenny", "centerX": 0.68, "centerY": 0.48,
         "apparentScale": 1.0, "depthPlane": 1, "bodyAngleDegrees": -3.0,
         "facing": "screen-right", "pose": "clean level glide"},
    ]
    placements = [item for item in placements if item["character"] in cast]
    style_version, style_text = cb_departments.canonical_style_paragraph()
    return {
        "providerPrompt": shot.get("keyframePrompt") or
                          "Maintain the approved inherited opening frame exactly.",
        "audienceRead": "Fuzzby's physical chaos is measured against Zenny's calm.",
        "composition": "Fuzzby remains frame-left and Zenny frame-right.",
        "lensAndCameraRelationship": "Bee-height camera preserves readable silhouettes.",
        "lightingAndDepth": "Warm daylight and layered flower depth remain stable.",
        "geography": [
            "The flower corridor travels frame-left to frame-right at bee height, "
            "with the springy leaf visible on the route."],
        "charactersInFrame": list(shot.get("charactersInFrame") or []),
        "canonicalStyleVersion": style_version,
        "canonicalStyleParagraph": style_text,
        "negativeSpace": ["Keep frame-right lead room open for travel."],
        "openingFrameLayout": {
            "aspectRatio": "16:9", "referenceCharacter": cast[0],
            "referenceHeightFraction": 0.28, "sameDepth": True,
            "placements": placements,
        },
        "continuityProtections": ["No identity or relative-scale drift."],
    }


def _build_package(tmp, valid=True):
    """Design + compile a real package through cb_engine's own compilers (no LLM — the
    design object is constructed directly), then place it where cb_render loads it."""
    s1 = _mkshot("1.B1.S1", "opener", None,
                 [_line("Fuzzby", "Nailed it.", 1.0, 2.5)],
                 "FUZZBY speaks with breathless pride", staging=STAGING)
    # THE SIMPLIFICATION (2026-07-17): the scene's true first shot has nothing to
    # inherit — typed absence (None), the same mechanical clear design_scene now applies.
    s1.continuityIn = None
    # s2's continuityIn must carry s1's marks (pollen dust) for the validator
    s2 = _mkshot("1.B1.S2", "relay", "1.B1.S1",
                 [_line("Zenny", "Fuzzby… why are you humming?", 1.0, 3.5)],
                 "ZENNY speaks with dry deadpan")
    s2.continuityIn = E.ContinuityState(lighting="warm", cameraSide="left", characters=[
        E.CharacterState(character=c, screenZone="frame-left", facing="right", pose="hover",
                          expression="bright", visibleMarks=["pollen dust"], heldProps=[])
        for c in ["Fuzzby", "Zenny"]])
    s3 = _mkshot("1.B1.S3", "relay", "1.B1.S2", [], None)
    s3.continuityIn = s2.continuityOut.model_copy(deep=True)
    design = E.SceneShotList(
        statement=E.DirectorStatement(audienceFeeling="joy", whoseScene="Fuzzby",
                                       emotionalChange="pride", theLaugh="the crash",
                                       visualSurprise="the leaf", carryForward="the hum"),
        shots=[s1, s2, s3])
    report = E.validate_scene_design(design, BEATS, CFG)
    assert report["passed"], report["issues"]

    shots_out = []
    for sh in design.shots:
        prompt, wc, slots = E.compile_shot_contract(sh, {}, CFG)
        rec = sh.model_dump()
        rec.update(seedancePrompt=prompt, promptWords=wc, referenceSlots=slots,
                   audioBrief=E.compile_audio_brief(sh))
        rec["seedancePrompt"] = R.cb_departments._apply_animation_provider_shell(
            rec["seedancePrompt"], rec)
        rec["promptWords"] = len(rec["seedancePrompt"].split())
        if sh.sourceType == "opener":
            kf, kwc, kslots = E.compile_keyframe_prompt(sh, {}, CFG)
            rec.update(keyframePrompt=kf, keyframePromptWords=kwc,
                       keyframeReferenceSlots=kslots)
        shots_out.append(rec)
    revision = 1
    pkg = {"episode": "EpT", "sceneNumber": "9", "revision": revision, "shots": shots_out,
           "continuityLedger": [E._ledger_entry(s) for s in design.shots],
           "validation": report if valid else {"passed": False, "issues": [
               {"severity": "ERROR", "code": "SYNTH", "path": "x", "message": "forced"}]}}
    by_id = {shot["shotId"]: shot for shot in shots_out}
    for ledger in pkg["continuityLedger"]:
        shot = by_id[ledger["shotId"]]
        ledger["departmentWork"] = {
            "cinematography": {"approved": {
                "packageRevision": revision,
                "output": _cinematography_output(shot)}},
            "voice": {"approved": {
                "packageRevision": revision,
                "output": _voice_direction_output(shot)}},
            "animation": {"approved": {
                "packageRevision": revision,
                "output": {"providerPrompt": shot["seedancePrompt"]}}},
        }
    out = tmp / "cb-output" / "EpT_scene9_production_package.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    json.dump(pkg, open(out, "w"), indent=1)
    return out


# ── the mocked provider estate — records every call, spends nothing ─────────────────────
class Providers:
    def __init__(self):
        self.voice_calls, self.image_calls, self.fire_calls = [], [], []

    def install(self, monkeypatch, tmp):
        import cb_costs
        monkeypatch.setattr(cb_costs, "load_billing_profile", lambda provider=None: {
            "planConfirmed": True, "cadenceConfirmed": True, "plan": "test",
            "billingCadence": "monthly", "cyclePriceUsdExTax": 99.0,
            "creditsPerCycle": 600000,
            "creditsPerCharacter": {"eleven_v3": 1.0},
            "pricingSource": "test", "effectiveDate": "2026-07-16",
        })

        def eleven_dialogue(inputs, out="vo.mp3", **k):
            self.voice_calls.append({"inputs": inputs, "out": out})
            # a REAL (silent) mp3 — the animatic runs genuine ffmpeg over this file, so the
            # mock must produce decodable audio, not a byte stub
            import subprocess as sp
            total_duration = 0.5 * max(1, len(inputs))
            sp.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                    "-t", str(total_duration), "-q:a", "9", out],
                   check=True, capture_output=True)
            duration = total_duration / max(1, len(inputs))
            timing = {
                "schemaVersion": 1,
                "audioSha256": R.cb_audio_timing.file_sha256(out),
                "voiceSegments": [{
                    "dialogueInputIndex": index,
                    "startTimeSec": index * duration,
                    "endTimeSec": (index + 1) * duration,
                } for index in range(len(inputs))],
            }
            pathlib.Path(str(out) + ".dialogue.json").write_text(
                json.dumps(timing), encoding="utf-8")
            return out
        def generate_image(prompt, refs=None, out="kf.png", **k):
            self.image_calls.append({"prompt": prompt, "refs": refs, "out": out})
            pathlib.Path(out).write_bytes(b"PNG")
            return out
        def _fal_upload(path):
            return f"url://{path}"
        def generate_video_seedance_ref(prompt, image_urls, audio_urls=None, out="c.mp4", **k):
            self.fire_calls.append({"prompt": prompt, "image_urls": image_urls,
                                     "audio_urls": audio_urls, "out": out, **k})
            pathlib.Path(out).write_bytes(b"MP4:" + os.path.basename(out).encode())
            return out
        def last_frame(clip, out="last.png"):
            pathlib.Path(out).write_bytes(b"FRAME:" + os.path.basename(clip).encode())
            return out
        monkeypatch.setattr(R.cb_gen, "eleven_dialogue", eleven_dialogue)
        monkeypatch.setattr(R.cb_gen, "generate_image", generate_image)
        monkeypatch.setattr(R.cb_gen, "generate_image_nanobanana_ab", generate_image)
        monkeypatch.setattr(R.cb_gen, "_fal_upload", _fal_upload)
        monkeypatch.setattr(R.cb_gen, "generate_video_seedance_ref", generate_video_seedance_ref)
        monkeypatch.setattr(R.cb_gen, "last_frame", last_frame)
        def restore_approved_hear(provider_clip, voice_path, out):
            pathlib.Path(out).write_bytes(
                pathlib.Path(provider_clip).read_bytes() + b"|APPROVED_HEAR")
            return str(out)
        monkeypatch.setattr(R.cb_post, "replace_guide_dialogue", restore_approved_hear)
        posed = tmp / "engine" / "media" / "reference_controls" / "approved_posed_integration.png"
        posed.parent.mkdir(parents=True, exist_ok=True)
        posed.write_bytes(b"APPROVED-POSED-INTEGRATION")
        posed_record = {
            "path": str(posed), "contractHash": "test-posed-integration",
            "imageSha256": hashlib.sha256(posed.read_bytes()).hexdigest(),
            "zeroSpend": True, "providerCalled": False, "providerInput": True,
        }
        monkeypatch.setattr(
            R, "_load_posed_integration_master", lambda *args, **kwargs: posed_record)
        monkeypatch.setattr(
            R, "_ensure_posed_integration_master", lambda *args, **kwargs: posed_record)
        def build_scene_post(shots, out_root, episode, scene_num, input_signature,
                             platform="youtube", candidate_id=None, music=None,
                             ambience=None):
            """Zero-ffmpeg post adapter with the production manifest contract.

            Media generation is mocked in this orchestration suite, but immutable paths,
            hashes, ordered sources, QC evidence and the signed manifest are all real.
            """
            candidate_id = candidate_id or "test-post-candidate"
            final_dir = pathlib.Path(out_root) / f"{episode}_Scene{scene_num}_{candidate_id}"
            final_dir.mkdir(parents=True)
            ordered = b"".join(pathlib.Path(s["approvedTake"]).read_bytes() for s in shots)
            files = {
                "conformedPicture": ("picture_conformed.mp4", b"CONFORMED:" + ordered),
                "master16x9": (f"master_16x9_{platform}.mp4", b"MASTER16:" + ordered),
                "master9x16": (f"master_9x16_{platform}.mp4", b"MASTER9:" + ordered),
                "captionsSrt": ("captions.srt", "\n".join(
                    line["exactText"] for shot in shots
                    for line in shot.get("dialogueLines") or []).encode("utf-8")),
                "captionsVtt": ("captions.vtt", ("WEBVTT\n\n" + "\n".join(
                    line["exactText"] for shot in shots
                    for line in shot.get("dialogueLines") or [])).encode("utf-8")),
                "programAudio": ("program_audio_24bit.wav", b"PROGRAM-AUDIO"),
            }
            outputs = {}
            for name, (filename, content) in files.items():
                asset = final_dir / filename
                asset.write_bytes(content)
                outputs[name] = {"path": str(asset),
                                 "sha256": hashlib.sha256(content).hexdigest(),
                                 "bytes": len(content)}
            manifest_path = final_dir / "post_manifest.json"
            manifest = {
                "schemaVersion": R.cb_post.POST_SCHEMA_VERSION,
                "policyVersion": R.cb_post.POST_POLICY_VERSION,
                "candidateId": candidate_id,
                "episode": episode,
                "sceneNumber": str(scene_num),
                "builtAt": "2026-07-30T00:00:00+00:00",
                "masteringPlatform": platform,
                "manifestPath": str(manifest_path),
                "inputSignature": input_signature,
                "orderedShots": [{
                    "shotId": shot["shotId"],
                    "approvedTake": str(shot["approvedTake"]),
                    "approvedTakeHash": hashlib.sha256(
                        pathlib.Path(shot["approvedTake"]).read_bytes()).hexdigest(),
                } for shot in shots],
                "conformPlan": [],
                "captionWindows": [line for shot in shots
                                   for line in shot.get("dialogueLines") or []],
                "outputs": outputs,
                "qc": {"passed": True, "checks": {"mockMediaContract": True}},
            }
            manifest["manifestDigest"] = hashlib.sha256(json.dumps(
                manifest, sort_keys=True, ensure_ascii=False,
                separators=(",", ":")).encode()).hexdigest()
            manifest_path.write_text(json.dumps(manifest, indent=1, ensure_ascii=False))
            return manifest
        monkeypatch.setattr(R.cb_post, "build_scene_post", build_scene_post)
        monkeypatch.setattr(R.cb_post, "_dur", lambda p: 6.0)


@pytest.fixture()
def world(monkeypatch, tmp_path):
    """A fully-isolated world mirroring the real repo layout (root/cb-output + root/engine/
    media): package, refs, plate, characters config, mocked providers."""
    prov = Providers()
    prov.install(monkeypatch, tmp_path)
    engine = tmp_path / "engine"
    monkeypatch.setattr(R, "HERE", engine)
    monkeypatch.setattr(R, "MEDIA", engine / "media" / "shots")
    (engine / "media" / "refs").mkdir(parents=True)
    for c in CFG.values():
        (engine / c["anchor"]).write_bytes(b"REF")
    _install_provider_identity_fixture(monkeypatch, engine)
    # NOTE (2026-07-19): a fixed-filename "EpT_S9_plate.png" used to be written here — dead
    # since the 2026-07-18 production-safety directive moved _plate_path to read the Scene
    # Look sidecar's own APPROVED record instead of globbing a conventional filename (never
    # actually exercised by any test before tonight, since every test refused earlier at
    # _require_current_scenelook before reaching _plate_path at all). The real plate file is
    # created below, alongside the scenelook approval record it's read from.
    # THE SCENE LOOK CANON FALLBACK (2026-07-19): _compile_scenelook_prompt reads
    # {root}/shows/crystal-bears/canon/locations.json for episode "EpT" scene "9" — this
    # world has no such file by default, so every path through keyframe_shot (which always
    # calls _require_current_scenelook first) refused with "no canon environment data
    # found," unrelated to whatever each test actually exercises downstream. A minimal,
    # synthetic (not real-show) entry closes that gate the same way the real production
    # shows/crystal-bears/canon/locations.json now does for Ep1.
    canon_dir = tmp_path / "shows" / "crystal-bears" / "canon"
    canon_dir.mkdir(parents=True, exist_ok=True)
    json.dump({"EpT": {"9": {
        "look": "A synthetic test meadow with oversized flowers.",
        "lighting": "Warm test daylight.",
        "weather": "Clear.",
        "colorTemperature": "Warm.",
        "definingFeature": "A single tall test flower.",
    }}}, open(canon_dir / "locations.json", "w"))
    monkeypatch.setattr(R, "_characters_cfg", lambda: CFG)
    # confirmed billing profiles — the unconfirmed hard-block has its own dedicated test
    import cb_costs
    monkeypatch.setattr(cb_costs, "load_billing_profile", lambda provider=None: {
        "planConfirmed": True, "cadenceConfirmed": True, "plan": "test",
        "billingCadence": "monthly", "cyclePriceUsdExTax": 99.0, "creditsPerCycle": 600000,
        "creditsPerCharacter": {"eleven_v3": 1.0}, "pricingSource": "test",
        "effectiveDate": "2026-07-16"})
    # a real beat package in the tmp world so _fresh_validation re-validates for real
    beatpkg = {"beats": [dict(b, sceneNumber="9") for b in BEATS],
               "scenes": [{"sceneNumber": "9", "name": "test"}]}
    (tmp_path / "cb-output" / "EpT_test_beat_package.json").parent.mkdir(
        parents=True, exist_ok=True)
    json.dump(beatpkg, open(tmp_path / "cb-output" / "EpT_test_beat_package.json", "w"))
    import cb_engine as E2
    monkeypatch.setattr(E2, "HERE", tmp_path / "engine")
    pkg_path = _build_package(tmp_path)
    # keyframe_shot also hard-refuses without a CURRENT APPROVED Scene Look Plate
    # (_require_current_scenelook). The safety layer binds that approval to both the
    # current package revision and the approved Look specialist prompt.
    look_prompt = ("Environment-only synthetic test meadow at bee scale, with readable "
                   "depth, warm daylight, oversized flowers, and no characters or text.")
    plate_path = engine / "media" / "EpT_S9_scenelook.png"
    plate_path.write_bytes(b"SCENELOOK_PLATE")
    composition_path = engine / "media" / "reference_controls" / "opening_composition.png"
    composition_path.parent.mkdir(parents=True, exist_ok=True)
    composition_path.write_bytes(b"OPENING_COMPOSITION")
    composition_record = {
        "path": str(composition_path), "contractHash": "test-composition",
        "zeroSpend": True, "providerCalled": False,
        "geometry": {"frameSize": [2048, 1152], "sameDepth": True,
                     "characters": []},
    }
    monkeypatch.setattr(
        R, "_load_opening_composition_master",
        lambda shot, scene, episode, characters: composition_record)
    monkeypatch.setattr(
        R, "_ensure_opening_composition_master",
        lambda pkg, shot, scene, episode, characters: composition_record)
    monkeypatch.setattr(
        R.cb_layout, "screen_candidate_geometry",
        lambda path, record: {
            "status": "pass", "reason": "synthetic fixture geometry",
            "zeroSpend": True, "providerCalled": False})
    plate_hash = hashlib.sha256(plate_path.read_bytes()).hexdigest()
    look_signature = {
        "briefHash": hashlib.sha256(look_prompt.encode()).hexdigest(),
        "referenceHashes": {},
        "plateHash": plate_hash,
    }
    R._save_scenelook_rec({
        "approved": {"path": str(plate_path), "hash": plate_hash,
                     "inputSignature": look_signature, "packageRevision": 1,
                     "referencePath": None, "approvedAt": "2026-07-19T00:00:00",
                     "reviewedBy": "test"},
        "candidate": None, "history": [],
        "departmentWork": {"look": {"approved": {
            "packageRevision": 1, "output": {"providerPrompt": look_prompt}},
            "candidate": None, "history": []}},
    }, "9", "EpT")
    # Sign the direct specialist inputs only after the package, references and Look plate
    # all exist. Revision metadata is provenance; these exact signatures are authority.
    pkg, pkg_disk_path = R.load_pkg("9", "EpT")
    look_rec = R._load_scenelook_rec("9", "EpT")
    look_rec["departmentWork"]["look"]["approved"]["inputSignature"] = \
        R._department_input_signature(pkg, "look", None, "9", "EpT")
    R._save_scenelook_rec(look_rec, "9", "EpT")
    look_rec = R._load_scenelook_rec("9", "EpT")
    look_rec["approved"]["inputSignature"] = R._scenelook_record_input_signature(
        "9", "EpT", look_rec["approved"]["path"], None)
    R._save_scenelook_rec(look_rec, "9", "EpT")
    for shot in pkg["shots"]:
        ledger = R._ledger(pkg, shot["shotId"])
        for stage in ("voice", "cinematography"):
            ledger["departmentWork"][stage]["approved"]["inputSignature"] = \
                R._department_input_signature(pkg, stage, shot["shotId"], "9", "EpT")
    R._save(pkg, pkg_disk_path)
    # THE LINEAGE CHECK, OUT OF SCOPE HERE ON PURPOSE (2026-07-17 state-integrity
    # checkpoint): _build_package hand-constructs a package directly through cb_engine's own
    # compilers — no creative-room storyboard file, no sourceStoryboard.md5, no revision at
    # all. This suite's own docstring already states its job: orchestration, validation,
    # spending control and state transitions, never storyboard-promotion lineage — real
    # lineage coverage lives in test_cb_render_lineage.py against a real storyboard/package
    # pair. Bypassing here is the same, already-established call as legacy_scratch_pkg's own
    # identical bypass in test_e2e_fire_route.py.
    monkeypatch.setattr(R, "_require_current_lineage", lambda pkg, scene, episode: None)
    return prov, tmp_path, pkg_path


def _token(shot_id, scene="9", ep="EpT", candidates=3):
    """Run the disclosure step (refuses by design) and return the server-issued token."""
    _approve_animation_direction(shot_id, scene, ep)
    with pytest.raises(R.Refused, match="SPEND NOT APPROVED"):
        R.fire_shot(scene, shot_id, ep, candidates=candidates, log=lambda *a, **k: None)
    return _led(scene, ep)[shot_id]["pendingSpendAuth"]["token"]


def _led(scene="9", ep="EpT"):
    pkg, _ = R.load_pkg(scene, ep)
    return {e["shotId"]: e for e in pkg["continuityLedger"]}


def _lock_scene_cut(scene="9", ep="EpT"):
    output = R.HERE.parent / "cb-output"
    state = R.cb_rough_cut.scene_status(ep, scene, out=output)
    return R.cb_rough_cut.save_scene_cut(
        ep, scene, state["sequence"], confirm=True, out=output)


def _fixture_reference_contract(shot):
    contract = []
    for tag, controls in (shot.get("referenceSlots") or {}).items():
        low = str(controls).casefold()
        if str(tag).casefold().startswith("@audio") or "voice" in low:
            role, scope = "audio", "continuity"
        elif "opening" in low or "previous shot final frame" in low:
            role, scope = "opening_frame", "continuity"
        elif "scene plate" in low or "location" in low:
            role, scope = "location", "episode"
        else:
            role, scope = "character_identity", "canon"
        contract.append({
            "assetTag": tag,
            "role": role,
            "controls": str(controls),
            "scope": scope,
        })
    return contract


def _current_animation_fixture(shot, geography=None):
    duration = int(round(float(shot.get("durationSec") or 6)))
    dialogue = list(shot.get("dialogueLines") or [])
    data = {
        "shotId": shot["shotId"],
        "durationSec": duration,
        "taskMode": "reference-to-video",
        "pacingMode": "timestamp" if duration > 15 else "storyline",
        "generationGoal": "Deliver the approved story beat with readable cause and effect.",
        "deliveryPlan": "Use the approved stage, references, voice authority and continuity finish.",
        "creativeTranslation": {
            "interpretation": {
                "jokeOrAche": "The approved fixture beat.",
                "mechanism": "Visible cause creates a readable emotional result.",
                "statusBefore": "The character enters with intent.",
                "statusAfter": "The character exits in the approved handoff state.",
                "audienceProgression": ["setup", "change", "landing"],
                "emotionalHeart": "The performance makes the story turn legible.",
            },
            "gagClocks": [],
            "generationDesign": {
                "packagingDecision": "single-unit",
                "completeGagArcCount": 0,
                "densityJudgement": "The fixture fits one provider unit.",
                "splitOrNonSplitRationale": "One causal beat is enough for the test.",
                "handoffState": "The approved final frame remains usable.",
            },
        },
        "dramaticBeat": "The approved fixture beat lands cleanly.",
        "audienceBefore": "The audience understands the setup.",
        "audienceAfter": "The audience understands the result.",
        "beatOwner": (shot.get("charactersInFrame") or ["Fuzzby"])[0],
        "performanceFreedom": "Allow micro-expression and secondary motion only.",
        "performanceArc": (
            "The eyes settle before the action, then the shoulders soften after the result."
        ),
        "physicalCauseAndEffect": (
            "As Fuzzby moves, he turns and steps because the approved cause moves him, "
            "then stops so that the visible result lands."
        ),
        "cameraBehaviour": shot.get("camera") or (
            "A medium-wide camera tracks the action, then holds the final framing."
        ),
        "timingAndRhythm": "Keep the beat moving while preserving the landing hold.",
        "landingBreath": "Hold the final image long enough to read.",
        "directionDensity": "guided",
        "shotPlan": [{
            "shotNumber": 1,
            "purpose": "Deliver the approved action.",
            "framingLensAndCamera": shot.get("camera") or "Readable framed camera.",
            "causalAction": (
                "Fuzzby turns and moves because the visible cause prompts him, then stops "
                "so that the result lands before the reaction."
            ),
            "observablePerformance": (
                "The eyes focus before the move; after it lands, breath and posture soften."
            ),
            "compositionLightAndMaterials": (
                "Layer foreground, midground and background under warm controlled light; "
                "preserve fur texture, soft contact shadow, scale and materials."
            ),
            "landingImage": shot.get("visualPayoff") or "Approved final state.",
            "dialogueLineIndexes": list(range(1, len(dialogue) + 1)),
            "dialogueDirections": [
                str(line.get("delivery") or "Act the line from the body.")
                for line in dialogue
            ],
            "holdAfterDialogue": not bool(dialogue),
            "gagBeatIds": [],
        }],
        "stagePlan": [{
            "stageNumber": 1,
            "beatIds": [shot.get("beatCode") or "1.B1"],
            "purpose": "Deliver the approved story event in one readable unit.",
            "initialOrCarriedState": "The approved opening establishes the physical stage.",
            "cause": "The character action begins from the approved setup.",
            "primaryEvent": "The character completes the approved causal action.",
            "observableEndState": "The shot lands on the approved handoff state.",
            "emotionOrCameraAnalysis": "The camera lets the performance turn read.",
            **({"startSec": 0.0, "endSec": float(duration)}
               if duration > 15 else {}),
        }],
        "geography": list(geography or [
            "Preserve the approved scene geography and camera axis."
        ]),
        "referenceContract": _fixture_reference_contract(shot),
        "consistencyContract": [
            "Keep identity, character count, scale, props, geography, light and camera axis stable."
        ],
        "audioContract": (
            "@Audio1 is the sole source of dialogue, voice, performance, timing and silence."
            if dialogue else "No dialogue. Preserve approved ambience only."
        ),
        "continuityFinish": shot.get("visualPayoff") or "End on the approved handoff frame.",
        "providerPrompt": "Temporary fixture prompt until deterministic compilation.",
    }
    direction = R.cb_departments.AnimationDirection.model_validate(data)
    output = direction.model_dump()
    output["providerPrompt"] = R.cb_departments.compile_animation_provider_prompt(
        shot, direction)
    return output


def _approve_animation_direction(shot_id, scene="9", ep="EpT"):
    """Test-only human approval record over the now-current direct animation inputs."""
    pkg, path = R.load_pkg(scene, ep)
    shot = R._shot(pkg, shot_id)
    work = R._ledger(pkg, shot_id)["departmentWork"]
    approved = work["animation"]["approved"]
    cinematography = ((work.get("cinematography") or {}).get("approved") or {}).get(
        "output") or {}
    previous_stages = list((approved.get("output") or {}).get("stagePlan") or [])
    output = _current_animation_fixture(shot, cinematography.get("geography"))
    if previous_stages and float(shot.get("durationSec") or 0) > 15:
        output["stagePlan"] = []
        for stage in previous_stages:
            normalized = dict(stage)
            normalized.setdefault(
                "cause", normalized.get("initialOrCarriedState") or
                "The approved carried state motivates this stage.")
            output["stagePlan"].append(normalized)
        direction = R.cb_departments.AnimationDirection.model_validate(output)
        output = direction.model_dump()
        output["providerPrompt"] = R.cb_departments.compile_animation_provider_prompt(
            shot, direction)
    approved["output"] = output
    approved["inputSignature"] = R._department_input_signature(
        pkg, "animation", shot_id, scene, ep)
    R._save(pkg, path)


def _review_output(artifact_type):
    dimension = {"score": 2, "intended": "Approved authored intent",
                 "observed": "Intent is present in the reviewed media",
                 "diagnosis": "No material failure", "confidence": "high"}
    output = {
        "artifactType": artifact_type, "verdict": "recommend-approve",
        "summary": "Test review found the approved intent intact.",
        "intendedRead": "The approved scene performance and continuity.",
        "actualRead": "The approved scene performance and continuity.",
        "finalFrameUsable": True, "recommendedCandidate": None,
        "candidateAssessments": [],
        "beatDelivery": dimension, "actingAndPerformance": dimension,
        "physicalCausality": dimension, "timingAndReaction": dimension,
        "cameraAndEdit": dimension, "compositionAndContinuity": dimension,
        "identityAndReferenceUse": dimension, "finishAndProductionValue": dimension,
        "likelyRootCause": "no-material-failure",
        "rootCauseReasoning": "The reviewed media matches its approved direct inputs.",
        "cheapestNextAction": {
            "action": "approve", "rerenderRequired": False,
            "reason": "No corrective action is required.",
            "changeOneLever": "None", "preserveExactly": [],
            "proofOfImprovement": "The current review is the proof.",
            "zeroCostChecksFirst": [],
        },
        "learningTags": [], "findings": [],
    }
    return R.cb_departments.MediaReview.model_validate(output).model_dump()


def _approve_director_review(stage, shot_id=None, scene="9", ep="EpT"):
    """Exercise the real signed candidate/decision transition without a vision call."""
    pkg, path = R.load_pkg(scene, ep)
    work, save_extra = R._department_container(pkg, scene, shot_id, stage, ep)
    artifact = "final" if stage == "review-final" else "animation"
    work["candidate"] = {
        "department": "Director Review",
        "worker": "Continuity Supervisor",
        "preparedAt": "2026-07-30T00:00:00+00:00",
        "preparedBy": "test",
        "sourceHash": "test",
        "output": _review_output(artifact),
        "packageRevision": pkg.get("revision"),
        "inputSignature": R._department_input_signature(
            pkg, stage, shot_id, scene, ep),
    }
    save_extra()
    R._save(pkg, path)
    return R.decide_department(
        scene, stage, "approved", shot_id=shot_id, episode=ep,
        reviewed_by="TestReviewer", log=lambda *a, **k: None)


def _install_scene_look(pkg, engine, scene, episode):
    prompt = ("Environment-only Crystal Cove meadow at bee scale, with readable depth, "
              "warm daylight, springy leaves, golden pollen, and no characters or text.")
    plate = engine / "media" / f"{episode}_S{scene}_scenelook.png"
    plate.parent.mkdir(parents=True, exist_ok=True)
    plate.write_bytes(b"APPROVED-SCENE-LOOK")
    plate_hash = hashlib.sha256(plate.read_bytes()).hexdigest()
    rec = {
        "approved": {
            "path": str(plate), "hash": plate_hash,
            "inputSignature": {
                "briefHash": hashlib.sha256(prompt.encode()).hexdigest(),
                "referenceHashes": {}, "plateHash": plate_hash,
            },
            "packageRevision": pkg.get("revision"), "referencePath": None,
            "approvedAt": "2026-07-30T00:00:00+00:00", "reviewedBy": "TestReviewer",
        },
        "candidate": None, "history": [],
        "departmentWork": {"look": {"approved": {
            "packageRevision": pkg.get("revision"),
            "output": {"providerPrompt": prompt},
        }, "candidate": None, "history": []}},
    }
    R._save_scenelook_rec(rec, scene, episode)
    rec = R._load_scenelook_rec(scene, episode)
    rec["departmentWork"]["look"]["approved"]["inputSignature"] = \
        R._department_input_signature(pkg, "look", None, scene, episode)
    R._save_scenelook_rec(rec, scene, episode)
    rec = R._load_scenelook_rec(scene, episode)
    rec["approved"]["inputSignature"] = R._scenelook_record_input_signature(
        scene, episode, rec["approved"]["path"], None)
    R._save_scenelook_rec(rec, scene, episode)


def _install_shot_departments(pkg, path, scene, episode):
    for shot in pkg["shots"]:
        compiled_animation = R.cb_departments._apply_animation_provider_shell(
            shot["seedancePrompt"], shot)
        shot["seedancePrompt"] = compiled_animation
        ledger = R._ledger(pkg, shot["shotId"])
        ledger["departmentWork"] = {
            "cinematography": {"approved": {
                "packageRevision": pkg.get("revision"),
                "output": _cinematography_output(shot),
            }},
            "voice": {"approved": {
                "packageRevision": pkg.get("revision"),
                "output": _voice_direction_output(shot),
            }},
            "animation": {"approved": {
                "packageRevision": pkg.get("revision"),
                "output": {"providerPrompt": compiled_animation},
            }},
        }
    R._save(pkg, path)
    pkg, path = R.load_pkg(scene, episode)
    for shot in pkg["shots"]:
        ledger = R._ledger(pkg, shot["shotId"])
        for stage in ("cinematography", "voice"):
            ledger["departmentWork"][stage]["approved"]["inputSignature"] = \
                R._department_input_signature(
                    pkg, stage, shot["shotId"], scene, episode)
    R._save(pkg, path)


def _voice_and_approve(scene="9", ep="EpT", log=lambda *a, **k: None):
    """THE VOICE APPROVAL STEP (2026-07-19): fire_shot now hard-refuses a dialogue shot
    whose voice track exists but hasn't been explicitly approved (mirrors the pre-existing
    keyframe-approval gate) — voice_scene() alone (generate) is no longer enough to clear
    a dialogue shot for animation. Approves every dialogue shot's track in package order,
    matching how a real Studio session would review-then-approve each one."""
    R.voice_scene(scene, ep, log=log)
    pkg, _ = R.load_pkg(scene, ep)
    for s in pkg["shots"]:
        if s.get("dialogueLines"):
            R.approve_voice(scene, s["shotId"], ep, log=log)


# ── THE GOLDEN PATH ─────────────────────────────────────────────────────────────────────
def test_golden_path_package_to_approved_scene_master(world):
    prov, tmp, _ = world

    # Gate 4 — voice: exactly the locked words, exactly once, right voices
    R.voice_scene("9", "EpT", log=lambda *a, **k: None)
    assert len(prov.voice_calls) == 2
    texts = [(t["voice_id"], t["text"]) for c in prov.voice_calls for t in c["inputs"]]
    assert ("voice-fuzzby", "Nailed it.") in texts
    assert ("voice-zenny", "Fuzzby… why are you humming?") in texts
    R.approve_voice("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    R.approve_voice("9", "1.B1.S2", "EpT", log=lambda *a, **k: None)

    # Gate 5 — the TIMING SLATE assembles from real durations + real voice, before any
    # image money (it approves timing/dialogue only — never staging or rhythm)
    out = R.animatic_scene("9", "EpT", log=lambda *a, **k: None)
    assert pathlib.Path(out).exists() and out.endswith("_timing_slate.mp4")
    assert R.timing_slate_status("9", "EpT")["current"] is True
    assert len(prov.image_calls) == 0          # no paid image call yet — slates only

    # Gate 6 — the opener keyframe receives the locked identities and Scene Look directly.
    # Generated poses and sizing/composition controls remain optional local evidence.
    R.keyframe_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    R.select_keyframe_candidate(
        "9", "1.B1.S1", "A", "EpT", log=lambda *a, **k: None)
    kf_call = prov.image_calls[-1]
    assert [os.path.basename(r) for r in kf_call["refs"]] == \
           ["Zenny_provider_front.png", "Fuzzby_provider_front.png",
            "EpT_S9_scenelook.png"]
    assert all("posed_integration" not in os.path.basename(r) for r in kf_call["refs"])
    assert "[Performance Freedom]" in kf_call["prompt"]
    assert "nailed it" not in kf_call["prompt"].lower()          # Law 6
    assert (_led()["1.B1.S1"]["keyframeCandidate"]["conformanceScreening"]
            ["status"] == "pass")

    # Gate 6b (2026-07-17 state-integrity checkpoint) — a generated-but-unapproved
    # keyframe candidate can never anchor a fire; Julian's own review approves it first,
    # exactly the lifecycle a real Studio session goes through before any spend.
    R.approve_keyframe("9", "1.B1.S1", "EpT", reviewed_by="TestReviewer", log=lambda *a, **k: None)
    _approve_animation_direction("1.B1.S1")

    # Gate 7 — SPEND CONTROL: no batch without a server-issued single-use token; the
    # disclosure is real, stored server-side, and bound to the exact package
    with pytest.raises(R.Refused, match="SPEND NOT APPROVED"):
        R.next_shot("9", "EpT", log=lambda *a, **k: None)
    assert len(prov.fire_calls) == 0                              # refusal spent NOTHING
    auth = _led()["1.B1.S1"]["pendingSpendAuth"]
    disc = auth["disclosure"]
    for k in ("candidateCount", "costPerCandidateUsd", "maxBatchCostUsd", "promptVersion",
               "bindingHash", "packageHash", "referenceSlots", "openingAnchor",
               "audioAsset", "shotDurationSec"):
        assert k in disc
    assert abs(disc["maxBatchCostUsd"] - 3 * disc["costPerCandidateUsd"]) < 1e-9

    # a fabricated token is refused — approval is server-side, never a client boolean
    with pytest.raises(R.Refused, match="unknown or already-used"):
        R.fire_shot("9", "1.B1.S1", "EpT", spend_token="deadbeef" * 4,
                     log=lambda *a, **k: None)

    # approved batch: 3 candidates, IDENTICAL prompt/refs/audio, anchor first, slot order
    R.next_shot("9", "EpT", spend_token=auth["token"], log=lambda *a, **k: None)  # 1.B1.S1
    batch1 = prov.fire_calls[-3:]
    assert len(batch1) == 3
    assert len({c["prompt"] for c in batch1}) == 1                # identical prompt
    assert len({tuple(c["image_urls"]) for c in batch1}) == 1     # identical references
    f1 = batch1[0]
    # anchor first: the APPROVED keyframe's own stored path (never renamed to a fixed
    # "_keyframe.png" — approve_keyframe keeps the candidate's own unique-hash filename,
    # matching this codebase's own "never rename an artefact, only what's approved of it
    # changes" convention; a literal ".endswith('_keyframe.png')" was stale against that)
    assert f1["image_urls"][0].endswith(_led()["1.B1.S1"]["keyframeApproval"]["path"])
    assert [os.path.basename(u) for u in f1["image_urls"][1:]] == \
           ["Zenny_provider_front.png", "Fuzzby_provider_front.png",
            "EpT_S9_scenelook.png"]
    assert f1["audio_urls"] and "_vo_candidate_" in f1["audio_urls"][0]
    assert f1["audio_urls"][0].endswith(".wav")
    assert f1["prompt"].count("{Nailed it.}") == 1
    assert "@Audio1 is the sole authority" in f1["prompt"]
    assert "no alternative performance is permitted" in f1["prompt"].lower()
    assert f1["duration"] == "6"      # deferred re-home item 8: always the shot's explicit
    #                                   seconds, never 'auto' (the old 15s literals can't bite)
    # per-candidate review sheets: human criteria all null — machine never approves quality
    led1 = _led()["1.B1.S1"]
    assert len(led1["candidatePaths"]) == 3
    rev = json.loads(pathlib.Path(led1["candidatePaths"][1] + ".review.json").read_text())
    assert set(rev["criteria"]) == set(R.REVIEW_CRITERIA)
    assert all(v is None for v in rev["criteria"].values())

    # the token is SINGLE-USE (consumed) and nothing advances past a pending batch
    assert _led()["1.B1.S1"]["pendingSpendAuth"] is None
    with pytest.raises(R.Refused, match="pending"):
        R.next_shot("9", "EpT", log=lambda *a, **k: None)
    with pytest.raises(R.Refused, match="pending"):
        R.fire_shot("9", "1.B1.S1", "EpT", spend_token=auth["token"],
                     log=lambda *a, **k: None)

    # Gate 8 — select candidate 2; the others are archived, its final frame harvested
    R.approve_shot("9", "1.B1.S1", 2, "EpT", log=lambda *a, **k: None)
    led1 = _led()["1.B1.S1"]
    assert led1["approvedTake"].endswith("_c2.mp4")
    assert led1["harvestFrame"].endswith("_final_frame.png")
    arch = tmp / "engine" / "media" / "archive" / "shots_candidates"
    archived = [p.name for d in arch.iterdir() for p in d.iterdir()]
    assert "EpT_1.B1.S1_c1.mp4" in archived and "EpT_1.B1.S1_c3.mp4" in archived
    assert len(led1["renderHistory"]) == 2
    assert all(item["outcome"] == "not-selected" for item in led1["renderHistory"])
    assert all(item["contentHashAtGeneration"] for item in led1["renderHistory"])
    assert all(item["promptContract"]["integrityVerified"] for item in led1["renderHistory"])

    # relay batch fires from the SELECTED candidate's harvested final frame
    t2 = _token("1.B1.S2")
    R.next_shot("9", "EpT", spend_token=t2, log=lambda *a, **k: None)   # 1.B1.S2 batch
    f2 = prov.fire_calls[-1]
    assert f2["image_urls"][0].endswith("EpT_1.B1.S1_final_frame.png")   # THE relay contract
    R.approve_shot("9", "1.B1.S2", 1, "EpT", log=lambda *a, **k: None)

    t3 = _token("1.B1.S3")
    R.next_shot("9", "EpT", spend_token=t3, log=lambda *a, **k: None)   # silent 1.B1.S3
    f3 = prov.fire_calls[-1]
    assert f3["audio_urls"] is None                               # silent shot: no @Audio1
    assert f3["image_urls"][0].endswith("EpT_1.B1.S2_final_frame.png")
    R.approve_shot("9", "1.B1.S3", 1, "EpT", log=lambda *a, **k: None)

    # Every selected take is independently reviewed before Post can consume it.
    for shot_id in ("1.B1.S1", "1.B1.S2", "1.B1.S3"):
        _approve_director_review("review-animation", shot_id)

    # Post builds an immutable, QC-passed candidate with every approved shot in order.
    _lock_scene_cut("9", "EpT")
    master = R.stitch_scene("9", "EpT", log=lambda *a, **k: None)
    data = pathlib.Path(master).read_bytes()
    i1 = data.find(b"1.B1.S1_c2.mp4"); i2 = data.find(b"1.B1.S2_c1.mp4")
    i3 = data.find(b"1.B1.S3_c1.mp4")
    assert -1 < i1 < i2 < i3
    pkg, _ = R.load_pkg("9", "EpT")
    post = R.post_status(pkg, "9", "EpT")
    assert post["candidate"]["current"] is True
    assert post["approved"]["exists"] is False

    # A QC pass is not a creative approval. The separate final review promotes this exact
    # candidate, without rebuilding or renaming any deliverable.
    _approve_director_review("review-final")
    pkg, _ = R.load_pkg("9", "EpT")
    post = R.post_status(pkg, "9", "EpT")
    assert post["candidate"]["exists"] is False
    assert post["approved"]["current"] is True
    assert post["approved"]["manifest"]["outputs"]["master16x9"]["path"] == master

    # the evidence pack records the whole run: every shot approved, every asset present,
    # the stitched output named — nothing invented, nothing silently missing
    out = R.evidence_pack("9", "EpT", log=lambda *a, **k: None)
    pack = json.loads((pathlib.Path(out) / "evidence.json").read_text())
    assert len(pack["shots"]) == 3 and pack["stitchedOutput"]["exists"]
    assert pack["finalMaster"]["exists"]
    assert pack["postManifest"]["qc"]["passed"] is True
    for c in pack["shots"]:
        assert c["state"]["status"] == "approved"
        assert c["assets"]["take"]["exists"] and c["assets"]["harvestFrame"]["exists"]
        assert c["state"]["disclosure"]["promptVersion"]          # the spend record persists
        if c["input"]["dialogueLines"]:
            assert c["assets"]["voice"]["exists"]
    idx = (pathlib.Path(out) / "index.md").read_text()
    for sid in ("1.B1.S1", "1.B1.S2", "1.B1.S3"):
        assert sid in idx
    assert idx.count("status: **approved**") == 3
    # A silent shot's "voice: MISSING" is truthful, while both post artefacts are present.
    assert "Conformed picture: `picture_conformed.mp4`" in idx
    assert "Final 16:9 master: `master_16x9_youtube.mp4`" in idx

    # Content integrity and review provenance remain live after approval. Any changed byte
    # or altered Director Review evidence makes the master stale instead of silently final.
    master_path = pathlib.Path(master)
    approved_bytes = master_path.read_bytes()
    master_path.write_bytes(approved_bytes + b"TAMPER")
    pkg, _ = R.load_pkg("9", "EpT")
    changed = R.post_status(pkg, "9", "EpT")["approved"]
    assert changed["current"] is False
    assert changed["reason"] == "post-output-changed:master16x9"
    master_path.write_bytes(approved_bytes)
    pkg, pkg_path = R.load_pkg("9", "EpT")
    review = R._ledger(pkg, "1.B1.S1")["departmentWork"]["review-animation"]["approved"]
    review["output"]["summary"] = "ALTERED REVIEW EVIDENCE"
    R._save(pkg, pkg_path)
    pkg, _ = R.load_pkg("9", "EpT")
    changed = R.post_status(pkg, "9", "EpT")["approved"]
    assert changed["current"] is False
    assert changed["reason"] == "direct-input-signature-mismatch"


def test_failed_keyframe_identity_screen_preserves_candidate_for_human_decision(
        world, monkeypatch):
    prov, _, _ = world
    monkeypatch.setattr(
        R.cb_departments, "review_keyframe_conformance",
        lambda context, images, **kwargs: _keyframe_conformance_output(context, "block"))

    R.keyframe_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)

    ledger = _led()["1.B1.S1"]
    assert ledger["keyframeCandidate"]["conformanceScreening"]["status"] == "fail"
    assert pathlib.Path(ledger["keyframeCandidate"]["path"]).exists()
    assert ledger.get("keyframeRejected") is None
    assert len(prov.image_calls) == 2

    R.reject_keyframe(
        "9", "1.B1.S1", "The staging does not match the shot.", episode="EpT",
        reviewed_by="TestReviewer", log=lambda *a, **k: None)
    ledger = _led()["1.B1.S1"]
    assert ledger.get("keyframeCandidate") is None
    assert ledger["keyframeRejected"]["reviewedBy"] == "TestReviewer"
    assert "The staging does not match" in ledger["keyframeRejected"]["reason"]


def test_unavailable_keyframe_identity_screen_preserves_candidate_for_human_accept(
        world, monkeypatch):
    prov, _, _ = world

    def unavailable(*args, **kwargs):
        raise RuntimeError("validator temporarily unavailable")

    monkeypatch.setattr(
        R.cb_departments, "review_keyframe_conformance", unavailable)
    R.keyframe_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    R.select_keyframe_candidate(
        "9", "1.B1.S1", "A", "EpT", log=lambda *a, **k: None)

    candidate = _led()["1.B1.S1"]["keyframeCandidate"]
    assert candidate["conformanceScreening"]["status"] == "unavailable"
    R.approve_keyframe(
        "9", "1.B1.S1", "EpT", reviewed_by="TestReviewer",
        log=lambda *a, **k: None)
    approval = _led()["1.B1.S1"]["keyframeApproval"]
    assert approval["conformanceAdvisoryDecision"]["acceptedBy"] == "TestReviewer"
    assert len(prov.image_calls) == 2


def test_watch_honors_human_accepted_keyframe_with_physical_stage_warning(
        world, monkeypatch):
    def physical_stage_failure(context=None, images=None, **kwargs):
        expected = list((context or {}).get("expectedCharacters") or ["Fuzzby", "Zenny"])
        ok_dimension = {
            "score": 2,
            "visibleEvidence": "Identities are readable.",
            "correction": "",
        }
        failed_stage = {
            "score": 0,
            "visibleEvidence": (
                "The rescue net is visibly attached to the boat hull, so the frame "
                "does not prove the required loose physical relationship."
            ),
            "correction": (
                "Rebuild SEE with visible water gap between the boat and every net "
                "strand before WATCH."
            ),
        }
        return R.cb_departments.KeyframeConformanceReview.model_validate({
            "verdict": "block",
            "expectedCharacters": expected,
            "detectedCharacters": expected,
            "expectedSubjectCount": len(expected),
            "subjectCount": len(expected),
            "summary": (
                "Opening geography and physical causality fail: the keyframe shows "
                "the net attached to the boat instead of floating free."
            ),
            "identityAndDistinguishability": ok_dimension,
            "relativeScaleAndGeography": failed_stage,
            "anatomyAndSilhouette": ok_dimension,
            "actionReadyComposition": failed_stage,
            "forbiddenContent": ok_dimension,
            "recommendedCorrection": (
                "SEE must prove the physical stage contract before WATCH; text "
                "cannot safely override this opening frame."
            ),
        })

    monkeypatch.setattr(
        R.cb_departments, "review_keyframe_conformance", physical_stage_failure)
    R.keyframe_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    R.select_keyframe_candidate(
        "9", "1.B1.S1", "A", "EpT", log=lambda *a, **k: None)
    R.approve_keyframe(
        "9", "1.B1.S1", "EpT", reviewed_by="TestReviewer",
        log=lambda *a, **k: None)

    approval = _led()["1.B1.S1"]["keyframeApproval"]
    assert approval["conformanceAdvisoryDecision"]["acceptedBy"] == "TestReviewer"

    # Approval is persisted in the package. Both UI state derivation and the fire gate
    # consume this same record after a fresh load, so a reload cannot resurrect the warning.
    reloaded_pkg, _ = R.load_pkg("9", "EpT")
    reloaded_approval = R._ledger(
        reloaded_pkg, "1.B1.S1")["keyframeApproval"]
    assert R._keyframe_stage_contract_report(reloaded_approval) == {
        "ready": True,
        "reason": None,
    }

    # The human accepted the exact advisory during SEE. WATCH must not demand a
    # second hidden approval for the same automated composition warning.
    with pytest.raises(R.Refused) as exc:
        R.fire_shot("9", "1.B1.S1", "EpT", candidates=1,
                    log=lambda *a, **k: None)
    assert "SEE frame does not prove the physical stage contract" not in str(exc.value)


def test_watch_blocks_unapproved_physical_stage_warning(world):
    record = {
        "approved": True,
        "conformanceScreening": {
            "status": "block",
            "reason": "Opening geography and physical staging fail.",
            "review": {
                "summary": "The prop placement does not match the authored stage.",
                "recommendedCorrection": "Correct the opening frame before WATCH.",
            },
        },
    }

    report = R._keyframe_stage_contract_report(record)
    assert report["ready"] is False
    assert report["reason"] == "Opening geography and physical staging fail."


def test_watch_allows_explicit_stage_contract_override(world, monkeypatch):
    def physical_stage_failure(context=None, images=None, **kwargs):
        expected = list((context or {}).get("expectedCharacters") or ["Fuzzby", "Zenny"])
        ok_dimension = {
            "score": 2,
            "visibleEvidence": "Identities are readable.",
            "correction": "",
        }
        failed_stage = {
            "score": 0,
            "visibleEvidence": "The rescue net placement does not match the authored stage.",
            "correction": "Human Director may override only with an explicit stage contract record.",
        }
        return R.cb_departments.KeyframeConformanceReview.model_validate({
            "verdict": "block",
            "expectedCharacters": expected,
            "detectedCharacters": expected,
            "expectedSubjectCount": len(expected),
            "subjectCount": len(expected),
            "summary": "Opening geography and physical staging fail.",
            "identityAndDistinguishability": ok_dimension,
            "relativeScaleAndGeography": failed_stage,
            "anatomyAndSilhouette": ok_dimension,
            "actionReadyComposition": failed_stage,
            "forbiddenContent": ok_dimension,
            "recommendedCorrection": "SEE failed physical stage conformance.",
        })

    monkeypatch.setattr(
        R.cb_departments, "review_keyframe_conformance", physical_stage_failure)
    R.keyframe_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    R.select_keyframe_candidate(
        "9", "1.B1.S1", "A", "EpT", log=lambda *a, **k: None)
    R.approve_keyframe(
        "9", "1.B1.S1", "EpT", reviewed_by="TestReviewer",
        log=lambda *a, **k: None)

    pkg, path = R.load_pkg("9", "EpT")
    R._shot(pkg, "1.B1.S1")["dialogueLines"] = []
    approval = R._ledger(pkg, "1.B1.S1")["keyframeApproval"]
    approval["stageContractOverride"] = {
        "acceptedBy": "TestReviewer",
        "acceptedAt": "2026-08-17T00:00:00",
        "reason": "Human director selected emotional composition over automated layout advice.",
    }
    R._save(pkg, path)

    with pytest.raises(R.Refused) as exc:
        R.fire_shot("9", "1.B1.S1", "EpT", candidates=1,
                    log=lambda *a, **k: None)
    assert "SEE frame does not prove the physical stage contract" not in str(exc.value)


def test_human_uploaded_keyframe_accepts_when_automated_advice_is_unavailable(
        world, monkeypatch, tmp_path):
    def unavailable(*args, **kwargs):
        raise RuntimeError("validator temporarily unavailable")

    monkeypatch.setattr(
        R.cb_departments, "review_keyframe_conformance", unavailable)
    monkeypatch.setattr(
        R, "_load_opening_composition_master",
        lambda shot, scene, episode, characters: None)
    upload = tmp_path / "human-selected-keyframe.jpeg"
    upload.write_bytes(b"HUMAN_SELECTED_STAGE")

    R.select_keyframe_source(
        "9", "1.B1.S1", "upload", "EpT", upload_path=str(upload),
        reviewed_by="TestReviewer", log=lambda *a, **k: None)

    candidate = _led()["1.B1.S1"]["keyframeCandidate"]
    assert candidate["source"] == "uploaded"
    assert candidate["geometryScreening"]["status"] == "unavailable"
    assert candidate["conformanceScreening"]["status"] == "unavailable"

    R.approve_keyframe(
        "9", "1.B1.S1", "EpT", reviewed_by="TestReviewer",
        log=lambda *a, **k: None)

    approval = _led()["1.B1.S1"]["keyframeApproval"]
    assert approval["approved"] is True
    assert approval["source"] == "uploaded"
    assert approval["conformanceAdvisoryDecision"]["acceptedBy"] == "TestReviewer"
    assert R._keyframe_record_status(
        R.load_pkg("9", "EpT")[0],
        R._shot(R.load_pkg("9", "EpT")[0], "1.B1.S1"),
        approval, "9", "EpT")["current"] is True


def test_same_process_comparison_returns_one_candidate_from_approved_stage_relay(
        world, monkeypatch):
    """A short-provider comparison remains one ordinary Studio review candidate."""
    prov, _, _ = world
    pkg, path = R.load_pkg("9", "EpT")
    shot = R._shot(pkg, "1.B1.S1")
    shot["durationSec"] = 28.0
    windows = ((0, 7), (7, 15), (15, 22), (22, 28))
    stages = [{
        "stageNumber": index,
        "beatIds": ["1.B1"],
        "purpose": f"Preserve approved story purpose {index}.",
        "startSec": start,
        "endSec": end,
        "initialOrCarriedState": f"Carry the approved visible state into stage {index}.",
        "primaryEvent": f"Fuzzby completes one readable causal action in stage {index}.",
        "observableEndState": f"Fuzzby reaches approved visible handoff {index}.",
        "emotionOrCameraAnalysis": (
            f"His gaze and chest recover visibly while the camera motivates stage {index}."),
    } for index, (start, end) in enumerate(windows, start=1)]
    ledger = R._ledger(pkg, shot["shotId"])
    ledger["departmentWork"]["animation"]["approved"]["output"] = {
        "providerPrompt": shot["seedancePrompt"],
        "durationSec": 28.0,
        "taskMode": "reference-to-video",
        "generationGoal": (
            "Deliver the approved pride, impact, recovery, and relationship turn in order."),
        "stagePlan": stages,
        "dramaticBeat": "Warm stylized 3D meadow comedy with physical cause and effect.",
        "performanceArc": (
            "Fuzzby's proud gaze and chest recover after each impact while Zenny remains still."),
        "cameraBehaviour": (
            "Use motivated bee-height tracking and readable internal cuts without changing axis."),
        "audioContract": (
            "@Audio1 is the sole source of English dialogue, voice, performance, and timing."),
        "consistencyContract": [
            "Keep identity, character count, scale, pollen marks, scene geography, light direction, and camera axis stable."
        ],
        "referenceContract": [{
            "assetTag": tag, "role": role, "controls": role,
        } for tag, role in shot["referenceSlots"].items()],
    }
    R._save(pkg, path)

    pkg, path = R.load_pkg("9", "EpT")
    for stage_name in ("voice", "cinematography"):
        R._ledger(pkg, shot["shotId"])["departmentWork"][stage_name]["approved"][
            "inputSignature"] = R._department_input_signature(
                pkg, stage_name, shot["shotId"], "9", "EpT")
    R._save(pkg, path)

    _voice_and_approve("9", "EpT", log=lambda *a, **k: None)
    R.animatic_scene("9", "EpT", log=lambda *a, **k: None)
    R.keyframe_shot("9", shot["shotId"], "EpT", log=lambda *a, **k: None)
    R.select_keyframe_candidate(
        "9", shot["shotId"], "A", "EpT", log=lambda *a, **k: None)
    R.approve_keyframe("9", shot["shotId"], "EpT", reviewed_by="TestReviewer",
                       log=lambda *a, **k: None)
    _approve_animation_direction(shot["shotId"])

    joined = []

    def join_segments(segment_paths, out):
        joined.append(list(segment_paths))
        pathlib.Path(out).write_bytes(b"JOINED-COMPARISON-CANDIDATE")
        return str(out)

    monkeypatch.setattr(R.cb_seedance_transport, "join_segments", join_segments)
    comparison = {
        "comparison_model_id": "fal-seedance-2.0",
        "comparison_run_id": "golden-same-process-comparison",
    }
    with pytest.raises(R.Refused, match="SPEND NOT APPROVED"):
        R.fire_shot("9", shot["shotId"], "EpT", candidates=1,
                    log=lambda *a, **k: None, **comparison)
    pending = _led()[shot["shotId"]]["pendingSpendAuth"]
    assert pending["disclosure"]["internalProviderCalls"] == [
        {"segmentIndex": 1, "durationSec": 15.0, "stageNumbers": [1, 2]},
        {"segmentIndex": 2, "durationSec": 13.0, "stageNumbers": [3, 4]},
    ]

    paths = R.fire_shot(
        "9", shot["shotId"], "EpT", candidates=1, spend_token=pending["token"],
        log=lambda *a, **k: None, **comparison)
    calls = prov.fire_calls[-2:]
    assert [call["duration"] for call in calls] == ["15", "13"]
    assert all(call["comparison_run_id"] == comparison["comparison_run_id"]
               for call in calls)
    assert calls[1]["image_urls"][0].endswith("segment_1_final.png")
    assert len(joined) == 1 and len(joined[0]) == 2
    assert len(paths) == 1 and pathlib.Path(paths[0]).read_bytes() == \
        b"JOINED-COMPARISON-CANDIDATE"
    final_ledger = _led()[shot["shotId"]]
    assert final_ledger["status"] == "candidates-pending"
    assert final_ledger["batch"]["transportCandidates"]["1"]["status"] == "joined"
    review = json.loads(pathlib.Path(paths[0] + ".review.json").read_text())
    assert all(value is None for value in review["criteria"].values())


def test_immutable_script_to_approved_master_golden_path(monkeypatch, tmp_path):
    """The audit's full proof: immutable screenplay bytes to a current final master.

    Creative and media model responses are deterministic fixtures, so this spends nothing.
    Parsing, exact-event lineage, human approval boundaries, handover, render orchestration,
    spend claims, post provenance and authoritative readiness are all production code.
    """
    import cb_engine
    import cb_handover as H
    import cb_intake
    import cb_lineage
    import cb_state
    from cb_scripts import ScriptStore
    from test_cb_handover import _refresh_dialogue_contract, _storyboard, _vp

    script = ("INT. CRYSTAL COVE - DAY 1\n\n"
              "Fuzzby rockets toward a springy leaf as Zenny watches from her petal.\n\n"
              "FUZZBY\nNailed it.\n")
    store = ScriptStore(
        tmp_path, script_root=tmp_path / "shows/crystal-bears/episodes/scripts")
    current = store.store(
        "Ep1", script, "Script To Master", source_name="script.txt",
        activated_by="TestReviewer", activated_at="2026-07-30T00:00:00+00:00")

    characters_path = tmp_path / "shows" / "crystal-bears" / "canon" / "characters.json"
    characters_path.parent.mkdir(parents=True, exist_ok=True)
    characters_path.write_text(json.dumps(CFG, indent=1))
    episodes = tmp_path / "cb-studio" / "data" / "episodes.json"
    episodes.parent.mkdir(parents=True, exist_ok=True)
    episodes.write_text(json.dumps([{
        "number": 1, "title": "Script To Master", "script": current["displayFile"],
        "scriptVersionId": current["scriptVersionId"],
    }]))
    output = tmp_path / "cb-output"
    creative = output / "creative"
    creative.mkdir(parents=True)
    for name, value in {
        "ROOT": tmp_path, "OUT": output, "CREATIVE_OUT": creative,
        "EPISODES_JSON": episodes, "SCRIPTS": store.script_root,
        "STUDIO_SCRIPTS": store.studio_root, "SCRIPT_STORE": store,
        "CHARACTERS_JSON": characters_path,
        "ARCHIVE_DIR": output / "archive" / "story_intake_rejected",
    }.items():
        monkeypatch.setattr(cb_intake, name, value)

    vision = {
        key: value for key, value in zip(
            ("premise", "dramaticQuestion", "theme", "externalJourney",
             "internalJourney", "relationshipChanges", "emotionalCurve",
             "comedyCurve", "setupPayoffMap", "visualMotifs", "sonicMotifs",
             "climax", "resolution", "intendedFinalFeeling"),
            ("A confident flight meets physics.", "Can confidence survive a wobble?",
             "Resilience", "Fuzzby crosses the meadow.", "He accepts a tiny mistake.",
             "Zenny sees his recovery.", "Confidence, surprise, recovery.",
             "Speed, impact, private flinch.", "The leaf answers his boast.",
             "Warm pollen and springy leaves.", "Wing hum and leaf twang.",
             "The leaf rebounds.", "Fuzzby stays airborne.", "Warm amusement."))}
    vision["storyArchitecture"] = {
        "storyTruth": {
            "protagonist": "Fuzzby", "falseBelief": "Control must look effortless.",
            "practicalWant": "Cross the meadow cleanly.", "keyRelationship": "Zenny",
            "emotionalFearOrWound": "Being seen making a mistake.",
            "transformedAction": "Stay connected after the wobble.",
            "themeProvenThroughAction": "He lets Zenny see the recovery."},
        "transformationMap": [{
            "movement": movement, "believes": "Control protects confidence.",
            "feels": "Increasingly exposed.", "does": "Adapts after the rebound.",
            "relationshipCondition": "Zenny becomes a witness and ally.",
            "audienceFeeling": "Amusement deepening into affection."}
            for movement in (
                "opening", "inciting-pressure", "first-adaptation", "midpoint-truth",
                "low-point", "climax-choice", "new-normal")],
        "tapestryMap": {
            "physicalMotifArc": "The leaf changes from obstacle to shared evidence.",
            "visualMotifArc": "An open flight lane closes and reopens.",
            "colourAndLightJourney": "Warm play cools at impact and returns.",
            "sourceSoundArc": "Wing hum breaks on the leaf twang, then settles.",
            "musicMotifArc": "The confident figure pauses before returning gently.",
            "environmentalMetaphor": "The meadow bends confidence without breaking it.",
            "openingImage": "Fuzzby owns an open flight lane.",
            "finalImage": "Fuzzby shares that lane with Zenny.",
            "transformedMeaning": "The lane now holds connection, not mastery."},
        "sequenceBlueprint": [{
            "sequenceId": "SEQ1", "sceneIds": ["S1"], "runtimeTarget": "one scene",
            "externalObjective": "Cross the meadow.",
            "emotionalStart": "Unchecked confidence.",
            "pressureOrComplication": "The springy leaf resists his speed.",
            "emotionalTurn": "A private wobble becomes an honest recovery.",
            "endCondition": "Fuzzby remains connected after failing.",
            "dominantAudienceFeeling": "Warm amusement.",
            "nextQuestion": "Can he accept help next time?"}]}

    def prepare_story(events, cast_by_scene, canon_context, log=print):
        assert [event["type"] for event in events] == ["action", "dialogue"]
        assert canon_context["canonProfileDigest"] == TEST_CANON_DIGESTS["story"]
        return R.cb_departments.StoryIntakeDirection.model_validate({
            "title": "Script To Master", "logline": "A boast meets a springy leaf.",
            "leadBear": "Fuzzby", "episodeVision": vision,
            "beats": [{
                "sceneNumber": 1, "firstEventIndex": 0, "beatCode": "1.B1",
                "storyBeat": "Fuzzby boasts just as the leaf challenges his control.",
                "charactersInFrame": ["Fuzzby", "Zenny"],
                "offscreenCharacters": [],
                "want": "Look effortless.", "need": "Recover without hiding the wobble.",
                "kidRead": "A funny bounce.", "adultRead": "Confidence can bend.",
                "emotionalIntent": "Pride turns into resilient amusement.",
            }],
        })

    monkeypatch.setattr(cb_intake.cb_departments, "prepare_story", prepare_story)
    intake_candidate = cb_intake.prepare_intake("Ep1", log=lambda *a, **k: None)
    assert intake_candidate["sourceEventCoverage"]["ok"] is True
    assert intake_candidate["dialogueCoverage"]["coveredExactly"] == 1
    intake_result = cb_intake.decide_intake(
        "Ep1", "approve", reviewed_by="TestReviewer", log=lambda *a, **k: None)
    beat_path = tmp_path / intake_result["canonicalPackage"]
    beat_package = json.loads(beat_path.read_text())
    source_beat = beat_package["beats"][0]
    source_occurrence = next(
        cut for cut in source_beat["cuts"] if cut["sourceType"] == "dialogue")

    storyboard = _storyboard("approved")
    directed_beat = storyboard["beats"][0]
    directed_beat["beatId"] = source_beat["beatCode"]
    for key in ("sourceBeatId", "sourceEventIds", "sourceEventRange",
                "sourceEventSignature"):
        directed_beat[key] = source_beat[key]
    occurrence = {
        "dialogueOccurrenceId": source_occurrence["dialogueOccurrenceId"],
        "sourceEventId": source_occurrence["sourceEventId"],
        "sourceEventIndex": source_occurrence["sourceEventIndex"],
        "beatId": source_beat["beatCode"],
        "sourceBeatId": source_beat["sourceBeatId"],
        "speaker": source_occurrence["speaker"],
        "exactText": source_occurrence["exactText"],
    }
    directed_beat["dialogueOccurrences"] = [occurrence]
    directed_beat["exactDialogue"] = [
        f"{occurrence['speaker']}: {occurrence['exactText']}"]
    storyboard["voicePerformances"] = [
        _vp(occurrence["speaker"], occurrence["exactText"], occurrence)]
    storyboard["productionDetail"][0]["dialogueOccurrenceIds"] = [
        occurrence["dialogueOccurrenceId"]]
    storyboard["productionDetail"][0]["dialogueTimings"] = [{
        "dialogueOccurrenceId": occurrence["dialogueOccurrenceId"],
        "startSec": 0.5, "endSec": 1.25,
    }]
    storyboard["productionDetail"][1]["dialogueOccurrenceIds"] = []
    storyboard["productionDetail"][1]["dialogueTimings"] = []
    storyboard["sourceScript"] = beat_package["sourceScript"]
    storyboard["sourceBeatPackage"] = {
        "path": str(beat_path.relative_to(tmp_path)),
        "contentSignature": beat_package["contentSignature"],
    }
    storyboard["inputSignature"] = cb_lineage.dependency_signature(
        "scene-storyboard", {
                "scriptVersionId": current["scriptVersionId"],
                "beatPackageDigest": beat_package["contentSignature"]["digest"],
                "episodeVisionDigest": "test-approved-vision", "sceneNumber": "1",
                "ambitionBrief": None,
                "canonProfileDigest": TEST_CANON_DIGESTS["storyboard"],
                "canonSources": {},
            })
    storyboard["canonLock"] = {
        "manifestDigest": "m" * 64,
        "profile": "storyboard",
        "profileDigest": TEST_CANON_DIGESTS["storyboard"],
    }
    _refresh_dialogue_contract(storyboard)
    storyboard_path = creative / "Ep1_scene1_storyboard.json"
    storyboard_path.write_text(json.dumps(storyboard, indent=1, ensure_ascii=False))

    engine = tmp_path / "engine"
    package_path = output / "Ep1_scene1_production_package.json"
    monkeypatch.setattr(H, "ROOT", tmp_path)
    monkeypatch.setattr(H, "SCRIPT_STORE", store)
    monkeypatch.setattr(H, "CHARS", characters_path)
    monkeypatch.setattr(cb_engine, "HERE", engine)
    monkeypatch.setattr(
        cb_engine, "canonical_package_path",
        lambda scene, episode="Ep1": output / f"{episode}_scene{scene}_production_package.json")
    promoted, _ = H.promote_to_canonical(
        storyboard_path, "1", ["S1.SH1"], episode="Ep1", dry_run=False,
        log=lambda *a, **k: None)
    assert promoted["validation"]["passed"] is True
    promoted_line = promoted["shots"][0]["dialogueLines"][0]
    assert promoted_line["exactText"] == "Nailed it."
    assert promoted_line["dialogueOccurrenceId"] == occurrence["dialogueOccurrenceId"]
    assert promoted_line["sourceEventId"] == occurrence["sourceEventId"]
    assert package_path.exists()

    providers = Providers()
    providers.install(monkeypatch, tmp_path)
    monkeypatch.setattr(R, "HERE", engine)
    monkeypatch.setattr(R, "ROOT", tmp_path)
    monkeypatch.setattr(R, "MEDIA", engine / "media" / "shots")
    monkeypatch.setattr(R, "SCRIPT_STORE", store)
    monkeypatch.setattr(R, "_characters_cfg", lambda: CFG)
    for character in CFG.values():
        ref = engine / character["anchor"]
        ref.parent.mkdir(parents=True, exist_ok=True)
        ref.write_bytes(b"IDENTITY-REFERENCE")
    _install_provider_identity_fixture(monkeypatch, engine)
    composition_path = engine / "media" / "reference_controls" / "opening_composition.png"
    composition_path.parent.mkdir(parents=True, exist_ok=True)
    composition_path.write_bytes(b"OPENING-COMPOSITION")
    composition_record = {
        "path": str(composition_path), "contractHash": "golden-composition",
        "zeroSpend": True, "providerCalled": False,
        "geometry": {"frameSize": [2048, 1152], "sameDepth": True,
                     "characters": []},
    }
    monkeypatch.setattr(
        R, "_load_opening_composition_master",
        lambda shot, scene, episode, characters: composition_record)
    monkeypatch.setattr(
        R, "_ensure_opening_composition_master",
        lambda pkg, shot, scene, episode, characters: composition_record)
    monkeypatch.setattr(
        R.cb_layout, "screen_candidate_geometry",
        lambda path, record: {
            "status": "pass", "reason": "synthetic fixture geometry",
            "zeroSpend": True, "providerCalled": False})
    locations = tmp_path / "shows" / "crystal-bears" / "canon" / "locations.json"
    locations.write_text(json.dumps({"Ep1": {"1": {
        "look": "Crystal Cove meadow at bee scale.", "lighting": "Warm daylight.",
        "weather": "Clear.", "colorTemperature": "Warm.",
        "definingFeature": "A springy leaf beside Zenny's petal.",
    }}}))

    pkg, pkg_path = R.load_pkg("1", "Ep1")
    _install_scene_look(pkg, engine, "1", "Ep1")
    _install_shot_departments(pkg, pkg_path, "1", "Ep1")
    R.voice_scene("1", "Ep1", log=lambda *a, **k: None)
    R.approve_voice("1", "S1.SH1", "Ep1", reviewed_by="TestReviewer",
                    log=lambda *a, **k: None)
    R.animatic_scene("1", "Ep1", log=lambda *a, **k: None)
    R.keyframe_shot("1", "S1.SH1", "Ep1", log=lambda *a, **k: None)
    R.select_keyframe_candidate(
        "1", "S1.SH1", "A", "Ep1", log=lambda *a, **k: None)
    R.approve_keyframe("1", "S1.SH1", "Ep1", reviewed_by="TestReviewer",
                       log=lambda *a, **k: None)
    token = _token("S1.SH1", "1", "Ep1", candidates=1)
    R.fire_shot("1", "S1.SH1", "Ep1", candidates=1, spend_token=token,
                log=lambda *a, **k: None)
    R.approve_shot("1", "S1.SH1", 1, "Ep1", reviewed_by="TestReviewer",
                   log=lambda *a, **k: None)
    _approve_director_review("review-animation", "S1.SH1", "1", "Ep1")
    _lock_scene_cut("1", "Ep1")
    master = R.stitch_scene("1", "Ep1", log=lambda *a, **k: None)
    _approve_director_review("review-final", None, "1", "Ep1")

    final_pkg, _ = R.load_pkg("1", "Ep1")
    post = R.post_status(final_pkg, "1", "Ep1")
    manifest = post["approved"]["manifest"]
    assert post["approved"]["current"] is True
    assert manifest["orderedShots"][0]["shotId"] == "S1.SH1"
    assert manifest["captionWindows"][0]["dialogueOccurrenceId"] == \
        occurrence["dialogueOccurrenceId"]
    captions = pathlib.Path(manifest["outputs"]["captionsSrt"]["path"]).read_text()
    assert captions.count("Nailed it.") == 1
    assert pathlib.Path(master).read_bytes().count(b"S1.SH1_c1.mp4") == 1
    assert store.current("Ep1")["scriptVersionId"] == current["scriptVersionId"]
    state = cb_state.production_state("1", "Ep1")
    assert state["packageCurrent"] is True
    assert state["stages"]["script"]["state"] == "approved"
    assert state["stages"]["storyboard"]["state"] == "approved"
    assert state["stages"]["continuity"]["state"] == "approved"
    assert state["stages"]["final"]["state"] == "approved"
    assert len(providers.voice_calls) == 1
    assert len(providers.image_calls) == 2
    assert len(providers.fire_calls) == 1


def test_relay_refuses_before_source_is_approved(world):
    _, _, _ = world
    _voice_and_approve()
    with pytest.raises(R.Refused, match="not approved"):
        R.fire_shot("9", "1.B1.S2", "EpT", log=lambda *a, **k: None)


def test_failed_validation_package_cannot_fire(world, monkeypatch, tmp_path):
    _build_package(tmp_path, valid=False)
    for fn in (lambda: R.voice_scene("9", "EpT"),
               lambda: R.next_shot("9", "EpT"),
               lambda: R.fire_shot("9", "1.B1.S1", "EpT")):
        with pytest.raises(R.Refused, match="validation"):
            fn()


def test_dialogue_shot_refuses_to_fire_without_voice(world):
    prov, _, _ = world
    R.keyframe_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    with pytest.raises(R.Refused, match="Law 5"):
        R.fire_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)


def test_missing_identity_reference_refuses_by_name(world, monkeypatch):
    bad = {k: dict(v) for k, v in CFG.items()}
    bad["Zenny"]["anchor"] = "media/refs/DOES_NOT_EXIST.jpeg"
    monkeypatch.setattr(R, "_characters_cfg", lambda: bad)
    R.voice_scene("9", "EpT", log=lambda *a, **k: None)
    with pytest.raises(R.Refused, match="Zenny"):
        R.keyframe_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)


def test_failure_ladder_unchanged_reroll_then_model_limited(world):
    """§5: rejection archives the whole batch; the reroll uses the UNCHANGED package (no
    auto-appended retake note, no new negatives); two failed batches hard-stop the shot."""
    prov, tmp, _ = world
    _voice_and_approve()
    R.keyframe_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    R.select_keyframe_candidate(
        "9", "1.B1.S1", "A", "EpT", log=lambda *a, **k: None)
    R.approve_keyframe("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    t1 = _token("1.B1.S1", candidates=2)
    R.fire_shot("9", "1.B1.S1", "EpT", candidates=2, spend_token=t1,
                log=lambda *a, **k: None)
    first_prompt = prov.fire_calls[-1]["prompt"]
    first_binding = _led()["1.B1.S1"]["lastBatchBinding"]
    take = _led()["1.B1.S1"]["candidatePaths"][0]
    R.reject_shot("9", "1.B1.S1", "camera too loose on the crash",
                  category="action-timing", episode="EpT", log=lambda *a, **k: None)
    led = _led()["1.B1.S1"]
    assert led["status"] == "designed" and led["batchAttempts"] == 1
    assert led["rejections"][0]["category"] == "action-timing"
    assert len(led["rejections"][0]["archivedCandidates"]) == 2
    assert all(item["contentHashAtGeneration"]
               for item in led["rejections"][0]["archivedCandidates"])
    assert all(item["promptContract"]["integrityVerified"]
               for item in led["rejections"][0]["archivedCandidates"])
    arch_root = tmp / "engine" / "media" / "archive" / "shots_rejected"
    arch = [p for p in arch_root.iterdir() if p.is_dir()]
    assert arch and any(p.name == os.path.basename(take) for p in arch[0].iterdir())
    # the controlled reroll: IDENTICAL binding — the disclosure itself confirms the
    # package is unchanged (rerollOfUnchangedPackage), and the shipped prompt is identical
    t1b = _token("1.B1.S1", candidates=2)
    auth = _led()["1.B1.S1"]["pendingSpendAuth"]
    assert auth["disclosure"]["rerollOfUnchangedPackage"] is True
    assert auth["bindingHash"] == first_binding
    R.fire_shot("9", "1.B1.S1", "EpT", candidates=2, spend_token=t1b,
                log=lambda *a, **k: None)
    assert prov.fire_calls[-1]["prompt"] == first_prompt
    # second failed batch -> MODEL-LIMITED; a third fire refuses by name
    R.reject_shot("9", "1.B1.S1", "still no readable impact",
                  category="action-timing", episode="EpT", log=lambda *a, **k: None)
    assert _led()["1.B1.S1"]["status"] == "model-limited"
    with pytest.raises(R.Refused, match="MODEL-LIMITED"):
        R.fire_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    # and the walk refuses at it too — a model-limited shot blocks, never silently skipped
    with pytest.raises(R.Refused, match="model-limited"):
        R.next_shot("9", "EpT", log=lambda *a, **k: None)


def test_stitch_refuses_with_unapproved_shots(world):
    with pytest.raises(R.Refused, match="unapproved"):
        R.stitch_scene("9", "EpT", log=lambda *a, **k: None)


if __name__ == "__main__":
    import subprocess
    sys_exit = subprocess.call(["python3", "-m", "pytest", __file__, "-q"])
    raise SystemExit(sys_exit)


def test_stale_token_refused_when_spend_envelope_changes(world):
    """Protection 1: changing the authorized candidate count voids the spend token."""
    prov, _, _ = world
    _voice_and_approve()
    R.keyframe_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    R.select_keyframe_candidate(
        "9", "1.B1.S1", "A", "EpT", log=lambda *a, **k: None)
    R.approve_keyframe("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    tok = _token("1.B1.S1")
    with pytest.raises(R.Refused, match="STALE"):
        R.fire_shot("9", "1.B1.S1", "EpT", candidates=2, spend_token=tok,
                    log=lambda *a, **k: None)
    assert len(prov.fire_calls) == 0
    # A fresh disclosure is required after the rejected authorization.
    _token("1.B1.S1")
    d = _led()["1.B1.S1"]["pendingSpendAuth"]["disclosure"]
    assert d["rerollOfUnchangedPackage"] is False


def test_parallel_fire_cannot_claim_the_same_spend_token_twice(world, monkeypatch):
    prov, _, _ = world
    _voice_and_approve()
    R.keyframe_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    R.select_keyframe_candidate(
        "9", "1.B1.S1", "A", "EpT", log=lambda *a, **k: None)
    R.approve_keyframe("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    token = _token("1.B1.S1", candidates=1)

    entered, release = threading.Event(), threading.Event()
    provider = R.cb_gen.generate_video_seedance_ref

    def blocked_provider(*args, **kwargs):
        entered.set()
        assert release.wait(5), "test did not release the provider call"
        return provider(*args, **kwargs)

    monkeypatch.setattr(R.cb_gen, "generate_video_seedance_ref", blocked_provider)
    failures = []

    def first_fire():
        try:
            R.fire_shot("9", "1.B1.S1", "EpT", candidates=1, spend_token=token,
                        log=lambda *a, **k: None)
        except Exception as exc:
            failures.append(exc)

    thread = threading.Thread(target=first_fire)
    thread.start()
    assert entered.wait(5), "first fire never reached the mocked provider"
    with pytest.raises(R.Refused, match="SCENE BUSY"):
        R.fire_shot("9", "1.B1.S1", "EpT", candidates=1, spend_token=token,
                    log=lambda *a, **k: None)
    release.set()
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert failures == []
    assert len(prov.fire_calls) == 1


def test_batch_resume_is_idempotent_never_repays(world):
    """Protection 2: two of three complete, the third fails -> resume generates ONLY the
    missing candidate under the ORIGINAL token; completed candidates never regenerate."""
    prov, tmp, _ = world
    _voice_and_approve()
    R.keyframe_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    R.select_keyframe_candidate(
        "9", "1.B1.S1", "A", "EpT", log=lambda *a, **k: None)
    R.approve_keyframe("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    tok = _token("1.B1.S1")
    real = R.cb_gen.generate_video_seedance_ref
    calls = {"n": 0}
    def flaky(prompt, image_urls, out="c.mp4", **k):
        calls["n"] += 1
        if out.endswith("_c3.mp4") and calls["n"] <= 3:
            raise RuntimeError("provider 500")
        return real(prompt, image_urls, out=out, **k)
    import pytest as _pt
    orig = R.cb_gen.generate_video_seedance_ref
    R.cb_gen.generate_video_seedance_ref = flaky
    try:
        with _pt.raises(R.Refused, match="resumable"):
            R.fire_shot("9", "1.B1.S1", "EpT", spend_token=tok, log=lambda *a, **k: None)
        led = _led()["1.B1.S1"]
        assert led["batch"]["status"] == "generating"
        assert led["batch"]["done"] == [1, 2]
        assert led["batch"]["failed"][0]["candidate"] == 3          # failure persisted
        # Legacy/session records may carry JSON null rather than omitting the counter.
        # Completing a resumable batch must normalize that state, not lose landed media.
        led["candidatesGenerated"] = None
        # a resume WITHOUT the original token is refused
        with _pt.raises(R.Refused, match="original spend token"):
            R.fire_shot("9", "1.B1.S1", "EpT", spend_token="deadbeef" * 4,
                         log=lambda *a, **k: None)
        # resume with the original token: ONLY candidate 3 generates
        before = calls["n"]
        R.fire_shot("9", "1.B1.S1", "EpT", spend_token=tok, log=lambda *a, **k: None)
        assert calls["n"] == before + 1                             # one call, no repays
        assert _led()["1.B1.S1"]["status"] == "candidates-pending"
        assert len(_led()["1.B1.S1"]["candidatePaths"]) == 3
    finally:
        R.cb_gen.generate_video_seedance_ref = orig


def test_unconfirmed_billing_profile_hard_blocks_all_paid_generation(world, monkeypatch):
    """Protection 5: an unconfirmed billing profile is a REFUSAL, never a warning."""
    import cb_costs
    monkeypatch.setattr(cb_costs, "load_billing_profile",
                         lambda provider=None: {"planConfirmed": False,
                                                 "cadenceConfirmed": True})
    with pytest.raises(R.Refused, match="UNCONFIRMED"):
        R.voice_scene("9", "EpT", log=lambda *a, **k: None)
    with pytest.raises(R.Refused, match="UNCONFIRMED"):
        R.keyframe_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    with pytest.raises(R.Refused, match="UNCONFIRMED"):
        R.fire_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)


def test_animation_direction_goes_stale_when_approved_opening_frame_changes(world):
    """The cinematic prompt is bound to its direct media inputs, not only package text."""
    _voice_and_approve()
    R.keyframe_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    R.select_keyframe_candidate(
        "9", "1.B1.S1", "A", "EpT", log=lambda *a, **k: None)
    R.approve_keyframe(
        "9", "1.B1.S1", "EpT", reviewed_by="TestReviewer",
        log=lambda *a, **k: None)
    pkg, path = R.load_pkg("9", "EpT")
    shot = R._shot(pkg, "1.B1.S1")
    ledger = R._ledger(pkg, shot["shotId"])
    approved = ledger["departmentWork"]["animation"]["approved"]
    approved["inputSignature"] = R._animation_input_signature(pkg, shot, "9", "EpT")
    R._save(pkg, path)

    pathlib.Path(ledger["keyframeApproval"]["path"]).write_bytes(b"CHANGED_OPENING_FRAME")
    pkg, _ = R.load_pkg("9", "EpT")
    with pytest.raises(R.Refused, match="Animation direction is stale"):
        R._approved_seedance_prompt(pkg, R._shot(pkg, "1.B1.S1"))


def test_completed_batch_can_be_approved_after_direction_runtime_changes(world):
    """Human approval binds returned pixels to their fired inputs, not a later text runtime."""
    _voice_and_approve()
    R.keyframe_shot("9", "1.B1.S1", "EpT", log=lambda *a, **k: None)
    R.select_keyframe_candidate(
        "9", "1.B1.S1", "A", "EpT", log=lambda *a, **k: None)
    R.approve_keyframe(
        "9", "1.B1.S1", "EpT", reviewed_by="TestReviewer",
        log=lambda *a, **k: None)
    token = _token("1.B1.S1", candidates=1)
    R.fire_shot(
        "9", "1.B1.S1", "EpT", candidates=1, spend_token=token,
        log=lambda *a, **k: None)

    pkg, path = R.load_pkg("9", "EpT")
    animation = R._ledger(pkg, "1.B1.S1")["departmentWork"]["animation"]["approved"]
    animation["inputSignature"] = {**animation["inputSignature"], "model": "retired-model"}
    R._save(pkg, path)

    R.approve_shot(
        "9", "1.B1.S1", 1, "EpT", reviewed_by="TestReviewer",
        log=lambda *a, **k: None)
    pkg, _ = R.load_pkg("9", "EpT")
    ledger = R._ledger(pkg, "1.B1.S1")
    assert ledger["status"] == "approved"
    assert ledger["approvedCandidate"] == 1
    assert R._animation_approval_status(
        pkg, R._shot(pkg, "1.B1.S1"), "9", "EpT")["current"] is True


def test_reference_slot_validator_accepts_possessive_character_name():
    """Keen's Mum is one canonical role, not a conflicting assignment to Keen."""
    R._require_prompt_slot_text_consistency(
        "@图2 defines Keen's Mum's complete turnaround and exact identity.",
        [{"slot": "@图2", "role": "Keen's Mum"}],
    )


def test_reference_slot_validator_still_blocks_real_character_swap():
    with pytest.raises(R.Refused, match="sealed as Keen's Mum, but prompt text assigns Keen"):
        R._require_prompt_slot_text_consistency(
            "@图2 is Keen and controls his identity.",
            [{"slot": "@图2", "role": "Keen's Mum"}],
        )
