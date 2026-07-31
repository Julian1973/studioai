#!/usr/bin/env python3
"""cb_llm.py — the DIRECTOR PROVIDER ABSTRACTION (OpenAI first, Gemini fallback).

The Director's structured reasoning (scene + beat breakdown) runs on OpenAI with strict Structured Outputs and
Pydantic validation. If OpenAI ERRORS, it STOPS by default with the exact OpenAI error; a Gemini fallback exists
but is OFF unless DIRECTOR_ENABLE_GEMINI_FALLBACK=true (the Gemini config is kept, not removed — Gemini is the
unstable Director path). Gemini / Nano Banana otherwise stay on keyframe IMAGE generation (cb_gen). Keys are read from the
ENVIRONMENT only (engine/.env) — never hardcoded in source, never sent to app.html / the frontend.

Configuration (env, with safe defaults):
    OPENAI_API_KEY          required — clean failure (SystemExit) if missing
    OPENAI_DIRECTOR_MODEL   default gpt-5.5        — the main Director model
    OPENAI_VALIDATOR_MODEL  default gpt-5.4-mini   — the validate / repair model
    DIRECTOR_GEMINI_MODEL   default gemini-3.1-pro-preview — the FALLBACK model id
    DIRECTOR_ENABLE_GEMINI_FALLBACK  default false — Gemini fallback OFF; an OpenAI failure STOPS with the exact error

Calls (all schema-constrained + Pydantic-validated):
  • structured()             — one call: OpenAI(model); on a provider error, Gemini FALLBACK only if enabled,
                               else STOP with the exact OpenAI error (Gemini fallback is OFF by default).
  • structured_with_repair() — structured() + ONE repair call if the response fails Pydantic validation.
  • repair_call()            — a single repair call on the VALIDATOR model, seeded with business-rule errors.
A Pydantic ValidationError propagates (the caller repairs / stops + reports); both providers failing → SystemExit.
"""
import os, re, json, base64, mimetypes, pathlib
from pydantic import ValidationError
import cb_gen   # importing cb_gen loads engine/.env into os.environ (keys never leave the backend)

# models — environment first, defaults second (rule: read from env; never hardcode secrets)
DIRECTOR_MODEL = os.environ.get("OPENAI_DIRECTOR_MODEL", "gpt-5.5")
VALIDATOR_MODEL = os.environ.get("OPENAI_VALIDATOR_MODEL", "gpt-5.4-mini")
GEMINI_MODEL = os.environ.get("DIRECTOR_GEMINI_MODEL", "gemini-3.1-pro-preview")   # FALLBACK only (kept, not used by default)
# Gemini is currently the UNSTABLE Director path, so its fallback is OFF BY DEFAULT. When false, an OpenAI failure
# STOPS with the EXACT OpenAI error instead of silently producing inconsistent Gemini results. Set =true to re-enable.
ENABLE_GEMINI_FALLBACK = os.environ.get("DIRECTOR_ENABLE_GEMINI_FALLBACK", "false").strip().lower() in ("1", "true", "yes", "on")
MAX_OUTPUT_TOKENS = 32000

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
        _client = OpenAI(api_key=_openai_key())
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


def _openai_call(model, system, user, schema, images=None):
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
    resp = _client_get().responses.parse(
        model=model,
        input=[{"role": "system", "content": [{"type": "input_text", "text": system}]},
               {"role": "user", "content": user_parts}],
        text_format=schema,
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )
    obj = resp.output_parsed
    if obj is None:
        raise RuntimeError(f"no parsed output (status={getattr(resp, 'status', '?')}, possible refusal)")
    return obj

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
            "generationConfig": {"temperature": 0.6, "maxOutputTokens": 65536, "responseMimeType": "application/json"}}
    r = requests.post(url, headers={"x-goog-api-key": cb_gen.GEMINI_KEY, "Content-Type": "application/json"},
                      json=body, timeout=600)
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
    return schema.model_validate(_loads(text))

def structured(system, user, schema, *, model=None, label="director", log=print, images=None):
    """ONE structured Director call — OpenAI FIRST, then Gemini FALLBACK on a PROVIDER error. `model` is the OpenAI
    model (defaults to the Director model; pass VALIDATOR_MODEL for the validator). A Pydantic ValidationError is
    NOT a fallback case (the model answered, just off-schema) — it propagates so the caller can repair. Returns the
    validated Pydantic instance."""
    model = model or DIRECTOR_MODEL
    try:
        return _openai_call(model, system, user, schema, images=images)
    except ValidationError:
        raise
    except Exception as e:
        if not ENABLE_GEMINI_FALLBACK:
            # Gemini fallback is OFF by default — STOP cleanly and surface the EXACT OpenAI error (rather than
            # silently producing inconsistent Gemini results). Re-enable with DIRECTOR_ENABLE_GEMINI_FALLBACK=true.
            raise SystemExit(f"Director provider error ({label}): OpenAI ({model}) failed and the Gemini fallback is "
                             f"DISABLED (set DIRECTOR_ENABLE_GEMINI_FALLBACK=true to allow it). "
                             f"Exact OpenAI error — {type(e).__name__}: {e}")
        log(f"  [director] {label}: OpenAI {model} error: {str(e)[:130]} — DIRECTOR_ENABLE_GEMINI_FALLBACK=true, "
            f"falling back to Gemini {GEMINI_MODEL}", flush=True)
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

def structured_with_repair(system, user, schema, *, model=None, label="director", log=print,
                           images=None):
    """structured() + ONE Pydantic-error-driven repair call. If the repair ALSO fails validation, the
    ValidationError propagates to the caller (stop + report)."""
    try:
        return structured(system, user, schema, model=model, label=label, log=log,
                          images=images)
    except ValidationError as e:
        log(f"  [director] {label}: response failed Pydantic validation — running ONE repair call…", flush=True)
        return structured(system, _repair_user(user, e), schema, model=model,
                          label=label + "/repair", log=log, images=images)

def repair_call(system, user, schema, errors, *, label="validator", log=print):
    """A single repair call on the VALIDATOR model (OPENAI_VALIDATOR_MODEL), seeded with externally-found
    business-rule errors — used by validate_scene_beats."""
    return structured(system, _repair_user(user, errors), schema, model=VALIDATOR_MODEL,
                      label=label + "/repair", log=log)
