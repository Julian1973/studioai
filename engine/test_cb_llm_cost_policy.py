import json
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

import cb_llm


class TinyDirection(BaseModel):
    answer: str


def _log(*_args, **_kwargs):
    pass


def _response(answer="ready", input_tokens=1000, cached_tokens=0, output_tokens=200):
    usage = SimpleNamespace(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        input_tokens_details=SimpleNamespace(cached_tokens=cached_tokens),
    )
    return SimpleNamespace(output_parsed=TinyDirection(answer=answer), usage=usage, status="completed")


def test_standard_is_default_and_premium_requires_explicit_tier(monkeypatch, tmp_path):
    calls = []

    def fake(model, system, user, schema, images=None, **kwargs):
        calls.append((model, kwargs["max_output_tokens"], kwargs["reasoning_effort"]))
        response = _response()
        return response.output_parsed, response

    monkeypatch.setattr(cb_llm, "_openai_call", fake)
    monkeypatch.setattr(cb_llm, "_log_openai_usage", lambda *_args: 0.0)
    monkeypatch.setattr(cb_llm, "OPENAI_CACHE_DIR", tmp_path)
    monkeypatch.setattr(cb_llm, "OPENAI_RESPONSE_CACHE", False)
    monkeypatch.setattr(cb_llm, "OPENAI_DAILY_BUDGET_USD", 100.0)
    monkeypatch.setattr(cb_llm, "OPENAI_MAX_CALL_USD", 100.0)

    cb_llm.structured("system", "shot", TinyDirection, reuse=False, log=_log)
    cb_llm.structured("system", "story", TinyDirection, tier="premium", reuse=False, log=_log)

    assert calls == [
        (cb_llm.VALIDATOR_MODEL, cb_llm.STANDARD_MAX_OUTPUT_TOKENS, "low"),
        (cb_llm.DIRECTOR_MODEL, cb_llm.PREMIUM_MAX_OUTPUT_TOKENS, "medium"),
    ]


def test_identical_standard_direction_is_reused_without_second_call(monkeypatch, tmp_path):
    calls = []

    def fake(*_args, **_kwargs):
        calls.append(True)
        response = _response()
        return response.output_parsed, response

    monkeypatch.setattr(cb_llm, "_openai_call", fake)
    monkeypatch.setattr(cb_llm, "_log_openai_usage", lambda *_args: 0.001)
    monkeypatch.setattr(cb_llm, "OPENAI_CACHE_DIR", tmp_path)
    monkeypatch.setattr(cb_llm, "OPENAI_RESPONSE_CACHE", True)
    monkeypatch.setattr(cb_llm, "OPENAI_DAILY_BUDGET_USD", 100.0)
    monkeypatch.setattr(cb_llm, "OPENAI_MAX_CALL_USD", 100.0)

    first = cb_llm.structured("same system", "same input", TinyDirection, log=_log)
    second = cb_llm.structured("same system", "same input", TinyDirection, log=_log)

    assert first == second
    assert len(calls) == 1


def test_cost_guard_refuses_before_provider_call(monkeypatch, tmp_path):
    called = False

    def fake(*_args, **_kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(cb_llm, "_openai_call", fake)
    monkeypatch.setattr(cb_llm, "OPENAI_CACHE_DIR", tmp_path)
    monkeypatch.setattr(cb_llm, "OPENAI_RESPONSE_CACHE", False)
    monkeypatch.setattr(cb_llm, "OPENAI_MAX_CALL_USD", 0.00001)

    with pytest.raises(SystemExit, match="OPENAI COST GUARD"):
        cb_llm.structured("system", "input", TinyDirection, reuse=False, log=_log)
    assert called is False


def test_exhausted_credit_is_not_retried(monkeypatch, tmp_path):
    calls = []

    def fake(*_args, **_kwargs):
        calls.append(True)
        raise RuntimeError("429 insufficient_quota: credit_balance_exhausted")

    monkeypatch.setattr(cb_llm, "_openai_call", fake)
    monkeypatch.setattr(cb_llm, "PROVIDER_ATTEMPTS", 3)
    monkeypatch.setattr(cb_llm, "ENABLE_GEMINI_FALLBACK", False)
    monkeypatch.setattr(cb_llm, "OPENAI_CACHE_DIR", tmp_path)
    monkeypatch.setattr(cb_llm, "OPENAI_RESPONSE_CACHE", False)
    monkeypatch.setattr(cb_llm, "OPENAI_DAILY_BUDGET_USD", 100.0)
    monkeypatch.setattr(cb_llm, "OPENAI_MAX_CALL_USD", 100.0)

    with pytest.raises(SystemExit, match="insufficient_quota"):
        cb_llm.structured("system", "input", TinyDirection, reuse=False, log=_log)
    assert len(calls) == 1


def test_actual_token_cost_is_logged_with_cached_input_discount(monkeypatch, tmp_path):
    ledger = tmp_path / "cost-ledger.jsonl"
    monkeypatch.setattr(cb_llm.cb_costs, "LEDGER_PATH", str(ledger))
    response = _response(input_tokens=1000, cached_tokens=400, output_tokens=200)

    cost = cb_llm._log_openai_usage(response, "gpt-5.4-mini", "department_voice", 0.05)

    assert cost == pytest.approx(0.00138)
    row = json.loads(ledger.read_text().strip())
    assert row["op"] == "openai_text"
    assert row["cost_usd"] == pytest.approx(0.00138)
    assert row["meta"]["cachedInputTokens"] == 400


def test_openai_request_uses_low_reasoning_output_cap_and_prompt_cache(monkeypatch):
    captured = {}

    class Responses:
        def parse(self, **kwargs):
            captured.update(kwargs)
            return _response()

    monkeypatch.setattr(cb_llm, "_client_get", lambda: SimpleNamespace(responses=Responses()))
    obj, _ = cb_llm._openai_call(
        "gpt-5.4-mini", "system", "input", TinyDirection,
        max_output_tokens=3210, reasoning_effort="low")

    assert obj.answer == "ready"
    assert captured["max_output_tokens"] == 3210
    assert captured["reasoning"] == {"effort": "low"}
    assert captured["verbosity"] == "low"
    assert captured["prompt_cache_retention"] == "24h"
    assert captured["prompt_cache_key"].startswith("crystal-bears-")
