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

def _reset():
    cb_gen.IMAGE_PROVIDER = _orig_provider

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

print("=== cb_costs.estimate_image_cost() matches the two-provider switch exactly ===")
import cb_costs
check("default (seedream) returns the seedream rate", cb_costs.estimate_image_cost() == cb_costs.RATES["seedream5pro_image"][0])
check("provider='nanobanana2' returns the nanobanana rate", cb_costs.estimate_image_cost(provider="nanobanana2") == cb_costs.RATES["nanobanana2_image"][0])
check("the two rates are genuinely different (not a copy-paste no-op)", cb_costs.RATES["seedream5pro_image"][0] != cb_costs.RATES["nanobanana2_image"][0])

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
        def raise_for_status(self):
            return None
        def json(self):
            import base64
            return {
                "audio_base64": base64.b64encode(b"MP3").decode(),
                "voice_segments": [{
                    "voice_id": "v1", "dialogue_input_index": 0,
                    "start_time_seconds": 0.0, "end_time_seconds": 1.0,
                    "character_start_index": 0, "character_end_index": 18,
                }],
            }
    monkeypatch.setattr(cb_gen, "_rpost", lambda *a, **k: FakeResp())
    monkeypatch.setattr(cb_gen, "MEDIA", tmp_path)
    monkeypatch.setattr(cb_gen, "ELEVEN_KEY", "test-key")
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
    timing = json.load(open(tmp_path / "proof_vo.mp3.dialogue.json"))
    assert timing["inputCount"] == 1
    assert timing["voiceSegments"][0]["dialogueInputIndex"] == 0
