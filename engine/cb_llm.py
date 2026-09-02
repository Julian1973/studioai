#!/usr/bin/env python3
"""cb_llm.py — the DIRECTOR PROVIDER ABSTRACTION (OpenAI first, Gemini fallback).

The Director's structured reasoning (scene + beat breakdown) runs on OpenAI with strict Structured Outputs and
Pydantic validation. If OpenAI ERRORS, it STOPS by default with the exact OpenAI error; a Gemini fallback exists
but is OFF unless DIRECTOR_ENABLE_GEMINI_FALLBACK=true (the Gemini config is kept, not removed — Gemini is the
unstable Director path). Gemini / Nano Banana otherwise stay on keyframe IMAGE generation (cb_gen). Keys are read from the
ENVIRONMENT only (engine/.env) — never hardcoded in source, never sent to app.html / the frontend.

Configuration (env, with safe defaults):
    OPENAI_API_KEY          required — clean failure (SystemExit) if missing
    OPENAI_DIRECTOR_MODEL   default gpt-5.5        — premium Story & Direction only
    OPENAI_VALIDATOR_MODEL  default gpt-5.4-mini   — every shot department and repair
    OPENAI_MAX_CALL_USD     default 1.00           — conservative pre-call ceiling
    OPENAI_DAILY_BUDGET_USD default 5.00           — hard daily text-direction budget
    DIRECTOR_GEMINI_MODEL   default gemini-3.1-pro-preview — the FALLBACK model id
    DIRECTOR_ENABLE_GEMINI_FALLBACK  default false — Gemini fallback OFF; an OpenAI failure STOPS with the exact error

Calls (all schema-constrained + Pydantic-validated):
  • structured()             — one call: OpenAI(model); on a provider error, Gemini FALLBACK only if enabled,
                               else STOP with the exact OpenAI error (Gemini fallback is OFF by default).
  • structured_with_repair() — structured() + ONE repair call if the response fails Pydantic validation.
  • repair_call()            — a single repair call on the VALIDATOR model, seeded with business-rule errors.
A Pydantic ValidationError propagates (the caller repairs / stops + reports); both providers failing → SystemExit.
"""
import os, re, json, base64, mimetypes, pathlib, time, hashlib, math
import fcntl
from contextlib import contextmanager
from typing import get_origin
from pydantic import ValidationError
import cb_gen   # importing cb_gen loads engine/.env into os.environ (keys never leave the backend)
import cb_costs

# models — environment first, defaults second (rule: read from env; never hardcode secrets)
DIRECTOR_MODEL = os.environ.get("OPENAI_DIRECTOR_MODEL", "gpt-5.5")
VALIDATOR_MODEL = os.environ.get("OPENAI_VALIDATOR_MODEL", "gpt-5.4-mini")
GEMINI_MODEL = os.environ.get("DIRECTOR_GEMINI_MODEL", "gemini-3.1-pro-preview")   # FALLBACK only (kept, not used by default)
# Gemini is currently the UNSTABLE Director path, so its fallback is OFF BY DEFAULT. When false, an OpenAI failure
# STOPS with the EXACT OpenAI error instead of silently producing inconsistent Gemini results. Set =true to re-enable.
ENABLE_GEMINI_FALLBACK = os.environ.get("DIRECTOR_ENABLE_GEMINI_FALLBACK", "false").strip().lower() in ("1", "true", "yes", "on")
PREMIUM_MAX_OUTPUT_TOKENS = int(os.environ.get("OPENAI_PREMIUM_MAX_OUTPUT_TOKENS", "24000"))
STANDARD_MAX_OUTPUT_TOKENS = int(os.environ.get("OPENAI_STANDARD_MAX_OUTPUT_TOKENS", "12000"))
MAX_OUTPUT_TOKENS = PREMIUM_MAX_OUTPUT_TOKENS  # backwards-compatible public constant
OPENAI_DAILY_BUDGET_USD = float(os.environ.get("OPENAI_DAILY_BUDGET_USD", "5.00"))
OPENAI_MAX_CALL_USD = float(os.environ.get("OPENAI_MAX_CALL_USD", "1.00"))
OPENAI_RESPONSE_CACHE = os.environ.get("OPENAI_RESPONSE_CACHE", "true").strip().lower() in (
    "1", "true", "yes", "on")
OPENAI_CACHE_DIR = pathlib.Path(__file__).resolve().parent / "_llm_response_cache"
OPENAI_COST_LOCK_PATH = pathlib.Path(__file__).resolve().parent / ".openai_cost_guard.lock"

# Published OpenAI API text-token prices, USD per one million tokens (2026-09-02).
# Unknown models are refused because their spend cannot be bounded honestly.
OPENAI_TEXT_RATES = {
    "gpt-5.5": {"input": 5.00, "cached_input": 0.50, "output": 30.00},
    "gpt-5.4": {"input": 2.50, "cached_input": 0.25, "output": 15.00},
    "gpt-5.4-mini": {"input": 0.75, "cached_input": 0.075, "output": 4.50},
}
try:
    PROVIDER_TIMEOUT_SECONDS = max(
        10.0, float(os.environ.get("DIRECTOR_PROVIDER_TIMEOUT_SECONDS", "180")))
except (TypeError, ValueError):
    PROVIDER_TIMEOUT_SECONDS = 180.0
try:
    PROVIDER_ATTEMPTS = min(
        3, max(1, int(os.environ.get("DIRECTOR_PROVIDER_ATTEMPTS", "1"))))
except (TypeError, ValueError):
    PROVIDER_ATTEMPTS = 1

# FIXED 2026-07-12 (full-codebase audit continued): PROVIDER + DIRECTOR_PROVIDER (a "config summary" dict built
# from PROVIDER/DIRECTOR_MODEL/VALIDATOR_MODEL/GEMINI_MODEL/ENABLE_GEMINI_FALLBACK) had zero callers anywhere in
# the live codebase — confirmed by grep, inert data nobody ever read. The one place that would plausibly consume
# a provider-config summary, cb_director.py's own startup log, already builds its message from the individual
# constants directly, bypassing this dict entirely. Removed rather than left as unread dead data; the individual
# constants above are the real, live source of truth and are already used everywhere that needs them.


def _openai_key():
    """The OpenAI key, from the environment ONLY. Clean, clear failure if it is missing."""
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise SystemExit("OPENAI_API_KEY is missing — add it to engine/.env (env only; never hardcode it or expose "
                         f"it to the frontend). The Director runs on OpenAI ({DIRECTOR_MODEL}); override the models "
                         "with OPENAI_DIRECTOR_MODEL / OPENAI_VALIDATOR_MODEL.")
    return key

_client = None
def _client_get():
    global _client
    if _client is None:
        from openai import OpenAI
        # A stalled Director call must fail once and return control to the Studio;
        # the SDK's default retries multiply the timeout and look like a hang.
        _client = OpenAI(api_key=_openai_key(), timeout=PROVIDER_TIMEOUT_SECONDS,
                         max_retries=0)
    return _client

def _image_part(path):
    """Return one local image as an OpenAI Responses input part.

    Department workers use this to look at the *actual* approved frame they are directing
    or reviewing.  Keeping the conversion here means every specialist and the paid render
    path share one authoritative attachment order; the browser never sends provider data.
    """
    p = pathlib.Path(path)
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"specialist image input is missing: {p}")
    mime = mimetypes.guess_type(p.name)[0] or "image/png"
    encoded = base64.b64encode(p.read_bytes()).decode("ascii")
    return {"type": "input_image", "image_url": f"data:{mime};base64,{encoded}"}


def _model_rates(model):
    if model in OPENAI_TEXT_RATES:
        return OPENAI_TEXT_RATES[model]
    for base in sorted(OPENAI_TEXT_RATES, key=len, reverse=True):
        rates = OPENAI_TEXT_RATES[base]
        if str(model).startswith(base + "-"):
            return rates
    raise SystemExit(
        f"OPENAI COST GUARD — model {model!r} has no verified price in OPENAI_TEXT_RATES; "
        "the Studio refused the call before spend.")


def _estimated_input_tokens(system, user, schema, images=None):
    """Conservative pre-call estimate used only to enforce a spend ceiling."""
    schema_text = json.dumps(schema.model_json_schema(), ensure_ascii=False, separators=(",", ":"))
    text_tokens = math.ceil((len(system) + len(user) + len(schema_text)) / 4.0)
    return text_tokens + (5000 * len(images or []))


def _estimated_call_cost(model, system, user, schema, images, max_output_tokens):
    rates = _model_rates(model)
    input_tokens = _estimated_input_tokens(system, user, schema, images)
    return ((input_tokens * rates["input"] + max_output_tokens * rates["output"]) / 1_000_000.0,
            input_tokens)


def _daily_openai_spend(now=None):
    now = time.time() if now is None else float(now)
    day_start = now - ((time.localtime(now).tm_hour * 3600) +
                       (time.localtime(now).tm_min * 60) + time.localtime(now).tm_sec)
    total = 0.0
    try:
        with open(cb_costs.LEDGER_PATH) as ledger:
            for line in ledger:
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if row.get("op") == "openai_text" and float(row.get("ts") or 0) >= day_start:
                    total += float(row.get("cost_usd") or 0)
    except FileNotFoundError:
        pass
    return total


def _assert_cost_budget(model, system, user, schema, images, max_output_tokens):
    estimate, estimated_input_tokens = _estimated_call_cost(
        model, system, user, schema, images, max_output_tokens)
    if estimate > OPENAI_MAX_CALL_USD:
        raise SystemExit(
            f"OPENAI COST GUARD — estimated maximum ${estimate:.4f} exceeds the "
            f"${OPENAI_MAX_CALL_USD:.2f} per-call limit; no provider call was made.")
    spent = _daily_openai_spend()
    if spent + estimate > OPENAI_DAILY_BUDGET_USD:
        raise SystemExit(
            f"OPENAI COST GUARD — ${spent:.4f} is already logged today and this call could cost "
            f"up to ${estimate:.4f}, exceeding the ${OPENAI_DAILY_BUDGET_USD:.2f} daily limit; "
            "no provider call was made.")
    return estimate, estimated_input_tokens


@contextmanager
def _cost_guard_lock():
    """Serialize text calls across Studio workers so the daily cap cannot race."""
    with open(OPENAI_COST_LOCK_PATH, "a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def cost_policy():
    """Read-only policy summary for the Studio cost surface."""
    return {
        "premium": {"model": DIRECTOR_MODEL, "use": "Story & Direction only",
                    "maxOutputTokens": PREMIUM_MAX_OUTPUT_TOKENS,
                    "reasoningEffort": "medium"},
        "standard": {"model": VALIDATOR_MODEL,
                     "use": "scene, shot, keyframe, voice, animation and review direction",
                     "maxOutputTokens": STANDARD_MAX_OUTPUT_TOKENS,
                     "reasoningEffort": "low"},
        "perCallLimitUsd": OPENAI_MAX_CALL_USD,
        "dailyLimitUsd": OPENAI_DAILY_BUDGET_USD,
        "spentTodayUsd": round(_daily_openai_spend(), 6),
        "identicalResponseReuse": OPENAI_RESPONSE_CACHE,
        "providerAttempts": PROVIDER_ATTEMPTS,
        "geminiFallbackEnabled": ENABLE_GEMINI_FALLBACK,
        "pricingAsOf": "2026-09-02",
    }


def _cache_digest(model, system, user, schema, images, max_output_tokens, reasoning_effort):
    digest = hashlib.sha256()
    for value in ("v1", model, system, user, schema.__module__, schema.__qualname__,
                  str(max_output_tokens), reasoning_effort):
        digest.update(str(value).encode("utf-8")); digest.update(b"\0")
    digest.update(json.dumps(schema.model_json_schema(), sort_keys=True,
                             ensure_ascii=False).encode("utf-8"))
    for path in (images or []):
        with open(path, "rb") as image:
            for chunk in iter(lambda: image.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def _cache_load(digest, schema):
    if not OPENAI_RESPONSE_CACHE:
        return None
    path = OPENAI_CACHE_DIR / f"{digest}.json"
    try:
        return schema.model_validate_json(path.read_text())
    except FileNotFoundError:
        return None
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        return None


def _cache_store(digest, obj):
    if not OPENAI_RESPONSE_CACHE:
        return
    try:
        OPENAI_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = OPENAI_CACHE_DIR / f"{digest}.json"
        tmp = OPENAI_CACHE_DIR / f".{digest}.{os.getpid()}.tmp"
        tmp.write_text(obj.model_dump_json())
        os.replace(tmp, path)
    except Exception:
        pass


def _usage_value(obj, name):
    if obj is None:
        return 0
    if isinstance(obj, dict):
        return int(obj.get(name) or 0)
    return int(getattr(obj, name, 0) or 0)


def _log_openai_usage(resp, model, label, estimated_max_cost):
    usage = getattr(resp, "usage", None)
    input_tokens = _usage_value(usage, "input_tokens")
    output_tokens = _usage_value(usage, "output_tokens")
    details = usage.get("input_tokens_details") if isinstance(usage, dict) else getattr(
        usage, "input_tokens_details", None)
    cached_tokens = min(input_tokens, _usage_value(details, "cached_tokens"))
    rates = _model_rates(model)
    cost = (((input_tokens - cached_tokens) * rates["input"] +
             cached_tokens * rates["cached_input"] + output_tokens * rates["output"]) /
            1_000_000.0)
    cb_costs.log_spend("openai_text", cost, meta={
        "model": model, "label": label, "inputTokens": input_tokens,
        "cachedInputTokens": cached_tokens, "outputTokens": output_tokens,
        "estimatedMaximumCostUsd": round(estimated_max_cost, 6),
        "pricingAsOf": "2026-09-02",
    })
    return cost


def _non_retryable_provider_error(exc):
    low = f"{type(exc).__name__}: {exc}".lower()
    return any(marker in low for marker in (
        "insufficient_quota", "credit_balance_exhausted", "no credits remaining",
        "authenticationerror", "permissiondeniederror", "badrequesterror",
        "notfounderror", "unprocessableentityerror", "invalid_api_key",
    ))


def _openai_call(model, system, user, schema, images=None, *, max_output_tokens,
                 reasoning_effort):
    """A single strict-Structured-Output OpenAI call → a validated Pydantic instance (raises on refusal).

    FIXED 2026-07-07 (found while proving THE FIDELITY-ALLOCATION LAW's live-fire path, completely unrelated to
    that feature): the installed openai SDK (2.41.1) now requires each message's `content` as a list of typed
    content parts (`[{"type": "input_text", "text": ...}]`), not a plain string — the plain-string form that
    worked at this session's earlier full-episode fire (CLAUDE.md rule 47, "ran for real, 3403s, exit code 0")
    now raises "expected an object, but got a string instead" on EVERY call, meaning the Director could not
    fire AT ALL until this was fixed — a real, currently-blocking regression from an SDK version drift, not a
    bug in any beat/schema logic. Verified directly against the real API (a `.parse()` call with a tiny dummy
    schema) before applying this exact fix, not guessed at."""
    user_parts = [{"type": "input_text", "text": user}]
    user_parts.extend(_image_part(p) for p in (images or []))
    prompt_cache_key = "crystal-bears-" + hashlib.sha256(
        f"{model}\0{schema.__module__}.{schema.__qualname__}\0{system}".encode("utf-8")
    ).hexdigest()[:40]
    resp = _client_get().responses.parse(
        model=model,
        input=[{"role": "system", "content": [{"type": "input_text", "text": system}]},
               {"role": "user", "content": user_parts}],
        text_format=schema,
        max_output_tokens=max_output_tokens,
        reasoning={"effort": reasoning_effort},
        verbosity="low",
        prompt_cache_key=prompt_cache_key,
        prompt_cache_retention="24h",
    )
    obj = resp.output_parsed
    if obj is None:
        raise RuntimeError(f"no parsed output (status={getattr(resp, 'status', '?')}, possible refusal)")
    return obj, resp

def repair_truncated(s):
    """Close a JSON reply cut off by the token cap (open string, dangling comma, missing ]/}) — recover the
    complete elements. FIXED 2026-07-12 (loose-ends pass): this was hand-duplicated in cb_writer.py as its own
    module-private `_repair_truncated` — moved here (the shared LLM-plumbing module) as the one canonical copy;
    cb_writer.py now imports it."""
    stack = []; in_str = esc = False
    for ch in s:
        if in_str:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == '"': in_str = False
        else:
            if ch == '"': in_str = True
            elif ch in "{[": stack.append(ch)
            elif ch in "}]" and stack: stack.pop()
    out = (s + ('"' if in_str else "")).rstrip()
    if out.endswith(","): out = out[:-1].rstrip()
    for ch in reversed(stack):
        out += "}" if ch == "{" else "]"
    return out

def _loads(text):
    """JSON recovery for the Gemini fallback: strip code fences, decode the first complete value, then — as of
    2026-07-12 (loose-ends pass) — also try closing a token-cap-truncated reply (repair_truncated) before giving
    up, the same recovery tier cb_writer.py's own _loadjson already had and this function was missing."""
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\n", "", t).rsplit("```", 1)[0].strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    i = next((k for k, c in enumerate(t) if c in "{["), -1)
    if i < 0:
        raise ValueError(f"no JSON object/array found in text ({len(t)} chars)")
    body = t[i:]
    try:
        return json.JSONDecoder().raw_decode(body)[0]
    except Exception:
        return json.loads(repair_truncated(body))


def _normalize_single_list_model(value, schema):
    """Accept a bare list for a model whose only field is that list.

    Gemini occasionally follows the inner array in a JSON schema while omitting
    the one-field object wrapper. The payload is otherwise complete and can be
    validated without weakening any item-level or length constraints.
    """
    if not isinstance(value, list):
        return value
    fields = getattr(schema, "model_fields", {})
    if len(fields) != 1:
        return value
    field_name, field = next(iter(fields.items()))
    if get_origin(field.annotation) is not list:
        return value
    return {field_name: value}


def _gemini_generation_config(schema):
    """Build Gemini JSON mode with the same schema enforced by OpenAI/Pydantic."""
    return {
        "temperature": 0.6,
        "maxOutputTokens": 65536,
        "responseMimeType": "application/json",
        "responseJsonSchema": schema.model_json_schema(),
    }

def _gemini_call(system, user, schema, images=None):
    """FALLBACK ONLY — Gemini JSON mode, then re-validate against the SAME Pydantic schema (off-schema raises
    ValidationError just like the OpenAI path). Uses the existing Gemini config in cb_gen — kept, not removed."""
    import requests
    if not cb_gen.GEMINI_KEY:
        raise RuntimeError("no GEMINI_API_KEY for the Director fallback")
    url = f"{cb_gen.GLA}/v1beta/models/{GEMINI_MODEL}:generateContent"
    parts = [{"text": user}]
    for path in (images or []):
        p = pathlib.Path(path)
        if not p.exists() or not p.is_file():
            raise FileNotFoundError(f"specialist image input is missing: {p}")
        parts.append({"inline_data": {
            "mime_type": mimetypes.guess_type(p.name)[0] or "image/png",
            "data": base64.b64encode(p.read_bytes()).decode("ascii")}})
    body = {"system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": _gemini_generation_config(schema)}
    r = requests.post(url, headers={"x-goog-api-key": cb_gen.GEMINI_KEY, "Content-Type": "application/json"},
                      json=body, timeout=PROVIDER_TIMEOUT_SECONDS)
    if r.status_code != 200:
        raise RuntimeError(f"Gemini {r.status_code}: {r.text[:200]}")
    rj = r.json()
    # FIXED 2026-07-12 (full-codebase audit continued): indexed candidates[0] with no guard for a safety-blocked
    # or otherwise candidate-less response (HTTP 200, a bare {"promptFeedback": {...}}, or "candidates": []) —
    # raised a bare KeyError/IndexError instead of naming the block reason, unlike this exact Gemini
    # generateContent response shape's siblings elsewhere in this codebase (cb_gen.py's
    # _generate_image_nanobanana, cb_writer.py's _gen()), which both guard it explicitly before indexing.
    # structured()'s own `except Exception as e2` still catches whatever this raises and re-raises it as a
    # SystemExit either way, so this was never a silent crash — just a worse diagnostic than every sibling caller
    # already gives for the identical failure mode.
    if not rj.get("candidates"):
        raise RuntimeError(f"Gemini returned no candidates (likely a safety block): {str(rj)[:300]}")
    text = rj["candidates"][0]["content"]["parts"][0]["text"]
    payload = _normalize_single_list_model(_loads(text), schema)
    return schema.model_validate(payload)

def structured(system, user, schema, *, model=None, tier="standard", label="director", log=print,
               images=None, max_output_tokens=None, reasoning_effort=None, reuse=True):
    """One bounded structured call.

    Standard is deliberately the default, so a new department cannot silently inherit the
    premium model. Only the episode Story & Direction entry points pass tier="premium".
    """
    if tier not in ("standard", "premium"):
        raise ValueError(f"unknown OpenAI cost tier: {tier!r}")
    model = model or (DIRECTOR_MODEL if tier == "premium" else VALIDATOR_MODEL)
    max_output_tokens = int(max_output_tokens or (
        PREMIUM_MAX_OUTPUT_TOKENS if tier == "premium" else STANDARD_MAX_OUTPUT_TOKENS))
    reasoning_effort = reasoning_effort or ("medium" if tier == "premium" else "low")
    digest = _cache_digest(model, system, user, schema, images, max_output_tokens, reasoning_effort)
    if reuse:
        cached = _cache_load(digest, schema)
        if cached is not None:
            log(f"  [director] {label}: reused identical signed direction locally — no API call, $0", flush=True)
            return cached
    openai_error = None
    with _cost_guard_lock():
        # Another Studio worker may have completed this exact request while this
        # worker waited for the lock. Recheck before authorizing any spend.
        if reuse:
            cached = _cache_load(digest, schema)
            if cached is not None:
                log(f"  [director] {label}: reused identical signed direction locally — no API call, $0",
                    flush=True)
                return cached
        estimated_max_cost, _ = _assert_cost_budget(
            model, system, user, schema, images, max_output_tokens)
        for attempt in range(1, PROVIDER_ATTEMPTS + 1):
            try:
                obj, resp = _openai_call(
                    model, system, user, schema, images=images,
                    max_output_tokens=max_output_tokens, reasoning_effort=reasoning_effort)
                actual_cost = _log_openai_usage(resp, model, label, estimated_max_cost)
                _cache_store(digest, obj)
                log(f"  [director] {label}: OpenAI {model} completed — logged ${actual_cost:.4f}",
                    flush=True)
                return obj
            except ValidationError:
                raise
            except Exception as exc:
                openai_error = exc
                if _non_retryable_provider_error(exc):
                    break
                if attempt < PROVIDER_ATTEMPTS:
                    log(f"  [director] {label}: OpenAI {model} transport failure on attempt "
                        f"{attempt}/{PROVIDER_ATTEMPTS}; retrying the same typed call", flush=True)
                    time.sleep(min(2.0 * attempt, 4.0))
    e = openai_error
    if not ENABLE_GEMINI_FALLBACK:
        # Gemini fallback is OFF by default — STOP cleanly and surface the EXACT OpenAI error (rather than
        # silently producing inconsistent Gemini results). Re-enable with DIRECTOR_ENABLE_GEMINI_FALLBACK=true.
        raise SystemExit(f"Director provider error ({label}): OpenAI ({model}) failed after "
                         f"{PROVIDER_ATTEMPTS} attempt(s) and the Gemini fallback is DISABLED "
                         f"(set DIRECTOR_ENABLE_GEMINI_FALLBACK=true to allow it). "
                         f"Exact OpenAI error — {type(e).__name__}: {e}")
    log(f"  [director] {label}: OpenAI {model} error after {PROVIDER_ATTEMPTS} attempt(s): "
        f"{str(e)[:130]} — DIRECTOR_ENABLE_GEMINI_FALLBACK=true, falling back to Gemini "
        f"{GEMINI_MODEL}", flush=True)
    try:
        obj = _gemini_call(system, user, schema, images=images)
        log(f"  [director] {label}: served by Gemini fallback ({GEMINI_MODEL})", flush=True)
        return obj
    except ValidationError:
        raise
    except Exception as e2:
        raise SystemExit(f"Director provider error ({label}): OpenAI ({model}) AND Gemini ({GEMINI_MODEL}) both "
                         f"failed — {str(e2)[:220]}")

def _repair_user(user, errors):
    return (user + "\n\n════════ REPAIR — your previous reply FAILED validation ════════\n"
            "Return the COMPLETE corrected JSON for the SAME schema (nothing else, no prose). Do NOT change any "
            "LOCKED dialogue — fix only the structural problems named here:\n" + str(errors)[:1800])

def structured_with_repair(system, user, schema, *, model=None, tier="standard", label="director",
                           log=print, images=None, max_output_tokens=None,
                           reasoning_effort=None, reuse=True):
    """structured() + ONE Pydantic-error-driven repair call. If the repair ALSO fails validation, the
    ValidationError propagates to the caller (stop + report)."""
    try:
        return structured(system, user, schema, model=model, tier=tier, label=label, log=log,
                          images=images, max_output_tokens=max_output_tokens,
                          reasoning_effort=reasoning_effort, reuse=reuse)
    except ValidationError as e:
        log(f"  [director] {label}: response failed Pydantic validation — running ONE repair call…", flush=True)
        return structured(system, _repair_user(user, e), schema, model=model, tier=tier,
                          label=label + "/repair", log=log, images=images,
                          max_output_tokens=max_output_tokens,
                          reasoning_effort=reasoning_effort, reuse=reuse)

def repair_call(system, user, schema, errors, *, label="validator", log=print):
    """A single repair call on the VALIDATOR model (OPENAI_VALIDATOR_MODEL), seeded with externally-found
    business-rule errors — used by validate_scene_beats."""
    return structured(system, _repair_user(user, errors), schema, model=VALIDATOR_MODEL,
                      label=label + "/repair", log=log)
