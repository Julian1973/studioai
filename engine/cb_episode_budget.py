"""Episode allowance: atomic reservations before provider requests, never media approval."""
from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
import fcntl
import json
import os
import re
import tempfile
import time
import uuid
import functools
import inspect
import math

ROOT = Path(__file__).resolve().parent.parent
_quote = ContextVar("episode_provider_quote", default=None)


class BudgetRefused(RuntimeError):
    pass


def _path(episode):
    if not re.fullmatch(r"Ep[0-9]+", str(episode)):
        raise ValueError("A numbered episode is required")
    return Path(os.environ.get("CB_EPISODE_BUDGET_ROOT", ROOT / "cb-output/episode-budgets")) / (episode + ".json")


def _units(amount):
    value = Decimal(str(amount))
    if not value.is_finite() or value < 0:
        raise ValueError("Budget amounts must be finite and nonnegative")
    return int((value * 1000000).to_integral_value(rounding=ROUND_CEILING))


@contextmanager
def _locked(episode):
    path = _path(episode)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(path) + ".lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield path


def _save(path, data):
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(data, handle, indent=1)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def status(episode):
    path = _path(episode)
    data = json.loads(path.read_text()) if path.exists() else {}
    used = sum(item["units"] for item in data.get("requests", [])
               if item["state"] in {"reserved", "committed", "unknown"})
    limit = data.get("limitUnits", 0)
    return {"episode": episode, "approved": bool(data.get("approvedBy")),
            "limitUsd": limit / 1000000, "usedAndReservedUsd": used / 1000000,
            "remainingUsd": max(0, limit - used) / 1000000,
            "basis": "Configured estimated provider costs in USD, excluding tax; not an invoice guarantee",
            "proposal": data.get("proposal"),
            "unknownRequests": sum(x["state"] == "unknown" for x in data.get("requests", []))}


def approve(episode, amount, by, script_version):
    units = _units(amount)
    if units <= 0 or not str(by).strip() or not script_version:
        raise ValueError("A positive allowance, reviewer and current script are required")
    with _locked(episode) as path:
        data = json.loads(path.read_text()) if path.exists() else {"requests": []}
        used = sum(x["units"] for x in data["requests"] if x["state"] != "released")
        if units < used:
            raise BudgetRefused("The allowance cannot be lower than spending already committed or reserved")
        data.update(episode=episode, limitUnits=units, approvedBy=by,
                    scriptVersion=script_version, approvedAt=time.time())
        _save(path, data)
    return status(episode)


def propose(script_text):
    """Zero-call planning allowance, explicitly provisional until shot planning exists."""
    import cb_costs
    import cb_llm
    scenes = max(1, len(re.findall(r"(?m)^\s*(?:\d+\s+)?(?:INT\.|EXT\.|INT/EXT\.)", script_text)))
    shots = max(scenes, math.ceil(len(script_text.split()) / 50))
    rates = cb_llm._model_rates(cb_llm.VALIDATOR_MODEL)
    text = (2 + scenes * 4 + shots * 8) * (20000 * rates["input"] + 8000 * rates["output"]) / 1000000
    stills = scenes * cb_costs.estimate_image_cost() + shots * (cb_costs.estimate_image_cost(num_refs=10) + cb_costs.estimate_image_cost(provider="nanobanana2"))
    voice = cb_costs.estimate_tts_cost(script_text)
    video = cb_costs.estimate_video_cost("seedance_25_byteplus_480p_per_sec", shots * 30)
    base = text + stills + voice + video
    return {"suggestedUsd": math.ceil(base * 1.25), "estimatedShots": shots,
            "assumptions": "Provisional: roughly 50 script words per 30-second shot; one WATCH take, SEE A/B, voice and internal direction, plus 25% revision allowance. Final shot count and provider invoices may differ.",
            "estimatedComponentsUsd": {"direction": round(text, 2), "keyframes": round(stills, 2), "voice": round(voice, 2), "animation": round(video, 2)}}


def require_allowance(episode, script_version, script_text=None):
    """Register a new upload without granting spending permission or resetting prior use."""
    with _locked(episode) as path:
        if not path.exists():
            _save(path, {"episode": episode, "scriptVersion": script_version,
                         "requests": [], "limitUnits": 0,
                         "proposal": propose(script_text) if script_text else None})
    return status(episode)


def reserve(episode, amount, operation):
    units = _units(amount)
    if units <= 0:
        raise BudgetRefused("This operation needs a positive verified cost estimate")
    with _locked(episode) as path:
        if not path.exists():
            raise BudgetRefused("Approve the episode allowance before generation")
        data = json.loads(path.read_text())
        used = sum(x["units"] for x in data["requests"] if x["state"] != "released")
        if not data.get("approvedBy") or used + units > data.get("limitUnits", 0):
            raise BudgetRefused("Episode allowance reached; no new provider request was submitted")
        key = uuid.uuid4().hex
        data["requests"].append({"id": key, "units": units, "operation": operation,
                                 "state": "reserved", "at": time.time()})
        _save(path, data)
    return key


def finish(episode, key, state, actual=None):
    if state not in {"committed", "unknown", "released"}:
        raise ValueError("Invalid budget outcome")
    with _locked(episode) as path:
        data = json.loads(path.read_text())
        item = next(x for x in data["requests"] if x["id"] == key)
        if actual is not None:
            item["units"] = _units(actual)
        item["state"] = state
        _save(path, data)


def episode_from_output(out=None):
    match = re.search(r"(?:^|[_/])((?:Ep)[0-9]+)(?:_|$)", str(out or ""))
    return match.group(1) if match else (os.environ.get("CB_PRODUCTION_EPISODE") or
                                       ((_quote.get() or (None,))[0]))


def provider(operation, estimate):
    """Attach a quote to a production operation; only real submission consumes it."""
    def decorate(function):
        signature = inspect.signature(function)
        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            episode = episode_from_output(bound.arguments.get("out"))
            if not episode or not _path(episode).exists():
                return function(*args, **kwargs)
            with quote(episode, estimate(bound.arguments), operation):
                return function(*args, **kwargs)
        return wrapped
    return decorate


@contextmanager
def quote(episode, amount, operation):
    token = _quote.set((episode, amount, operation) if episode else None)
    try:
        yield
    finally:
        _quote.reset(token)


def active():
    value = _quote.get()
    return bool(value and _path(value[0]).exists())


def configured(episode):
    return bool(episode and _path(episode).exists())


def call(function):
    value = _quote.get()
    if not active():
        return function()
    episode, amount, operation = value
    key = reserve(episode, amount, operation)
    try:
        result = function()
    except BaseException:
        # A missing response is not proof that nothing was charged. Retain the allowance.
        finish(episode, key, "unknown")
        raise
    finish(episode, key, "committed")
    return result
