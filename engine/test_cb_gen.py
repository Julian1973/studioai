#!/usr/bin/env python3
"""Zero-cost tests for the production image route lock.

Every provider mutation is scoped through pytest's monkeypatch fixture. Running
provider checks at import time used to leak stubs into unrelated production tests.
"""
import json

import pytest

import cb_costs
import cb_gen


def test_default_image_route_is_seedream(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cb_gen, "_generate_image_seedream",
        lambda *args, **kwargs: calls.append((args, kwargs)) or "SEEDREAM_OUT")

    assert cb_gen.IMAGE_PROVIDER == "seedream"
    assert cb_gen.generate_image(
        "prompt", ["ref1.png"], "16:9", "out1.png",
        production_route="cb_render") == "SEEDREAM_OUT"
    assert len(calls) == 1


def test_explicit_image_model_override_is_refused(monkeypatch):
    calls = []
    monkeypatch.setattr(
        cb_gen, "_generate_image_seedream",
        lambda *args, **kwargs: calls.append((args, kwargs)) or "SEEDREAM_OUT")

    with pytest.raises(RuntimeError, match="model overrides"):
        cb_gen.generate_image(
            "prompt", ["ref2.png"], "16:9", "out2.png",
            model="gemini-3.1-flash-image", production_route="cb_render")
    assert calls == []


def test_image_provider_fallback_is_refused(monkeypatch):
    calls = []
    monkeypatch.setattr(cb_gen, "IMAGE_PROVIDER", "nanobanana")
    monkeypatch.setattr(
        cb_gen, "_generate_image_seedream",
        lambda *args, **kwargs: calls.append((args, kwargs)) or "SEEDREAM_OUT")

    with pytest.raises(RuntimeError, match="locked to Seedream 5 Pro"):
        cb_gen.generate_image(
            "prompt", ["ref3.png"], "16:9", "out3.png",
            production_route="cb_render")
    assert calls == []


def test_image_cost_discloses_provider_and_reference_difference():
    assert cb_costs.estimate_image_cost() == cb_costs.RATES["seedream5pro_image"][0]
    assert cb_costs.estimate_image_cost(num_refs=3) == 0.096
    assert cb_costs.RATES["seedream5pro_image"][0] != cb_costs.RATES["nanobanana2_image"][0]


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


def test_seedance_prompt_wrapper_does_not_auto_bake_music():
    prompt = cb_gen._seedance_json_prompt(
        "Fuzzby flies through the flower corridor.", duration=12, ref=True)
    obj = json.loads(prompt)
    assert obj["duration_seconds"] == 12
    assert "music" not in obj
    assert "No musical underscore in the render" in obj["audio"]
    assert "ENGLISH" in obj["audio"]


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
                "alignment": {
                    "characters": list("Bizzy-bizzy-bizzy!"),
                    "character_start_times_seconds": [0.0] * 18,
                    "character_end_times_seconds": [1.0] * 18,
                },
                "normalized_alignment": None,
            }
    monkeypatch.setattr(cb_gen, "_rpost", lambda *a, **k: FakeResp())
    monkeypatch.setattr(cb_gen, "MEDIA", tmp_path)
    monkeypatch.setattr(cb_gen, "ELEVEN_KEY", "sk_test_key")
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
    assert timing["alignment"]["characters"][:5] == list("Bizzy")
