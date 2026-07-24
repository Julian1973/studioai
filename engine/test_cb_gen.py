#!/usr/bin/env python3
"""Zero-cost tests for cb_gen.generate_image()'s provider dispatcher (2026-07-09, THE PROVIDER SWITCH —
Seedream 5 Pro is now the default keyframe model, NB2 kept live for rollback via CB_IMAGE_PROVIDER). No
real API calls — the two provider implementations are monkeypatched, so this proves the ROUTING logic
only, exactly matching the manual verification run before this file was written."""
import cb_gen

PASS = 0
FAIL = 0

def check(label, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}")

_orig_provider = cb_gen.IMAGE_PROVIDER
# REGRESSION FIX (2026-07-22, found while adding the BytePlus image tests below): this script-style
# block runs unconditionally at MODULE-IMPORT time (pytest imports every test_*.py file to collect it,
# executing all top-level code) — _stub() below permanently overwrote cb_gen._generate_image_seedream/
# _generate_image_nanobanana with fake stubs, and _reset() never restored them, only IMAGE_PROVIDER.
# Under `python3 test_cb_gen.py` standalone this was invisible (the process exits right after), but
# under `pytest` (which runs many test files in one process) it silently corrupted cb_gen's real
# dispatcher for every test that ran afterward — exactly the class of cross-test-file pollution this
# whole project's history has repeatedly found and fixed (e.g. rule 59's test_cb_scene.py/
# test_cb_post.py chdir leak). Now saved and restored alongside IMAGE_PROVIDER.
_orig_generate_image_seedream = cb_gen._generate_image_seedream
_orig_generate_image_nanobanana = cb_gen._generate_image_nanobanana

def _reset():
    cb_gen.IMAGE_PROVIDER = _orig_provider
    cb_gen._generate_image_seedream = _orig_generate_image_seedream
    cb_gen._generate_image_nanobanana = _orig_generate_image_nanobanana

def _stub():
    calls = []
    cb_gen._generate_image_seedream = lambda *a, **k: calls.append(("seedream", a, k)) or "SEEDREAM_OUT"
    cb_gen._generate_image_nanobanana = lambda *a, **k: calls.append(("nanobanana", a, k)) or "NB2_OUT"
    return calls

print("=== default provider (seedream) routes new calls to Seedream ===")
_reset()
calls = _stub()
r = cb_gen.generate_image("prompt", ["ref1.png"], "16:9", "out1.png", production_route="cb_render")
check("default IMAGE_PROVIDER is 'seedream'", cb_gen.IMAGE_PROVIDER == "seedream")
check("returns the seedream path", r == "SEEDREAM_OUT")
check("routed to the seedream implementation", calls and calls[-1][0] == "seedream")

print("=== an explicit model= kwarg forces the nanobanana path regardless of IMAGE_PROVIDER ===")
_reset()
calls = _stub()
r = cb_gen.generate_image("prompt", ["ref2.png"], "16:9", "out2.png", model="gemini-3.1-flash-image", production_route="cb_render")
check("returns the nanobanana path", r == "NB2_OUT")
check("routed to the nanobanana implementation", calls and calls[-1][0] == "nanobanana")
check("model kwarg forwarded through", calls[-1][1][4] == "gemini-3.1-flash-image")

print("=== CB_IMAGE_PROVIDER=nanobanana (rollback) routes with no explicit model ===")
_reset()
cb_gen.IMAGE_PROVIDER = "nanobanana"
calls = _stub()
r = cb_gen.generate_image("prompt", ["ref3.png"], "16:9", "out3.png", production_route="cb_render")
check("returns the nanobanana path", r == "NB2_OUT")
check("routed to the nanobanana implementation", calls and calls[-1][0] == "nanobanana")
check("falls back to the module default IMAGE_MODEL", calls[-1][1][4] == cb_gen.IMAGE_MODEL)
_reset()

print("=== cb_costs.estimate_image_cost() matches the (now three-way) provider switch exactly ===")
import cb_costs
check("default (seedream/fal) returns the seedream rate", cb_costs.estimate_image_cost() == cb_costs.RATES["seedream5pro_image"][0])
check("provider='nanobanana2' returns the nanobanana rate", cb_costs.estimate_image_cost(provider="nanobanana2") == cb_costs.RATES["nanobanana2_image"][0])
check("provider='seedream5pro_byteplus' returns the byteplus rate", cb_costs.estimate_image_cost(provider="seedream5pro_byteplus") == cb_costs.RATES["seedream5pro_byteplus_image"][0])
check("the three rates are genuinely distinct (not a copy-paste no-op)",
      len({cb_costs.RATES["seedream5pro_image"][0], cb_costs.RATES["nanobanana2_image"][0],
           cb_costs.RATES["seedream5pro_byteplus_image"][0]}) == 3)

_reset()   # leave cb_gen's real dispatch functions intact for every pytest test that runs after this

print(f"\n{PASS}/{PASS+FAIL} passed.")
if FAIL:
    raise SystemExit(f"{FAIL} FAILURE(S)")
print("ALL PASS")


# ── THE BILLING PROFILE (Julian's directives, 2026-07-16: configured pricing, never a
# hardcoded universal rate; official source only; NOT the verified account cost until the
# plan and cadence are confirmed) ────────────────────────────────────────────────────────
def test_billing_profile_is_the_pricing_source():
    import cb_costs
    prof = cb_costs.load_billing_profile("elevenlabs")
    assert prof["pricingSource"] == "https://elevenlabs.io/pricing"   # official page ONLY
    # Julian confirmed his real ElevenLabs plan (Pro, monthly) 2026-07-18 — both flip to
    # True in billing_profile.json; the fallback-profile-missing path (tested separately,
    # test_billing_falls_back_to_rates_when_profile_missing) is the only place these still
    # read False.
    assert prof["planConfirmed"] is True and prof["cadenceConfirmed"] is True
    assert prof["cyclePriceUsdExTax"] / prof["creditsPerCycle"] * 1000 == 0.165
    # the RATES entry is explicitly a fallback, never labelled verified
    rate, unit, conf = cb_costs.RATES["elevenlabs_dialogue_v3_per_1k_chars"]
    assert rate == 0.165 and "unconfirmed" in conf and "verified" not in conf


def test_billing_record_carries_every_required_field():
    """Julian's ledger contract: provider+model, characters, credits, plan+cadence,
    pricing-table version+effective date, estimated allocated cost ex tax, and
    generation-vs-regeneration credit consumption."""
    import cb_costs
    rec = cb_costs.dialogue_billing([{"text": "Nailed it.", "voice_id": "v"}],
                                     generation_kind="regeneration")
    assert rec["provider"] == "elevenlabs" and rec["model"] == "eleven_v3"
    assert rec["charactersSubmitted"] == 10 and rec["creditsConsumed"] == 10
    assert rec["billingPlan"] == "pro" and rec["billingCadence"] == "monthly"
    # Julian confirmed his real ElevenLabs plan (Pro, monthly) 2026-07-18 — real profile now
    # reads True for both.
    assert rec["planConfirmed"] is True and rec["cadenceConfirmed"] is True
    # the record must carry the CURRENT profile version (never a frozen literal — the
    # version bumps on every confirmed data change, e.g. Julian's 2026-07-16 fal ruling)
    assert rec["pricingTableVersion"] == cb_costs.load_billing_profile()["_version"]
    assert rec["pricingEffectiveDate"] == "2026-07-16"
    assert abs(rec["estimatedCostUsdExTax"] - 99.0 / 600000 * 10) < 1e-6
    assert "UNCONFIRMED" not in rec["costBasis"] and rec["costBasis"].endswith("CONFIRMED")
    assert "ex tax" in rec["costBasis"]
    assert rec["generationKind"] == "regeneration" and rec["creditsWereConsumed"] is True


def test_billing_falls_back_to_rates_when_profile_missing(monkeypatch):
    import cb_costs
    monkeypatch.setattr(cb_costs, "load_billing_profile", lambda provider=None: None)
    rec = cb_costs.dialogue_billing([{"text": "x" * 20, "voice_id": "v"}])
    assert rec["pricingSource"].startswith("RATES fallback")
    assert abs(rec["estimatedCostUsdExTax"] - 0.165 * 20 / 1000) < 1e-9


def test_estimate_dialogue_cost_math():
    import cb_costs
    turns = [{"text": "Nailed it.", "voice_id": "v1"},          # 10 chars
             {"text": "Fuzzby… why?", "voice_id": "v2"}]        # 12 chars
    expected = 0.165 * (22 / 1000.0)
    assert abs(cb_costs.estimate_dialogue_cost(turns) - expected) < 1e-9
    assert cb_costs.estimate_dialogue_cost([]) == 0.0


def test_dialogue_cost_reaches_the_ledger_correctly(monkeypatch, tmp_path):
    """END-TO-END proof: a real eleven_dialogue call (network mocked) produces a ledger
    entry whose cost is EXACTLY the verified rate x the billed characters, and a sidecar
    recording the same character count — the ledger and spending control agree."""
    import cb_gen, cb_costs
    logged = {}
    class FakeResp:
        content = b"MP3"
        def raise_for_status(self):
            return None
    monkeypatch.setattr(cb_gen, "_rpost", lambda *a, **k: FakeResp())
    monkeypatch.setattr(cb_gen, "MEDIA", tmp_path)
    monkeypatch.setattr(cb_gen.cb_costs, "log_spend",
                         lambda op, cost, out=None, meta=None: logged.update(
                             op=op, cost=cost, out=out, meta=meta))
    turns = [{"text": "Bizzy-bizzy-bizzy!", "voice_id": "v1"}]   # 18 chars
    cb_gen.eleven_dialogue(turns, out="proof_vo.mp3", production_route="cb_render")
    assert logged["op"] == "elevenlabs_dialogue"
    assert abs(logged["cost"] - 99.0 / 600000 * 18) < 1e-9
    m = logged["meta"]
    for field in ("provider", "model", "charactersSubmitted", "creditsConsumed",
                   "billingPlan", "billingCadence", "pricingTableVersion",
                   "pricingEffectiveDate", "estimatedCostUsdExTax", "generationKind",
                   "creditsWereConsumed"):
        assert field in m, f"ledger meta missing {field}"
    assert m["charactersSubmitted"] == 18 and m["generationKind"] == "generation"
    import json
    side = json.load(open(tmp_path / "proof_vo.mp3.gen.json"))
    assert side["chars"] == 18 and side["billing"]["creditsConsumed"] == 18


def test_as_fal_url_passes_through_an_already_uploaded_url_without_reupload(monkeypatch):
    """REGRESSION 2026-07-19: the ONLY real production caller of generate_video_seedance_ref
    (cb_render.fire_shot) uploads every reference ONCE per invocation and reuses the resulting
    fal URLs across all N candidates in a batch — it never passes local paths into this
    function. But generate_video_seedance_ref's own body used to unconditionally wrap every
    image/audio/video item in str(pathlib.Path(p)) before re-uploading it via _fal_upload —
    pathlib collapses the double slash in "https://host/..." (which isn't at the very start of
    the string) down to a single slash, and fal_client.upload_file then tried to open() that
    corrupted string as a local file, raising a 100%-reproducible FileNotFoundError on every
    single real render. _as_fal_url is the fix: an already-uploaded http(s) URL passes straight
    through with zero re-upload; a genuine local path still uploads exactly as before."""
    import cb_gen
    calls = []
    monkeypatch.setattr(cb_gen, "_fal_upload", lambda p: calls.append(p) or f"https://uploaded/{p}")
    url = "https://v3b.fal.media/files/b/0aa2d918/keyframe_candidate.png"
    assert cb_gen._as_fal_url(url) == url          # unchanged — no re-upload attempted
    assert calls == []                              # _fal_upload never called for an existing URL
    local = "/tmp/keyframe_candidate.png"
    result = cb_gen._as_fal_url(local)
    assert calls == [local]                         # a real local path still uploads
    assert result == f"https://uploaded/{local}"


def test_generate_video_seedance_ref_never_reuploads_preuploaded_reference_urls(monkeypatch, tmp_path):
    """End-to-end proof at the real call site: feeding generate_video_seedance_ref the SAME
    shape of already-uploaded image_urls/audio_urls cb_render.fire_shot passes in production
    must reach fal's subscribe call byte-identical, with zero re-upload calls at all.

    REGRESSION 2026-07-20: this test mocked _fal_upload/_fal_subscribe/_rget (the real network
    boundary) but NOT cb_costs.log_spend/write_gen_sidecar — both of which live INSIDE the real,
    unmocked generate_video_seedance_ref body and fire unconditionally on any "successful"
    return. Every run of this test was appending a real, phantom $4.551 seedance_ref2vid entry
    (out="proof.mp4") to the REAL, production cost_ledger.jsonl at repo root — no real money was
    spent (the provider call was fully faked), but the financial RECORD was silently corrupted
    every single test run, contradicting this whole suite's own "zero-spend proof" name. Found
    live: 5 such phantom entries already sitting in the real ledger. Fixed by mocking cb_costs
    too, with an explicit call-count assertion so this exact regression can never land silently
    again."""
    import cb_gen
    # This test proves the FAL-specific pre-upload-reuse behaviour of _generate_video_seedance_ref_fal
    # (via _as_fal_url) — pin VIDEO_PROVIDER="fal" explicitly so it keeps exercising that path
    # regardless of which provider CB_VIDEO_PROVIDER defaults to (byteplus, since 2026-07-22).
    monkeypatch.setattr(cb_gen, "VIDEO_PROVIDER", "fal")
    upload_calls = []
    monkeypatch.setattr(cb_gen, "_fal_upload", lambda p: upload_calls.append(p) or f"SHOULD_NOT_HAPPEN:{p}")
    subscribe_args = {}
    def fake_subscribe(endpoint, arguments=None, with_logs=False):
        subscribe_args.update(arguments)
        return {"video": {"url": "https://fake/out.mp4"}}
    monkeypatch.setattr(cb_gen, "_fal_subscribe", fake_subscribe)
    class FakeResp:
        content = b"MP4"
        def raise_for_status(self):
            return None
    monkeypatch.setattr(cb_gen, "_rget", lambda *a, **k: FakeResp())
    monkeypatch.setattr(cb_gen, "MEDIA", tmp_path)
    monkeypatch.setattr(cb_gen, "FAL_KEY", "fake-key")
    spend_calls = []
    sidecar_calls = []
    monkeypatch.setattr(cb_gen.cb_costs, "log_spend",
                         lambda *a, **k: spend_calls.append((a, k)))
    monkeypatch.setattr(cb_gen.cb_costs, "write_gen_sidecar",
                         lambda *a, **k: sidecar_calls.append((a, k)))
    pre_uploaded_images = ["https://v3b.fal.media/files/a/keyframe.png",
                           "https://v3b.fal.media/files/b/zenny.png"]
    pre_uploaded_audio = ["https://v3b.fal.media/files/c/vo.mp3"]
    cb_gen.generate_video_seedance_ref("a raw seedance prompt", pre_uploaded_images,
                                       audio_urls=pre_uploaded_audio, out="proof.mp4",
                                       raw_prompt=True, production_route="cb_render")
    assert upload_calls == []                                   # NOT re-uploaded, at all
    # the real ledger/sidecar functions are mocked, not skipped — the call still happens
    # exactly once (proving the function's own accounting logic still runs), but it can never
    # again reach the real cost_ledger.jsonl or write a real .gen.json sidecar from this test.
    assert len(spend_calls) == 1
    assert len(sidecar_calls) == 1
    assert subscribe_args["image_urls"] == pre_uploaded_images   # passed through byte-identical
    assert subscribe_args["audio_urls"] == pre_uploaded_audio


# ── THE BYTEPLUS MODELARK IMAGE-PROVIDER SWITCH (2026-07-22, Julian: "we have to now use byte
# plus for both the image seedream 5 pro and seedance 2") — Seedream 5 Pro's HOST switches from
# fal.ai to BytePlus's own Ark API; IMAGE_PROVIDER itself still picks the MODEL FAMILY (seedream vs
# nanobanana), unchanged. Zero real network calls anywhere below. ──────────────────────────────────

def test_seedream_host_default_is_byteplus():
    import cb_gen
    assert cb_gen.SEEDREAM_HOST == "byteplus"


def test_generate_image_seedream_dispatch_default_routes_to_byteplus(monkeypatch):
    import cb_gen
    monkeypatch.setattr(cb_gen, "SEEDREAM_HOST", "byteplus")
    calls = []
    monkeypatch.setattr(cb_gen, "_generate_image_seedream_byteplus",
                         lambda *a, **k: calls.append(("byteplus", a, k)) or "BP_OUT")
    monkeypatch.setattr(cb_gen, "_generate_image_seedream_fal",
                         lambda *a, **k: calls.append(("fal", a, k)) or "FAL_OUT")
    r = cb_gen._generate_image_seedream("p", ["r.png"], "16:9", "o.png", "2K")
    assert r == "BP_OUT"
    assert calls and calls[-1][0] == "byteplus"


def test_generate_image_seedream_dispatch_fal_rollback(monkeypatch):
    import cb_gen
    monkeypatch.setattr(cb_gen, "SEEDREAM_HOST", "fal")
    calls = []
    monkeypatch.setattr(cb_gen, "_generate_image_seedream_byteplus",
                         lambda *a, **k: calls.append(("byteplus", a, k)) or "BP_OUT")
    monkeypatch.setattr(cb_gen, "_generate_image_seedream_fal",
                         lambda *a, **k: calls.append(("fal", a, k)) or "FAL_OUT")
    r = cb_gen._generate_image_seedream("p", ["r.png"], "16:9", "o.png", "2K")
    assert r == "FAL_OUT"
    assert calls and calls[-1][0] == "fal"


def test_generate_image_top_level_dispatch_still_reaches_byteplus_by_default(monkeypatch):
    """End-to-end at the PUBLIC entry point every cb_scene.py call site actually uses
    (generate_image), proving the two-layer dispatch (family, then host) both resolve to
    byteplus with zero explicit configuration — the real default a fresh checkout gets."""
    import cb_gen
    monkeypatch.setattr(cb_gen, "IMAGE_PROVIDER", "seedream")
    monkeypatch.setattr(cb_gen, "SEEDREAM_HOST", "byteplus")
    calls = []
    monkeypatch.setattr(cb_gen, "_generate_image_seedream_byteplus",
                         lambda *a, **k: calls.append(1) or "OUT")
    r = cb_gen.generate_image("p", ["r.png"], "16:9", "o.png", production_route="cb_render")
    assert r == "OUT" and calls == [1]


def test_byteplus_seedream_size_computes_exact_pixels_for_known_tiers_and_aspects():
    import cb_gen
    assert cb_gen._byteplus_seedream_size("2K", "16:9") == "2048x1152"
    assert cb_gen._byteplus_seedream_size("2K", "9:16") == "1152x2048"
    assert cb_gen._byteplus_seedream_size("2K", "1:1") == "2048x2048"
    assert cb_gen._byteplus_seedream_size("1K", "16:9") == "1024x576"
    assert cb_gen._byteplus_seedream_size("4K", "16:9") == "4096x2304"
    # unrecognized aspect or tier -> falls back to the bare tier string, never a guessed shape
    assert cb_gen._byteplus_seedream_size("2K", "2.35:1") == "2K"
    assert cb_gen._byteplus_seedream_size("weird", "16:9") == "weird"


def test_generate_image_seedream_byteplus_end_to_end(monkeypatch, tmp_path):
    """Proves the real BytePlus image code path at zero cost/zero network: the POST body
    carries the correct model/prompt/size/watermark fields and the reference-image array
    (Julian's own curl example's "image" field shape for Seedream), the response's
    data[0].url is downloaded correctly, already-uploaded URLs are never re-uploaded (the
    same _fal_upload-as-utility discipline as the video path), and the ledger/sidecar are
    both written with provider='byteplus'."""
    import cb_gen
    monkeypatch.setattr(cb_gen, "BYTEPLUS_ARK_KEY", "fake-ark-key")
    monkeypatch.setattr(cb_gen, "MEDIA", tmp_path)

    upload_calls = []
    ref = tmp_path / "ref1.png"; ref.write_bytes(b"REF")
    monkeypatch.setattr(cb_gen, "_fal_upload",
                         lambda p: upload_calls.append(p) or f"https://uploaded/{pathlib_name(p)}")

    post_calls = []
    class FakeResp:
        def json(self):
            return {"data": [{"url": "https://fake/keyframe.png"}]}
    def fake_rpost(url, **kw):
        post_calls.append((url, kw))
        assert url == cb_gen.BYTEPLUS_ARK_IMAGES_URL
        assert kw["headers"]["Authorization"] == "Bearer fake-ark-key"
        return FakeResp()
    monkeypatch.setattr(cb_gen, "_rpost", fake_rpost)

    class FakeImgResp:
        content = b"PNG"
        def raise_for_status(self): return None
    monkeypatch.setattr(cb_gen, "_rget", lambda url, **kw: FakeImgResp())

    spend_calls = []
    sidecar_calls = []
    monkeypatch.setattr(cb_gen.cb_costs, "log_spend", lambda *a, **k: spend_calls.append((a, k)))
    monkeypatch.setattr(cb_gen.cb_costs, "write_gen_sidecar", lambda *a, **k: sidecar_calls.append((a, k)))

    out = cb_gen._generate_image_seedream_byteplus("a raw keyframe prompt", [str(ref)],
                                                     aspect="16:9", out="bp_keyframe.png", image_size="2K")

    assert out == str(tmp_path / "bp_keyframe.png")
    assert (tmp_path / "bp_keyframe.png").read_bytes() == b"PNG"
    assert len(upload_calls) == 1   # local ref file uploaded exactly once

    body = post_calls[0][1]["json"]
    assert body["model"] == cb_gen.BYTEPLUS_SEEDREAM_MODEL
    assert body["prompt"] == "a raw keyframe prompt"
    assert body["size"] == "2048x1152"
    assert body["watermark"] is False
    assert body["image"] == [f"https://uploaded/{ref.name}"]

    assert len(spend_calls) == 1 and len(sidecar_calls) == 1
    assert spend_calls[0][1]["meta"]["provider"] == "byteplus"
    assert sidecar_calls[0][1]["provider"] == "byteplus"


def test_generate_image_seedream_byteplus_no_references_omits_image_field(monkeypatch, tmp_path):
    import cb_gen
    monkeypatch.setattr(cb_gen, "BYTEPLUS_ARK_KEY", "fake-ark-key")
    monkeypatch.setattr(cb_gen, "MEDIA", tmp_path)
    post_calls = []
    class FakeResp:
        def json(self): return {"data": [{"url": "https://fake/x.png"}]}
    monkeypatch.setattr(cb_gen, "_rpost", lambda url, **kw: post_calls.append((url, kw)) or FakeResp())
    class FakeImgResp:
        content = b"PNG"
        def raise_for_status(self): return None
    monkeypatch.setattr(cb_gen, "_rget", lambda url, **kw: FakeImgResp())
    monkeypatch.setattr(cb_gen.cb_costs, "log_spend", lambda *a, **k: None)
    monkeypatch.setattr(cb_gen.cb_costs, "write_gen_sidecar", lambda *a, **k: None)
    cb_gen._generate_image_seedream_byteplus("p", None, out="t2i.png")
    assert "image" not in post_calls[0][1]["json"]


def test_generate_image_seedream_byteplus_raises_loud_on_no_url(monkeypatch, tmp_path):
    import cb_gen
    monkeypatch.setattr(cb_gen, "BYTEPLUS_ARK_KEY", "fake-ark-key")
    monkeypatch.setattr(cb_gen, "MEDIA", tmp_path)
    class FakeResp:
        def json(self): return {"data": []}
    monkeypatch.setattr(cb_gen, "_rpost", lambda url, **kw: FakeResp())
    try:
        cb_gen._generate_image_seedream_byteplus("p", None, out="fail.png")
        assert False, "expected SystemExit on a missing image url"
    except SystemExit:
        pass


def pathlib_name(p):
    import pathlib
    return pathlib.Path(p).name


# ── THE BYTEPLUS MODELARK VIDEO-PROVIDER SWITCH (2026-07-22, Julian: "i want to go via byteplus
# model ark") — zero-cost tests for the routing logic AND the real request/response shape, matching
# the discipline test_cb_gen.py already established for CB_IMAGE_PROVIDER above. No real network
# calls anywhere in this section — every provider boundary (_rpost/_rget/time.sleep) is mocked. ──────

def test_video_provider_default_is_byteplus():
    import cb_gen
    assert cb_gen.VIDEO_PROVIDER == "byteplus"


def test_video_provider_dispatch_default_routes_to_byteplus(monkeypatch):
    import cb_gen
    monkeypatch.setattr(cb_gen, "VIDEO_PROVIDER", "byteplus")
    calls = []
    monkeypatch.setattr(cb_gen, "_generate_video_seedance_ref_byteplus",
                         lambda *a, **k: calls.append(("byteplus", a, k)) or "BYTEPLUS_OUT")
    monkeypatch.setattr(cb_gen, "_generate_video_seedance_ref_fal",
                         lambda *a, **k: calls.append(("fal", a, k)) or "FAL_OUT")
    r = cb_gen.generate_video_seedance_ref("p", ["img.png"], out="o.mp4", production_route="cb_render")
    assert r == "BYTEPLUS_OUT"
    assert calls and calls[-1][0] == "byteplus"


def test_video_provider_fal_rollback_routes_to_fal(monkeypatch):
    import cb_gen
    monkeypatch.setattr(cb_gen, "VIDEO_PROVIDER", "fal")
    calls = []
    monkeypatch.setattr(cb_gen, "_generate_video_seedance_ref_byteplus",
                         lambda *a, **k: calls.append(("byteplus", a, k)) or "BYTEPLUS_OUT")
    monkeypatch.setattr(cb_gen, "_generate_video_seedance_ref_fal",
                         lambda *a, **k: calls.append(("fal", a, k)) or "FAL_OUT")
    r = cb_gen.generate_video_seedance_ref("p", ["img.png"], out="o.mp4", production_route="cb_render")
    assert r == "FAL_OUT"
    assert calls and calls[-1][0] == "fal"


def test_video_provider_dispatch_still_requires_production_route(monkeypatch):
    """The dispatcher must still call _require_production_route BEFORE picking a provider —
    a legacy caller with no production_route must be blocked regardless of VIDEO_PROVIDER."""
    import cb_gen
    calls = []
    monkeypatch.setattr(cb_gen, "_generate_video_seedance_ref_byteplus", lambda *a, **k: calls.append(1))
    monkeypatch.setattr(cb_gen, "_generate_video_seedance_ref_fal", lambda *a, **k: calls.append(1))
    try:
        cb_gen.generate_video_seedance_ref("p", ["img.png"], out="o.mp4")  # no production_route
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass
    assert calls == []   # neither provider implementation was ever reached


def test_byteplus_task_id_extraction_tries_multiple_keys():
    import cb_gen
    assert cb_gen._byteplus_task_id({"id": "abc"}) == "abc"
    assert cb_gen._byteplus_task_id({"task_id": "abc"}) == "abc"
    assert cb_gen._byteplus_task_id({"taskId": "abc"}) == "abc"
    assert cb_gen._byteplus_task_id({"request_id": "abc"}) == "abc"
    try:
        cb_gen._byteplus_task_id({"nothing_recognizable": "abc"})
        assert False, "expected SystemExit on an unrecognized response shape"
    except SystemExit:
        pass


def test_generate_video_seedance_ref_byteplus_end_to_end(monkeypatch, tmp_path):
    """Proves the real BytePlus code path at zero cost/zero network: the create-task POST carries
    the correct content array (text + role-tagged image_url/audio_url items) and top-level fields
    (model, ratio, resolution, duration, generate_audio, watermark) matching Julian's own worked
    curl example exactly; the poll loop reads status/content.video_url correctly; already-uploaded
    reference URLs are never re-uploaded (same _as_fal_url discipline as the fal path); and the
    cost ledger + .gen.json sidecar are both written with provider='byteplus'."""
    import cb_gen
    monkeypatch.setattr(cb_gen, "BYTEPLUS_ARK_KEY", "fake-ark-key")
    monkeypatch.setattr(cb_gen, "MEDIA", tmp_path)
    monkeypatch.setattr(cb_gen.time, "sleep", lambda s: None)   # skip the real poll delay

    upload_calls = []
    monkeypatch.setattr(cb_gen, "_fal_upload", lambda p: upload_calls.append(p) or f"SHOULD_NOT_HAPPEN:{p}")

    post_calls = []
    class FakeCreateResp:
        def json(self):
            return {"id": "task-123"}
    def fake_rpost(url, **kw):
        post_calls.append((url, kw))
        assert url == cb_gen.BYTEPLUS_ARK_TASKS_URL
        assert kw["headers"]["Authorization"] == "Bearer fake-ark-key"
        return FakeCreateResp()
    monkeypatch.setattr(cb_gen, "_rpost", fake_rpost)

    get_calls = []
    class FakePollResp:
        def json(self):
            return {"status": "succeeded", "content": {"video_url": "https://fake/byteplus_out.mp4"}}
    def fake_rget(url, **kw):
        get_calls.append((url, kw))
        if url == "https://fake/byteplus_out.mp4":
            class FakeVid:
                content = b"MP4"
                def raise_for_status(self): return None
            return FakeVid()
        assert url == f"{cb_gen.BYTEPLUS_ARK_TASKS_URL}/task-123"
        return FakePollResp()
    monkeypatch.setattr(cb_gen, "_rget", fake_rget)

    spend_calls = []
    sidecar_calls = []
    monkeypatch.setattr(cb_gen.cb_costs, "log_spend", lambda *a, **k: spend_calls.append((a, k)))
    monkeypatch.setattr(cb_gen.cb_costs, "write_gen_sidecar", lambda *a, **k: sidecar_calls.append((a, k)))

    pre_uploaded_images = ["https://v3b.fal.media/files/a/keyframe.png"]
    pre_uploaded_audio = ["https://v3b.fal.media/files/c/vo.mp3"]
    out = cb_gen._generate_video_seedance_ref_byteplus(
        "a raw seedance prompt", pre_uploaded_images, audio_urls=pre_uploaded_audio,
        resolution="720p", duration="15", out="byteplus_proof.mp4", raw_prompt=True)

    assert upload_calls == []   # already-public URLs never re-uploaded
    assert out == str(tmp_path / "byteplus_proof.mp4")
    assert (tmp_path / "byteplus_proof.mp4").read_bytes() == b"MP4"

    # the create-task POST body matches Julian's own curl example's shape exactly
    body = post_calls[0][1]["json"]
    assert body["model"] == "dreamina-seedance-2-0-260128"
    assert body["generate_audio"] is True
    assert body["ratio"] == "16:9"
    assert body["resolution"] == "720p"
    assert body["duration"] == 15
    assert body["watermark"] is False
    content = body["content"]
    assert content[0] == {"type": "text", "text": "a raw seedance prompt"}
    img_items = [c for c in content if c["type"] == "image_url"]
    assert img_items == [{"type": "image_url", "image_url": {"url": pre_uploaded_images[0]},
                           "role": "reference_image"}]
    audio_items = [c for c in content if c["type"] == "audio_url"]
    assert audio_items == [{"type": "audio_url", "audio_url": {"url": pre_uploaded_audio[0]},
                             "role": "reference_audio"}]

    assert len(spend_calls) == 1 and len(sidecar_calls) == 1
    assert spend_calls[0][0][0] == "seedance_ref2vid"
    assert spend_calls[0][1]["meta"]["provider"] == "byteplus"
    assert sidecar_calls[0][1]["provider"] == "byteplus"


def test_generate_video_seedance_ref_byteplus_fast_tier_uses_fast_model(monkeypatch, tmp_path):
    import cb_gen
    monkeypatch.setattr(cb_gen, "BYTEPLUS_ARK_KEY", "fake-ark-key")
    monkeypatch.setattr(cb_gen, "MEDIA", tmp_path)
    monkeypatch.setattr(cb_gen.time, "sleep", lambda s: None)
    post_calls = []
    class FakeCreateResp:
        def json(self): return {"id": "task-456"}
    monkeypatch.setattr(cb_gen, "_rpost", lambda url, **kw: post_calls.append((url, kw)) or FakeCreateResp())
    class FakePollResp:
        def json(self): return {"status": "succeeded", "content": {"video_url": "https://fake/f.mp4"}}
    class FakeVid:
        content = b"MP4"
        def raise_for_status(self): return None
    monkeypatch.setattr(cb_gen, "_rget", lambda url, **kw: FakeVid() if url.endswith("f.mp4") else FakePollResp())
    monkeypatch.setattr(cb_gen.cb_costs, "log_spend", lambda *a, **k: None)
    monkeypatch.setattr(cb_gen.cb_costs, "write_gen_sidecar", lambda *a, **k: None)
    cb_gen._generate_video_seedance_ref_byteplus("p", ["https://x/img.png"], out="fast.mp4",
                                                  fast=True, raw_prompt=True)
    assert post_calls[0][1]["json"]["model"] == "dreamina-seedance-2-0-fast-260128"


def test_generate_video_seedance_ref_byteplus_raises_on_failed_task(monkeypatch, tmp_path):
    import cb_gen
    monkeypatch.setattr(cb_gen, "BYTEPLUS_ARK_KEY", "fake-ark-key")
    monkeypatch.setattr(cb_gen, "MEDIA", tmp_path)
    monkeypatch.setattr(cb_gen.time, "sleep", lambda s: None)
    class FakeCreateResp:
        def json(self): return {"id": "task-789"}
    monkeypatch.setattr(cb_gen, "_rpost", lambda url, **kw: FakeCreateResp())
    class FakePollResp:
        def json(self): return {"status": "failed", "error": "content policy violation"}
    monkeypatch.setattr(cb_gen, "_rget", lambda url, **kw: FakePollResp())
    try:
        cb_gen._generate_video_seedance_ref_byteplus("p", ["https://x/img.png"], out="fail.mp4",
                                                      raw_prompt=True)
        assert False, "expected SystemExit on a failed task"
    except SystemExit as e:
        assert "failed" in str(e)
