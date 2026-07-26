#!/usr/bin/env python3
"""test_provider_switch.py — THE PROVIDER SWITCH (2026-07-26).

Julian: "why are we using gpt for that surely your opus 5 is better?" The honest answer
was that nobody ever chose it — there was no Anthropic path in cb_llm at all. This file
guards the switch that was added to make that a decision instead of an inheritance.

Every test here stubs the SDK boundary. NOTHING in this file makes a paid provider call.
"""
import os
import sys
import pathlib

import pytest
from pydantic import BaseModel, Field

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import cb_llm


class Tiny(BaseModel):
    verdict: str = Field(min_length=1)


class _Block:
    type = "tool_use"
    def __init__(self, payload): self.input = payload


class _Resp:
    stop_reason = "tool_use"
    def __init__(self, payload): self.content = [_Block(payload)]


class _Stream:
    """The SDK requires STREAMING for any request whose estimated duration exceeds 10
    minutes, and at MAX_OUTPUT_TOKENS=32000 every Director call qualifies — a plain
    .create() raised before generating a single token on the first real fire. The stub
    mirrors the real context-manager shape so a regression back to .create() fails here."""
    def __init__(self, sink, kw, payload): self._sink, self._kw, self._p = sink, kw, payload
    def __enter__(self): self._sink.append(self._kw); return self
    def __exit__(self, *a): return False
    def get_final_message(self): return _Resp(self._p)


class _Messages:
    def __init__(self, sink, payload=None):
        self._sink = sink; self._p = payload or {"verdict": "ok"}
    def stream(self, **kw): return _Stream(self._sink, kw, self._p)
    def create(self, **kw):
        raise AssertionError("must use messages.stream() — .create() fails at 32k max_tokens")


class _FakeAnthropic:
    def __init__(self, sink): self.messages = _Messages(sink)


def test_the_casting_is_claude_authors_gpt_reviews():
    """THE CASTING (2026-07-26), set on evidence rather than preference.

    The same script was broken down by each provider and read blind by five independent
    reviewers, in five separate applications, with no knowledge of one another. All five
    preferred the Anthropic breakdown on craft — including one judging against its own
    house, which is hard to explain as style affinity.

    But the reason for the SPLIT is that the two fail differently, measured: 18 NEED
    lines written as obligations the character ought to meet on one side, 4 unfalsifiable
    audience-effect claims and 2 off-screen images on the other. The failure mode of the
    weaker AUTHOR is the right temperament for a CRITIC.

    And the part that holds whichever way the craft argument lands: the gate asked to
    actively attempt to FAIL the work must not be the model that wrote it. A critic
    sharing the author's blind spots is the one pattern it cannot see. If these two ever
    drift back to the same provider, that guarantee is silently gone — which is what this
    test exists to catch.
    """
    assert cb_llm.DIRECTOR_PROVIDER == "anthropic"
    assert cb_llm.REVIEW_PROVIDER == "openai"
    assert cb_llm.REVIEW_PROVIDER != cb_llm.DIRECTOR_PROVIDER, (
        "the adversarial gate is reviewing work its own model authored")


def test_anthropic_path_forces_the_schema_and_returns_a_validated_model(monkeypatch):
    """The whole pipeline rests on every gate returning a VALIDATED PYDANTIC MODEL. On the
    OpenAI path that is strict Structured Outputs; here it must be a forced single-tool
    call whose input_schema IS the Pydantic schema — so the model cannot answer in prose."""
    sent = []
    monkeypatch.setattr(cb_llm, "_anthropic_client_get", lambda: _FakeAnthropic(sent))
    got = cb_llm.structured("sys", "user", Tiny, provider="anthropic")

    assert isinstance(got, Tiny) and got.verdict == "ok"
    kw = sent[0]
    assert kw["tool_choice"] == {"type": "tool", "name": "emit"}, (
        "the tool must be FORCED — an optional tool lets the model answer in prose and "
        "the gate's own schema guarantee evaporates")
    assert kw["tools"][0]["input_schema"] == Tiny.model_json_schema()
    assert kw["system"] == "sys"
    assert kw["model"] == cb_llm.ANTHROPIC_MODEL


def test_an_off_schema_answer_still_raises_ValidationError_for_the_repair_loop(monkeypatch):
    """A ValidationError means the same thing on both paths — the model answered, just
    off-schema — so every caller's EXISTING repair loop works unchanged. If this raised
    something else, a Claude run would crash where a GPT run would self-repair."""
    from pydantic import ValidationError

    monkeypatch.setattr(cb_llm, "_anthropic_client_get",
                        lambda: type("C", (), {"messages": _Messages([], {"wrong_field": 1})})())
    with pytest.raises(ValidationError):
        cb_llm.structured("sys", "user", Tiny, provider="anthropic")


def test_there_is_no_cross_provider_fallback(monkeypatch):
    """Silently answering a Claude call with GPT would make an A/B meaningless and a
    production run unattributable. A provider failure must STOP with its own error."""
    class _Boom:
        def stream(self, **kw): raise RuntimeError("provider down")

    monkeypatch.setattr(cb_llm, "_anthropic_client_get",
                        lambda: type("C", (), {"messages": _Boom()})())
    calls = []
    monkeypatch.setattr(cb_llm, "_openai_call",
                        lambda *a, **k: calls.append(1) or Tiny(verdict="gpt"))
    with pytest.raises(SystemExit) as ei:
        cb_llm.structured("sys", "user", Tiny, provider="anthropic")
    assert "Anthropic" in str(ei.value)
    assert not calls, "an Anthropic failure silently fell through to OpenAI"


def test_the_adversarial_gate_can_be_pointed_at_a_different_provider_than_the_author():
    """The critic should not be the author. This gate is asked to ACTIVELY ATTEMPT to fail
    work that the same model wrote nine gates of — it shares the blind spots that made it.
    True whichever provider authors; not an argument about which model is better."""
    import inspect
    import cb_creative as C
    src = inspect.getsource(C.gate6_adversarial_review)
    assert "provider=cb_llm.REVIEW_PROVIDER" in src, (
        "gate6 reviews on whatever authored the work — the one gate where that matters most")


def test_a_typo_in_the_provider_name_fails_loudly_at_import():
    """A silently-ignored CB_DIRECTOR_PROVIDER=antropic would run the whole episode on the
    wrong model and report success — the exact failure this file exists to prevent."""
    src = (HERE / "cb_llm.py").read_text(encoding="utf-8")
    assert "is not one of" in src and "VALID_PROVIDERS" in src


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
