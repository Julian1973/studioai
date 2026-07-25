#!/usr/bin/env python3
"""Zero-cost tests for cb_render's shot-fire helpers. No real API calls, no real fire_shot
invocation (that function does file I/O, provider uploads and gate checks far beyond this
file's own scope) — these test the small, pure, independently-callable pieces directly."""
import json
import cb_render as R


def test_handle_duration_floors_at_handle_total_with_no_voice(monkeypatch):
    """A shot with no voice track (None, or a path that doesn't resolve) still renders at
    the full HANDLE_TOTAL — the archived beat-level doctrine's own universal behaviour,
    restored: every clip gets the same handle regardless of content."""
    monkeypatch.setattr(R, "_audio_dur", lambda p: 0.0)
    assert R._handle_duration(None) == R.HANDLE_TOTAL
    assert R._handle_duration("nonexistent.mp3") == R.HANDLE_TOTAL


def test_handle_duration_floors_at_handle_total_for_a_short_real_take(monkeypatch):
    """REGRESSION 2026-07-19: S1.SH1's real V3 take (9.68s) was fired against a 7.0s-
    designed clip with zero crash or warning — durationSec was a design-time estimate never
    reconciled against the actual recorded voice length before firing the paid render. A
    take shorter than HANDLE_TOTAL - HANDLE_SETTLE (13s) must still floor at the full 15s,
    exactly as this real 9.68s take should have."""
    monkeypatch.setattr(R, "_audio_dur", lambda p: 9.68)
    assert R._handle_duration("vo.mp3") == 15.0


def test_handle_duration_stretches_past_handle_total_for_a_long_real_take(monkeypatch):
    """RE-PINNED 2026-07-24: the original expectation (16.5/22.0 — unbounded stretch past
    the take) predates THE PROVIDER CAP (2026-07-23, cb_render._handle_duration: BytePlus/
    Seedance 400s outright on any duration > 15s, found live on a real fire). The stretch
    principle still holds BELOW the cap; at/above it the cap wins, always."""
    monkeypatch.setattr(R, "_audio_dur", lambda p: 14.5)
    assert R._handle_duration("vo.mp3") == 15.0   # 14.5+2=16.5 -> provider cap clamps to 15
    monkeypatch.setattr(R, "_audio_dur", lambda p: 20.0)
    assert R._handle_duration("vo.mp3") == 15.0   # cap, never 22.0
    monkeypatch.setattr(R, "_audio_dur", lambda p: 11.0)
    assert R._handle_duration("vo.mp3") == 15.0   # below-cap floor: max(15, 11+2) = 15


def test_handle_duration_matched_master_fires_exactly_the_master_length(monkeypatch):
    """THE DURATION-MATCHED MASTER (2026-07-24, S1.SH3 retiming): a padded @Audio1 master
    built to exactly the shot's own durationSec already contains its lead-in and settle
    tail — the fire duration IS the master's length, never master+HANDLE_SETTLE (which
    produced 2s of video past the audio's own end, an undefined tail)."""
    monkeypatch.setattr(R, "_audio_dur", lambda p: 7.0)
    assert R._handle_duration("vo_master7.mp3", 7.0) == 7.0      # matched -> exact
    monkeypatch.setattr(R, "_audio_dur", lambda p: 15.0)
    assert R._handle_duration("vo_master15.mp3", 15.0) == 15.0   # SH2's case, unchanged
    monkeypatch.setattr(R, "_audio_dur", lambda p: 1.76)
    assert R._handle_duration("vo.mp3", 7.0) == 7.0              # raw short take: floor wins
    monkeypatch.setattr(R, "_audio_dur", lambda p: 6.0)
    assert R._handle_duration("vo.mp3", 7.0) == 8.0              # NOT matched: 6+2 > floor


def test_handle_duration_matches_the_real_s1sh1_take_end_to_end():
    """End-to-end proof against the real, un-mocked audio file this bug was found on."""
    import pathlib
    vo = pathlib.Path(__file__).resolve().parent / "media" / "shots" / "Ep1_S1.SH1_vo.mp3"
    if not vo.exists():
        return  # media not present in this checkout — the mocked tests above already cover the logic
    assert R._handle_duration(str(vo)) == 15.0


def test_fire_shot_overrides_durationSec_before_any_downstream_read(monkeypatch, tmp_path):
    """The actual choke point: fire_shot must override shot['durationSec'] with the computed
    handle duration BEFORE _binding_hash/_sealed_envelope/the provider call ever see it —
    proven by stubbing everything around the override and reading what reaches the sealed
    envelope, without ever firing a real candidate loop."""
    import json
    # GOLD BUILD (2026-07-24): fire_shot now runs check_formula_structure on the resolved
    # prompt BEFORE the duration override — the fixture prompt must be a valid (dialogue-
    # free) formula card or the gate refuses before the property under test ever runs.
    shot = {"shotId": "S1.SHX", "durationSec": 7.0,
            "seedancePrompt": ("Shot 1: Static wide. Fuzzby hovers, wobbles, and settles."
                                "\n\nHOLD on the settle, about 2 seconds of silence."),
            "referenceSlots": {"@图1": "opening keyframe", "@Audio1": "voice track"},
            "dialogueLines": []}
    pkg = {"shots": [shot], "continuityLedger": [{"shotId": "S1.SHX", "voPath": "vo.mp3"}],
           "validation": {"passed": True}, "sceneNumber": 1, "revision": 1}
    path = tmp_path / "pkg.json"
    path.write_text(json.dumps(pkg))

    monkeypatch.setattr(R, "load_pkg", lambda scene, episode="Ep1": (pkg, path))
    monkeypatch.setattr(R, "_require_valid", lambda p: None)
    monkeypatch.setattr(R, "_require_current_lineage", lambda p, s, e: None)
    monkeypatch.setattr(R, "_require_confirmed_billing", lambda provider: None)
    monkeypatch.setattr(R, "_resolve_seedance_prompt",
                        lambda p, s, scene, episode="Ep1": (s["seedancePrompt"], False))
    monkeypatch.setattr(R, "_audio_dur", lambda p: 9.68)
    monkeypatch.setattr(R, "_fresh_validation", lambda pkg, episode: None)

    captured = {}
    def fake_binding_hash(pkg, shot, led, imgs, anchor, candidates, fast, resolution="720p"):
        captured["binding_durationSec"] = shot["durationSec"]
        return "fakehash", 1.0
    def fake_sealed_envelope(pkg, shot, led, imgs, anchor, candidates, fast, per, resolution="720p"):
        captured["envelope_durationSec"] = shot["durationSec"]
        return {"durationSec": shot["durationSec"], "prompt": shot["seedancePrompt"]}, "fakeenvhash"
    monkeypatch.setattr(R, "_binding_hash", fake_binding_hash)
    monkeypatch.setattr(R, "_sealed_envelope", fake_sealed_envelope)
    monkeypatch.setattr(R, "_anchor_for", lambda pkg, shot: "anchor.png")
    monkeypatch.setattr(R, "_characters_cfg", lambda: {})
    monkeypatch.setattr(R, "_slot_paths", lambda *a, **k: ["anchor.png"])
    monkeypatch.setattr(R, "_save", lambda pkg, path: None)

    try:
        R.fire_shot(1, "S1.SHX", episode="Ep1", candidates=1)
    except R.Refused:
        pass  # expected — this stub stops short of issuing a real spend token; the override already ran
    # RE-PINNED 2026-07-24: the original 15.0 expectation encoded the retired unconditional
    # HANDLE_TOTAL floor. Since Julian's split-generation directive (2026-07-23), the shot's
    # OWN durationSec (7.0 here) is the floor — the mocked 9.7s take + 2s settle = 11.7 wins.
    # The property under test is unchanged: the override lands BEFORE binding/envelope.
    assert captured.get("binding_durationSec") == 11.7
    assert captured.get("envelope_durationSec") == 11.7


def _minimal_shot(shot_id, beat_code, speaker="Fuzzby", text="Do I look official?"):
    char_state = {"character": speaker, "screenZone": "centre", "facing": "camera",
                  "pose": "hovering", "expression": "neutral", "visibleMarks": [], "heldProps": []}
    return {
        "shotId": shot_id, "beatCode": beat_code, "durationSec": 6.0,
        "purpose": "test", "performanceAssignment": "Fuzzby performs.", "camera": "static wide",
        "openingPose": "Fuzzby hovers.", "sourceType": "opener", "sourceShotId": None,
        "cutInMotivation": None,
        "dialogueBinding": f"{speaker} speaks his line." if text else None,
        "dialogueLines": ([{"speaker": speaker, "exactText": text, "delivery": "plain",
                             "startSec": 0.0, "endSec": 2.0}] if text else []),
        "visualPayoff": "a payoff",
        "physicalStaging": {"staysVisible": "yes", "contactAndWeight": "n/a",
                             "payoffShape": "n/a", "prohibitedStaging": []},
        "prohibited": [],
        "charactersInFrame": [speaker], "continuityIn": None,
        "continuityOut": {"lighting": "warm", "cameraSide": "left", "characters": [char_state]},
        # cutPace is REQUIRED (2026-07-21 cut-pace mandate) — no default, must fire every time.
        "cutPace": "single_continuous_take", "cutPaceReason": "test fixture default.",
        "internalCuts": [],
    }


def test_sequential_promotion_pending_lines_do_not_block_a_ready_shot(monkeypatch, tmp_path):
    """REGRESSION 2026-07-20 (Julian — "This is why we have scenes and shots. Shot 1 has to
    be shot one then we move shot 2 etc, not all at once."): a beat's dialogue lines not yet
    claimed by any PROMOTED shot must not hard-block firing an already-complete, unrelated
    shot — as long as the storyboard shows those lines' shots exist (even unpromoted) or the
    beat simply hasn't been designed yet. Two beats: BEAT-A is fully promoted (its one shot,
    S1.SH1, claims its one line) and must validate clean; BEAT-B has a real second line that
    belongs to a storyboard shot (S1.SH2) never promoted into the package — this must WARN,
    never ERROR, and must never flip report['passed'] to False."""
    import cb_engine as E
    import cb_render as R

    # 2026-07-22 UPDATE: _fresh_validation's beats now come from the real storyboard file
    # (_beats_for_fresh_validation, the orphaned-beat-package fix) rather than a same-named-
    # episode file discovered by an unrelated glob — beats live INSIDE the storyboard's own
    # "beats" key (beatId/exactDialogue) now, alongside its "shots" key, not injected via a
    # separate E._load_pkg mock.
    monkeypatch.setattr(R, "_characters_cfg", lambda: {"Fuzzby": {}, "Zenny": {}})

    sb_path = tmp_path / "Ep1_scene1_storyboard.json"
    sb_path.write_text(json.dumps({
        "beats": [
            {"beatId": "BEAT-A", "exactDialogue": ["Fuzzby: Do I look official?"]},
            {"beatId": "BEAT-B", "exactDialogue": ["Zenny: A storm's coming."]},
        ],
        "shots": [
            {"shotId": "S1.SH1", "beatIds": ["BEAT-A"]},
            {"shotId": "S1.SH2", "beatIds": ["BEAT-B"]},  # exists in the storyboard, NOT promoted
        ]}))
    monkeypatch.setattr(R, "_storyboard_path", lambda scene, episode="Ep1": sb_path)

    pkg = {"sceneNumber": 1, "shots": [_minimal_shot("S1.SH1", "BEAT-A")],
           }

    report = R._fresh_validation(pkg, "Ep1")
    assert report["passed"] is True
    drop_issues = [i for i in report["issues"] if i["code"] == "DIALOGUE_LINE_DROPPED"]
    assert len(drop_issues) == 1
    assert drop_issues[0]["severity"] == "WARNING"
    assert "PENDING" in drop_issues[0]["message"]
    assert "A storm's coming" in drop_issues[0]["message"]


def test_sequential_promotion_still_hard_blocks_a_genuine_drop(monkeypatch, tmp_path):
    """The other half of the same fix: once a beat's shots are ALL promoted, a line that's
    still unclaimed is a real authoring bug, not a pending-production state — this must
    still hard-block exactly as before."""
    import cb_engine as E
    import cb_render as R

    # 2026-07-22 UPDATE: see the sibling test above — beats now live inside the storyboard's
    # own "beats" key, not injected via a separate E._load_pkg mock.
    monkeypatch.setattr(R, "_characters_cfg", lambda: {"Fuzzby": {}, "Zenny": {}})

    sb_path = tmp_path / "Ep1_scene1_storyboard.json"
    sb_path.write_text(json.dumps({
        "beats": [{"beatId": "BEAT-A", "exactDialogue": [
            "Fuzzby: Do I look official?", "Zenny: Yes, officially nuts!"]}],
        "shots": [{"shotId": "S1.SH1", "beatIds": ["BEAT-A"]}]}))
    monkeypatch.setattr(R, "_storyboard_path", lambda scene, episode="Ep1": sb_path)

    # S1.SH1 is the beat's ONLY storyboard shot and IS promoted, but only claims one of
    # the beat's two locked lines — Zenny's line is a genuine drop, not a pending one.
    pkg = {"sceneNumber": 1, "shots": [_minimal_shot("S1.SH1", "BEAT-A")],
           }

    try:
        R._fresh_validation(pkg, "Ep1")
        assert False, "expected Refused"
    except R.Refused as e:
        assert "DIALOGUE_LINE_DROPPED" in str(e)


# ── THE BYTEPLUS PROVIDER SWITCH — DISCLOSURE HONESTY (2026-07-22) ────────────────────────
# THE CORE LAW: nothing fires without an honest disclosure of what will actually happen.
# _binding_hash/_sealed_envelope are what Julian sees (and what the spend token binds to)
# BEFORE a real render fires — both used to hardcode provider="fal"/endpoint="bytedance/
# seedance-2.0/..." regardless of which provider cb_gen.VIDEO_PROVIDER would actually route
# to, which would have shown a false disclosure the instant the default flipped to byteplus.
# These prove both functions now read the real, live provider at disclosure time.

def _rp_fixture(tmp_path):
    """A minimal real shot/pkg/led + real on-disk files (both functions call _file_md5,
    which needs a real file to hash — no mocking the hash itself, since that's the whole
    point of the binding: it must reflect the ACTUAL bytes that will be sent)."""
    anchor = tmp_path / "anchor.png"; anchor.write_bytes(b"ANCHOR")
    ref1 = tmp_path / "ref1.png"; ref1.write_bytes(b"REF1")
    vo = tmp_path / "vo.mp3"; vo.write_bytes(b"VO")
    shot = {"shotId": "S1.SHX", "durationSec": 15.0, "seedancePrompt": "a raw prompt",
            "referenceSlots": {"@图1": "opening keyframe", "@Audio1": "voice track"}}
    pkg = {"shots": [shot], "revision": 1}
    led = {"voPath": str(vo)}
    return pkg, shot, led, [str(ref1)], str(anchor)


def test_binding_hash_reflects_the_live_video_provider(monkeypatch, tmp_path):
    import cb_gen
    pkg, shot, led, imgs, anchor = _rp_fixture(tmp_path)

    monkeypatch.setattr(cb_gen, "VIDEO_PROVIDER", "byteplus")
    _, per_byteplus = R._binding_hash(pkg, shot, led, imgs, anchor, 1, fast=False)
    payload_bp = json.loads(json.dumps(
        {"provider": cb_gen.VIDEO_PROVIDER}))  # sanity: the module state really is byteplus here
    assert payload_bp["provider"] == "byteplus"

    monkeypatch.setattr(cb_gen, "VIDEO_PROVIDER", "fal")
    _, per_fal = R._binding_hash(pkg, shot, led, imgs, anchor, 1, fast=False)

    # different provider -> different disclosed rate -> a genuinely different binding hash,
    # never the old hardcoded-"fal" value regardless of the real switch
    monkeypatch.setattr(cb_gen, "VIDEO_PROVIDER", "byteplus")
    h_bp, _ = R._binding_hash(pkg, shot, led, imgs, anchor, 1, fast=False)
    monkeypatch.setattr(cb_gen, "VIDEO_PROVIDER", "fal")
    h_fal, _ = R._binding_hash(pkg, shot, led, imgs, anchor, 1, fast=False)
    assert h_bp != h_fal


def test_video_provider_rate_key_switches_with_cb_gen_video_provider(monkeypatch):
    import cb_gen
    monkeypatch.setattr(cb_gen, "VIDEO_PROVIDER", "byteplus")
    assert R._video_provider_rate_key(fast=False) == "seedance_byteplus_ark_per_sec"
    assert R._video_provider_rate_key(fast=True) == "seedance_byteplus_ark_per_sec"
    monkeypatch.setattr(cb_gen, "VIDEO_PROVIDER", "fal")
    assert R._video_provider_rate_key(fast=False) == "seedance_standard_per_sec"
    assert R._video_provider_rate_key(fast=True) == "seedance_fast_per_sec"


def test_sealed_envelope_reflects_the_live_video_provider(monkeypatch, tmp_path):
    import cb_gen
    pkg, shot, led, imgs, anchor = _rp_fixture(tmp_path)

    monkeypatch.setattr(cb_gen, "VIDEO_PROVIDER", "byteplus")
    env_bp, _ = R._sealed_envelope(pkg, shot, led, imgs, anchor, 1, fast=False, per=1.0)
    assert env_bp["provider"] == "byteplus"
    assert env_bp["model"] == "dreamina-seedance-2-0-260128"
    assert env_bp["endpoint"] == cb_gen.BYTEPLUS_ARK_TASKS_URL

    monkeypatch.setattr(cb_gen, "VIDEO_PROVIDER", "fal")
    env_fal, _ = R._sealed_envelope(pkg, shot, led, imgs, anchor, 1, fast=False, per=1.0)
    assert env_fal["provider"] == "fal"
    assert env_fal["model"] == "bytedance/seedance-2.0"
    assert env_fal["endpoint"] == "bytedance/seedance-2.0/reference-to-video"

    # a fast-tier byteplus request names the fast model id
    monkeypatch.setattr(cb_gen, "VIDEO_PROVIDER", "byteplus")
    env_bp_fast, _ = R._sealed_envelope(pkg, shot, led, imgs, anchor, 1, fast=True, per=1.0)
    assert env_bp_fast["model"] == "dreamina-seedance-2-0-fast-260128"


def test_image_model_label_reflects_the_live_seedream_host(monkeypatch):
    import cb_gen
    monkeypatch.setattr(cb_gen, "IMAGE_PROVIDER", "seedream")
    monkeypatch.setattr(cb_gen, "SEEDREAM_HOST", "byteplus")
    assert R._image_model_label() == f"seedream:{cb_gen.BYTEPLUS_SEEDREAM_MODEL}:2K"

    monkeypatch.setattr(cb_gen, "SEEDREAM_HOST", "fal")
    assert R._image_model_label() == f"seedream:{cb_gen.SEEDREAM_ENDPOINT}:2K"

    # nanobanana model family is unaffected by SEEDREAM_HOST either way
    monkeypatch.setattr(cb_gen, "IMAGE_PROVIDER", "nanobanana")
    assert R._image_model_label() == f"nanobanana:{cb_gen.IMAGE_MODEL}:2K"


def test_drift_vocab_is_advisory_not_a_refusal():
    """THE DRIFT-VOCABULARY BAN, DEMOTED (2026-07-25, Julian's no-straitjacket ruling —
    "remove a lot of the guardrails that suffocate the creative prompting").

    The original evidence stands: these eleven words triggered real, documented drift
    (S1.SH2 campaign, regressed live on S1.SH3). What changed is the RESPONSE. A blacklist
    that refuses a prompt for containing "dusk" also bans eleven legitimate pieces of light
    vocabulary from a show that contains a storm at sea and a sunrise — and the thing that
    actually holds the look was never the blacklist, it is the plate reference plus the
    scene's own authored lighting field, both of which still ship on every prompt.

    So: hits are RETURNED and warned about, never raised. Every fire lands in the verdict
    corpus, so if drift returns it shows up in Julian's own verdicts and the block can be
    restored with fresh evidence rather than from memory."""
    for bad in ("warm saturated sunset light", "shafts of sunset light", "golden hour glow",
                "at dusk in the meadow", "late afternoon warmth", "amber light"):
        hits = R._check_no_drift_vocab(bad)          # must NOT raise
        assert hits, f"{bad!r} should still be detected and warned about"
    for ok in ("Fresh, high-key daylight with a white sun high and outside the frame",
               "a warm smile", "golden pollen moustache"):
        assert R._check_no_drift_vocab(ok) == []


def test_only_the_voice_laws_still_block_a_prompt():
    """THE NO-STRAITJACKET PASS (2026-07-25). The formula gate refuses exactly three
    things — the ones that protect the V3 voice pipeline, which is where this studio is
    measurably ahead and where a mistake is unrecoverable. Everything it used to refuse on
    FORM (shot labelling, Cut-to counts, the closing hold, duration prose, a word ceiling)
    now comes back as advisory so a human decides."""
    import pytest
    # a bare, unlabelled, hold-less, 900-word continuous take with no dialogue: fires.
    long_take = "A single unbroken take. " + ("Fuzzby banks hard past the stem. " * 150)
    advisories = R.check_formula_structure(long_take, [])
    assert advisories, "form problems should be reported, just not refused"
    assert any("Shot 1" in a for a in advisories)

    # the three that still block, each on its own
    lines = [{"speaker": "Fuzzby", "exactText": "Nailed it."}]
    for bad, why in [
        ("Shot 1: he lands. @Audio1 carries the voice.", "missing audio-law header"),
        ("ENGLISH DIALOGUE ONLY, spoken in English. Shot 1: he lands.", "no @Audio1"),
        ("ENGLISH DIALOGUE ONLY, spoken in English. @Audio1 is the sole source.\n"
         "FUZZBY: Nailed it.", "inline dialogue"),
    ]:
        with pytest.raises(R.Refused):
            R.check_formula_structure(bad, lines)

    # and a clean one passes with dialogue present
    good = ("ENGLISH DIALOGUE ONLY, spoken in English. @Audio1 is the sole source of "
            "dialogue, wording, voice, performance and timing. Shot 1: he lands.")
    R.check_formula_structure(good, lines)


def test_audit_shot_integrity_clean_on_real_scene1():
    """Standing regression pin: the real Scene 1 package must stay free of dead links and
    drift vocabulary in every live prompt — the exact state the 2026-07-24 purge left it in.
    A failure here means an old prompt style or broken path re-entered the pipeline."""
    findings = R.audit_shot_integrity(1, "Ep1", log=lambda *a, **k: None)
    assert findings == [], f"integrity audit regressed: {findings}"


# ══ THE CLIP/CARD SEPARATION AT THE FIRE DOOR (Julian's directive, 2026-07-25) ══
def test_member_card_is_not_independently_fireable():
    """A card named by another card's composedOf is a MEMBER of that generation clip.
    Firing it alone would render and BILL the same camera shot twice."""
    pkg = {"shots": [{"shotId": "S1.SH1", "composedOf": ["S1.SH2", "S1.SH3"]},
                     {"shotId": "S1.SH2"}, {"shotId": "S1.SH3"}]}
    for member in ("S1.SH2", "S1.SH3"):
        try:
            R._require_own_clip(pkg, member)
        except R.Refused as e:
            assert "S1.SH1" in str(e), "the refusal must name the clip to fire instead"
            continue
        raise AssertionError(f"{member} was fireable despite being a member card")
    R._require_own_clip(pkg, "S1.SH1")          # the owning clip itself is fireable


def test_own_clip_guard_never_refuses_an_ordinary_package():
    """Every existing package declares no composedOf — the guard must be a pure no-op,
    and must not raise on a partial/legacy shot record either (a guard that crashes on
    an unrelated schema gap refuses fires it has no business refusing)."""
    pkg = {"shots": [{"shotId": "S1.SH1", "durationSec": 7.0},
                     {"shotId": "S1.SH2"}, {"notAShotAtAll": True}]}
    R._require_own_clip(pkg, "S1.SH1")
    R._require_own_clip(pkg, "S1.SH2")


def test_department_signature_is_independent_of_working_directory(tmp_path, monkeypatch):
    """THE CWD BUG (2026-07-25, found live — it cost Julian an evening).

    _walk_for_signature hashes file CONTENT, so any relative "media/..." path in the
    dependency context made the signature depend on which process asked. engine/ resolved
    and hashed the bytes; cb-studio/ (where serve.py actually runs) did not, and hashed
    the bare string — so an Animation direction Julian approved through one process was
    PERMANENTLY STALE to the other, on byte-identical data, reporting only "an upstream
    input changed" with no way to see that nothing had.

    Two real sites shared the bug: the isfile() probe here, and _audio_dur's ffprobe (which
    silently measured 0.0 from the wrong cwd and put a different measuredAudioDurationSec
    into the same signature). Both now resolve via _engine_path.
    """
    import cb_render as R
    rel = "media/__cwd_probe__.bin"
    target = R.HERE / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"content that must be hashed identically from anywhere")
    try:
        ctx = {"someAsset": rel, "nested": {"refs": [{"path": rel}]}}
        from_engine = R._department_signature(ctx)
        monkeypatch.chdir(tmp_path)          # any cwd that is NOT the engine dir
        assert R._department_signature(ctx) == from_engine, \
            "the department signature still depends on the caller's working directory"
        # and it must genuinely be hashing CONTENT, not merely the path string
        walked = R._walk_for_signature(rel)
        assert isinstance(walked, dict) and walked.get("contentMd5"), \
            "a relative media path is no longer resolved to its bytes at all"
    finally:
        target.unlink(missing_ok=True)


def _fixture(name):
    import cb_render as R
    return (R.HERE.parent / "shows" / "crystal-bears" / "creative" / name).read_text(encoding="utf-8")


def test_stasis_check_is_calibrated_on_a_real_good_and_a_real_bad_prompt():
    """THE STASIS LOAD CHECK (2026-07-25), pinned against the two REAL prompts it was
    calibrated on — never a synthetic fixture, because the whole value of the threshold is
    that it sits between a take Julian approved and a take an external craft review called
    "dramatically immobilised".

    The keeper direction matters most: a first draft of this check flagged the APPROVED SH1
    prompt (it read "Zenny travels physically with the flower" as a contradiction, when
    that is the anchor working correctly). A craft check that fails the known-good take
    teaches everyone to ignore it, which is worse than having no check at all.
    """
    import cb_render as R
    cast = ("Fuzzby", "Zenny")

    keeper = R.check_stasis_load(_fixture("SH1_KEEPER_EXEMPLAR.txt"), characters=cast)
    assert keeper == [], f"the check flags the APPROVED keeper: {keeper}"

    laboured = R.check_stasis_load(_fixture("fixtures/SH2_LABOURED_FIXTURE.txt"),
                                   characters=cast)
    joined = " ".join(laboured)
    assert any("STASIS LOAD" in a for a in laboured), "density signal missed the laboured prompt"
    assert "two-shot" in joined, "the repeated framing lock was not named"
    assert "GEOGRAPHY CONTRADICTION on Zenny" in joined, \
        "the anchored-and-hovering contradiction was not caught"


def test_stasis_check_never_invents_a_camera_leader():
    """'the camera follows at a readable distance' must never report the leader as 'at' —
    a preposition presented to Julian as a character. Caught in the first draft."""
    import cb_render as R
    out = R.check_stasis_load(
        "The camera follows at a readable distance. Zenny remains anchored to her flower.",
        characters=("Fuzzby", "Zenny"))
    assert not any("follows at" in a for a in out), out
