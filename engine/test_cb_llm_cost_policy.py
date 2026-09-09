import json
from types import SimpleNamespace
from typing import ClassVar

import pytest
from pydantic import BaseModel, ValidationError, model_validator

import cb_llm


class TinyDirection(BaseModel):
    answer: str


@pytest.fixture(autouse=True)
def isolated_cost_lock(monkeypatch, tmp_path):
    # Test provider fakes must not contend with a live Studio request's lock.
    monkeypatch.setattr(cb_llm, 'OPENAI_COST_LOCK_PATH', tmp_path / 'cost.lock')


def _log(*_args, **_kwargs):
    pass


def _response(answer="ready", input_tokens=1000, cached_tokens=0, output_tokens=200):
    usage = SimpleNamespace(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        input_tokens_details=SimpleNamespace(cached_tokens=cached_tokens),
    )
    return SimpleNamespace(output_parsed=TinyDirection(answer=answer), output_text=json.dumps({'answer': answer}), usage=usage, status="completed")


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
        def create(self, **kwargs):
            captured.update(kwargs)
            return _response()

    monkeypatch.setattr(cb_llm, "_client_get", lambda: SimpleNamespace(responses=Responses()))
    obj, _ = cb_llm._openai_call(
        "gpt-5.4-mini", "system", "input", TinyDirection,
        max_output_tokens=3210, reasoning_effort="low")

    assert obj.answer == "ready"
    assert captured["max_output_tokens"] == 3210
    assert captured["reasoning"] == {"effort": "low"}
    assert captured["text"]['verbosity'] == 'low'
    assert captured["text"]['format']['type'] == 'json_schema'
    assert captured["text"]['format']['strict'] is True
    assert captured["extra_body"]["prompt_cache_retention"] == "24h"
    assert captured["prompt_cache_key"].startswith("crystal-bears-")


def test_worker_receipt_binds_actual_runtime_context_output_and_cache_use():
    result=TinyDirection(answer='ready')
    fresh=cb_llm.direction_handoff_receipt('runtime skill','shot context',result,label='department_voice',model='test')
    reused=cb_llm.direction_handoff_receipt('runtime skill','shot context',result,label='department_voice',model='test',reused=True)
    changed=cb_llm.direction_handoff_receipt('changed runtime skill','shot context',result,label='department_voice',model='test')
    assert fresh['systemHash']!=changed['systemHash']
    assert fresh['outputHash']==reused['outputHash']
    assert not fresh['reused'] and reused['reused']
    assert 'shot context' not in json.dumps(fresh)


def test_paid_response_survives_local_validation_error_and_revalidates_without_spend(monkeypatch, tmp_path):
    class RepairableDirection(BaseModel):
        repaired: ClassVar[bool] = False
        answer: str

        @model_validator(mode='after')
        def enforce_local_contract(self):
            if not self.repaired:
                raise ValueError('local contract defect')
            return self

    calls, costs, finishes = [], [], []
    def create(**kwargs):
        calls.append(kwargs)
        return _response()
    monkeypatch.setattr(cb_llm, '_client_get', lambda: SimpleNamespace(responses=SimpleNamespace(create=create)))
    monkeypatch.setattr(cb_llm, '_log_openai_usage', lambda *a: costs.append(True) or .01)
    monkeypatch.setattr(cb_llm, '_assert_cost_budget', lambda *a: (.5, {}))
    monkeypatch.setattr(cb_llm, 'OPENAI_CACHE_DIR', tmp_path)
    monkeypatch.setattr(cb_llm, 'OPENAI_RESPONSE_CACHE', True)
    monkeypatch.setattr(cb_llm.episode_budget, 'episode_from_output', lambda: 'TestEp')
    monkeypatch.setattr(cb_llm.episode_budget, 'configured', lambda _: True)
    monkeypatch.setattr(cb_llm.episode_budget, 'reserve', lambda *a: 'reservation')
    monkeypatch.setattr(cb_llm.episode_budget, 'finish', lambda *a: finishes.append(a))
    with pytest.raises(ValidationError):
        cb_llm.structured('skill', 'shot', RepairableDirection, log=_log)
    receipts = list((tmp_path / 'failures').glob('*.json'))
    assert len(receipts) == 1 and not json.loads(receipts[0].read_text())['validated']
    assert finishes == [('TestEp', 'reservation', 'committed', .01)]
    RepairableDirection.repaired = True
    assert cb_llm.structured('skill', 'shot', RepairableDirection, log=_log).answer == 'ready'
    assert len(calls) == 1 and len(costs) == 1
    # Changed direction is a distinct request; an old response cannot leak across it.
    cb_llm.structured('skill', 'different shot', RepairableDirection, log=_log)
    assert len(calls) == 2


def test_incomplete_paid_response_is_recorded_but_not_retried(monkeypatch, tmp_path):
    calls = []
    def create(**kwargs):
        calls.append(kwargs)
        response = _response()
        response.status = 'incomplete'
        return response
    monkeypatch.setattr(cb_llm, '_client_get', lambda: SimpleNamespace(responses=SimpleNamespace(create=create)))
    monkeypatch.setattr(cb_llm, '_log_openai_usage', lambda *a: .01)
    monkeypatch.setattr(cb_llm, '_assert_cost_budget', lambda *a: (.5, {}))
    monkeypatch.setattr(cb_llm, 'OPENAI_CACHE_DIR', tmp_path)
    monkeypatch.setattr(cb_llm, 'OPENAI_RESPONSE_CACHE', True)
    monkeypatch.setattr(cb_llm, 'PROVIDER_ATTEMPTS', 3)
    monkeypatch.setattr(cb_llm.episode_budget, 'configured', lambda _: False)
    with pytest.raises(RuntimeError, match='No complete structured output'):
        cb_llm.structured('skill', 'shot', TinyDirection, log=_log)
    assert len(calls) == 1
    receipt = json.loads(next((tmp_path / 'failures').glob('*.json')).read_text())
    assert receipt['status'] == 'incomplete'
    assert cb_llm._cache_load(receipt['requestDigest'], TinyDirection) is None
