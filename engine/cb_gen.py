#!/usr/bin/env python3
"""
Crystal Bears — local generation module (the app's provider layer).

Wires the crew's prompts to the real APIs, locally (no Replit):
  - generate_image()  -> DP keyframes; dispatches to Seedream 5 Pro (fal.ai, default, 2026-07-09) or
                         Nano Banana 2 (gemini-3.1-flash-image, kept live, CB_IMAGE_PROVIDER=nanobanana)
  - generate_video_seedance_ref() -> the capability-gated Seedance video adapter. Crystal Bears
                         targets Seedance 2.5 through BytePlus ModelArk; the historical fal 2.0
                         route is retained as code evidence but disabled in the provider registry.
  - generate_video()  -> Veo 3.1 (veo-3.1-generate-preview) [Camera i2v] — unused in production; CLI/manual-only.
  - eleven_tts()      -> ElevenLabs TTS (V3 acted masters)
  - voice_change()    -> RETIRED (CLAUDE.md rules 4/29 — no post voice swap, ever); raises loud on call, kept
                         only for the record.
  - list_voices()/keycheck -> cheap validity checks

FIXED 2026-07-12 (full-codebase audit continued): this list had drifted from the code — voice_change() was
listed as a live feature (it unconditionally raises RuntimeError; see its own RETIRED docstring below) and
generate_video_seedance_ref() (this module's actual sole production video path) wasn't mentioned at all, while
generate_video() (Veo) read as the production camera path even though no render caller anywhere uses it —
corrected above to match what the code actually does.

Keys come from cb-gen/.env (gitignored): GEMINI_API_KEY, ELEVENLABS_API_KEY.
Endpoints verified against ai.google.dev + elevenlabs.io docs (June 2026).
"""
import os, sys, json, time, base64, mimetypes, argparse, pathlib, subprocess, tempfile
import requests
import cb_costs
import cb_providers

HERE = pathlib.Path(__file__).resolve().parent
MEDIA = HERE / "media"
MEDIA.mkdir(exist_ok=True)

def _load_env():
    env = HERE / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
_load_env()

# THE keyframe image model — "Nano Banana 2" (gemini-3.1-flash-image): 2K, best reference-hold. A/B-confirmed 2026-06-28
# to hold fine identity markers on the CHAINED cascade where Pro (gemini-3-pro-image) dropped them. Override via CB_IMAGE_MODEL.
# HISTORICAL NOTE (2026-07-09): NB2 was the sole keyframe model from 2026-06-28 until today. Left as the dated record
# of that decision, not rewritten — see IMAGE_PROVIDER below for the current, superseding decision.
IMAGE_MODEL = os.environ.get("CB_IMAGE_MODEL", "gemini-3.1-flash-image")  # NB2 — the A/B winner for the cascade

# THE PROVIDER SWITCH (Julian's ruling, 2026-07-09 — "we go Seedream 5 pro, it's the one the industry is
# suggesting"): a real, evidence-based side-by-side on 1.B1's actual production prompt+references (identical
# 1086-word prompt, identical 3 refs — Fuzzby turnaround, Zenny turnaround, scene plate — fired through both
# models) found NB2 violated the Crystal World Rule outright (invented glowing hearts + swirling magic-light
# crystal auras, directly contradicting the prompt's own "NO crystal self-glow, aura, beams, particles" line)
# and dropped Zenny's signature identity detail (rosy blush cheeks, present on her turnaround); Seedream 5 Pro
# held both correctly. n=1 — a single seed each, not a benchmark, and generation is stochastic — so NB2 is
# KEPT LIVE, never deleted, selectable via CB_IMAGE_PROVIDER=nanobanana for rollback or a future re-test.
# Cost: Seedream 5 Pro runs ~40% more per image (~$0.144 vs NB2's real ~$0.101 at 2K, both confirmed against
# each vendor's own pricing page the same day — see cb_costs.py's RATES, also corrected today) — accepted as
# immaterial at episode scale (~43 keyframes).
IMAGE_PROVIDER = os.environ.get("CB_IMAGE_PROVIDER", "seedream")  # "seedream" (default) | "nanobanana" (rollback)
SEEDREAM_ENDPOINT = os.environ.get("CB_SEEDREAM_ENDPOINT", "bytedance/seedream/v5/pro/edit")
# THE SCENE LOOK PROVIDER-ROUTING FIX (2026-07-19): SEEDREAM_ENDPOINT above is an EDIT/reference
# endpoint — fal.ai requires at least one image in image_urls for it, and rejects an empty list
# with a deterministic 422 (found live: every Scene Look fire, which always called this endpoint
# with refs=[]). A no-reference generation must use a genuine TEXT-TO-IMAGE endpoint instead —
# left UNSET by default rather than guessing a plausible-looking model id (never invent an
# endpoint); set CB_SEEDREAM_T2I_ENDPOINT to enable no-reference generation on this provider.
SEEDREAM_T2I_ENDPOINT = os.environ.get("CB_SEEDREAM_T2I_ENDPOINT", "")

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
ELEVEN_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
GLA = "https://generativelanguage.googleapis.com"
XI = "https://api.elevenlabs.io"
FAL_KEY = os.environ.get("FAL_KEY", "")
FAL = "https://queue.fal.run"
BYTEPLUS_ARK_KEY = os.environ.get("BYTEPLUS_ARK_API_KEY", "")
BYTEPLUS_ARK = "https://ark.ap-southeast.bytepluses.com"
BYTEPLUS_MAX_REQUEST_BYTES = 64 * 1024 * 1024

def _b64(path):
    data = pathlib.Path(path).read_bytes()
    mime = mimetypes.guess_type(path)[0] or "image/png"
    return mime, base64.b64encode(data).decode()

def _need(key, name):
    if not key:
        raise SystemExit(f"{name} not set — add it to cb-gen/.env")

def _need_eleven_key():
    _need(ELEVEN_KEY, "ELEVENLABS_API_KEY")
    if not ELEVEN_KEY.startswith("sk_"):
        raise SystemExit(
            "ELEVENLABS_API_KEY is not a usable ElevenLabs API key. "
            "It looks like an API key ID; ElevenLabs API keys start with 'sk_'. "
            "Create or reveal a valid key in ElevenLabs and update engine/.env."
        )

# ── TICKET 5 — API RESILIENCE: retry + exponential backoff on EVERY external call. A transient blip (network drop,
#    429 rate-limit, 5xx, fal-queue hiccup) retries INSIDE the job instead of failing the whole render; a real client
#    error (4xx except 429) raises immediately so we don't loop on a bad request. ────────────────────────────────────
import random
_RETRY_STATUS = {429, 500, 502, 503, 504}
def _retryable(e):
    rx = requests.exceptions
    if isinstance(e, (rx.ConnectionError, rx.Timeout, rx.ChunkedEncodingError)):
        return True
    if isinstance(e, rx.HTTPError) and getattr(e, "response", None) is not None:
        return e.response.status_code in _RETRY_STATUS
    # FIXED 2026-07-19 (Scene Look provider-routing incident): fal_client's own FalClientHTTPError
    # carries a REAL status_code attribute — check it directly rather than guessing from str(e).
    # A Seedream 422 validation error's message is fal's own structured error body (e.g.
    # "[{'loc': [...], 'msg': 'Sequence should have at least 1 items', ...}]") with no "422" or
    # "unprocessable" substring anywhere in it — the string-matching fallback below silently missed
    # this exact class and retried a guaranteed-to-fail request 3 times before this fix.
    status = getattr(e, "status_code", None)
    if isinstance(status, int):
        return status in _RETRY_STATUS
    m = str(e).lower()
    if any(x in m for x in ("400", "401", "403", "404", "422", "invalid", "unprocessable", "bad request", "unauthor", "not found")):
        return False
    return True   # unknown (network / fal queue) — treat as transient and retry
def _retry(fn, what="API", tries=4, base=4.0, cap=60.0):
    for attempt in range(1, tries + 1):
        try:
            return fn()
        except Exception as e:
            if attempt >= tries or not _retryable(e):
                raise
            wait = min(cap, base * (2 ** (attempt - 1))) + random.uniform(0, 1.0)
            print(f"  [retry] {what}: attempt {attempt}/{tries} failed — {str(e)[:140]}; backoff {wait:.1f}s", flush=True)
            time.sleep(wait)
def _checked(r):
    try:
        r.raise_for_status()
    except requests.HTTPError as exc:
        body = ""
        try:
            body = (r.text or "")[:800]
        except Exception:
            body = ""
        raise requests.HTTPError(
            f"{exc} — provider response: {body}", response=r
        ) from exc
    return r
def _rpost(url, **kw):
    kw.setdefault("timeout", 120)
    return _retry(lambda: _checked(requests.post(url, **kw)), what="POST " + str(url).rsplit("/", 1)[-1][:24])
def _rget(url, **kw):
    kw.setdefault("timeout", 120)
    return _retry(lambda: _checked(requests.get(url, **kw)), what="GET " + str(url).rsplit("/", 1)[-1][:24])
def _fal_upload(path):
    import fal_client
    return _retry(lambda: fal_client.upload_file(path), what="fal upload")
def _fal_asset_url(value):
    """Keep already-uploaded fal URLs stable; upload local provider inputs once."""
    value = str(value)
    if value.startswith(("https://", "http://")):
        return value
    return _fal_upload(str(pathlib.Path(value)))
def _fal_subscribe(endpoint, arguments=None, with_logs=False):
    import fal_client
    return _retry(lambda: fal_client.subscribe(endpoint, arguments=arguments, with_logs=with_logs),
                  what="fal:" + str(endpoint).rsplit("/", 1)[-1])


def _byteplus_asset_url(value, kind):
    """Return a BytePlus-compatible URL/data URI without uploading to another provider."""
    value = str(value)
    if value.startswith(("https://", "http://", "asset://", "data:")):
        return value
    path = pathlib.Path(value)
    if not path.is_file():
        raise FileNotFoundError(f"BytePlus {kind} reference does not exist: {path}")
    mime = (mimetypes.guess_type(path.name)[0] or "").lower()
    allowed = {
        "image": {"image/jpeg", "image/png", "image/webp", "image/bmp", "image/tiff",
                  "image/gif", "image/heic", "image/heif"},
        "audio": {"audio/wav", "audio/x-wav", "audio/mpeg", "audio/mp3"},
    }
    if kind not in allowed or mime not in allowed[kind]:
        raise ValueError(f"unsupported BytePlus {kind} reference type: {mime or path.suffix}")
    size_limit = 30 * 1024 * 1024 if kind == "image" else 15 * 1024 * 1024
    if path.stat().st_size >= size_limit:
        raise ValueError(
            f"BytePlus {kind} reference is too large for an inline request: {path.name}")
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    canonical_mime = "audio/wav" if mime == "audio/x-wav" else (
        "audio/mpeg" if mime == "audio/mp3" else mime)
    return f"data:{canonical_mime};base64,{data}"


def _byteplus_task_url(endpoint):
    endpoint = str(endpoint or "").strip()
    if endpoint.startswith(("https://", "http://")):
        return endpoint.rstrip("/")
    return BYTEPLUS_ARK.rstrip("/") + "/" + endpoint.lstrip("/").rstrip("/")


def _byteplus_generate_video(contract, prompt, image_refs, audio_refs, resolution,
                             duration, out, *, poll_interval=10, timeout=3600):
    """Submit and retrieve one ModelArk asynchronous video task.

    Provider capability, spend authorization and billing confirmation happen before this
    transport is reachable. This function never chooses a model or fallback.
    """
    _need(BYTEPLUS_ARK_KEY, "BYTEPLUS_ARK_API_KEY")
    try:
        seconds = int(duration)
    except (TypeError, ValueError) as exc:
        raise ValueError("BytePlus duration must be an integer number of seconds") from exc
    if float(duration) != seconds:
        raise ValueError("BytePlus duration must be an integer number of seconds")

    content = [{"type": "text", "text": str(prompt)}]
    content.extend({"type": "image_url", "image_url": {
        "url": _byteplus_asset_url(value, "image")}, "role": "reference_image"}
        for value in image_refs)
    content.extend({"type": "audio_url", "audio_url": {
        "url": _byteplus_asset_url(value, "audio")}, "role": "reference_audio"}
        for value in audio_refs)
    body = {
        "model": contract["providerModelId"],
        "content": content,
        "generate_audio": True,
        "resolution": resolution,
        "ratio": "16:9",
        "duration": seconds,
        "watermark": False,
        "return_last_frame": True,
    }
    if len(json.dumps(body, ensure_ascii=False).encode("utf-8")) > BYTEPLUS_MAX_REQUEST_BYTES:
        raise ValueError(
            "BytePlus request body exceeds 64 MB; use public/asset URLs for larger references")

    headers = {"Authorization": f"Bearer {BYTEPLUS_ARK_KEY}",
               "Content-Type": "application/json"}
    task_url = _byteplus_task_url(contract["endpoint"])
    created = _rpost(task_url, headers=headers, json=body, timeout=120).json()
    task_id = str(created.get("id") or "").strip()
    if not task_id:
        raise RuntimeError("BytePlus video task creation returned no task ID")

    deadline = time.monotonic() + timeout
    task = None
    while time.monotonic() < deadline:
        task = _rget(f"{task_url}/{task_id}", headers=headers, timeout=120).json()
        status = str(task.get("status") or "").lower()
        if status == "succeeded":
            break
        if status in {"failed", "expired"}:
            error = task.get("error") or {}
            detail = error.get("message") if isinstance(error, dict) else str(error)
            raise RuntimeError(
                f"BytePlus video task {status}: {str(detail or 'no detail')[:300]}")
        if status not in {"queued", "running"}:
            raise RuntimeError(f"BytePlus video task returned unknown status: {status or 'blank'}")
        time.sleep(poll_interval)
    else:
        raise TimeoutError(f"BytePlus video task did not finish within {timeout} seconds")

    url = ((task or {}).get("content") or {}).get("video_url")
    if not url:
        raise RuntimeError("BytePlus video task succeeded without a video URL")
    video = _rget(url, timeout=300)
    outp = MEDIA / out
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_bytes(video.content)
    return outp, task_id, task

# ── Last-frame extractor (first/last-frame chaining for continuous flow) ──────
def last_frame(clip, out="lastframe.png"):
    import subprocess
    subprocess.run(["ffmpeg", "-y", "-sseof", "-0.1", "-i", clip,
                    "-update", "1", "-frames:v", "1", out],
                   check=True, capture_output=True)
    return out

# ── DP keyframes — provider dispatch (2026-07-09) ────────────────────────────

# ── THE SINGLE PRODUCTION ROUTE (Julian's cutover order, 2026-07-16) ─────────────────────────
# After the old Pipeline tab's Gate-3 button fired a legacy 15s mega-prompt around every spend
# protection ($4.57, uncontrolled), every PAID provider call now requires the authorized route
# sentinel. Only cb_render (the shot pipeline: disclosure -> sealed envelope -> single-use token)
# passes it. Every legacy caller — cb_beats, cb_retake, cb_replicator, cb_pipeline, cb_scene,
# cb_previz, cb_voice, this module's own CLI — is DISABLED AT RUNTIME at this chokepoint: legacy
# prompts and outputs stay archived and readable, but they can no longer reach a provider.
_AUTHORIZED_PRODUCTION_ROUTE = "cb_render"


def _require_production_route(production_route, op):
    if production_route != _AUTHORIZED_PRODUCTION_ROUTE:
        raise RuntimeError(
            f"BLOCKED — legacy fire route disabled (production cutover, 2026-07-16). Every paid "
            f"provider call ({op}) must travel through cb_render's shot pipeline: disclosure -> "
            f"sealed envelope -> Julian's single-use spend token. This call came from an "
            f"unauthorized route and spent nothing.")

def generate_image(prompt, refs=None, aspect="16:9", out="keyframe.png",
                   model=None, image_size="2K", production_route=None):
    _require_production_route(production_route, "generate_image")
    """THE single keyframe-generation entry point every cb_scene.py call site uses — unchanged signature, so
    no caller needed to change for the provider swap. Dispatches on IMAGE_PROVIDER (module-level, env-overridable
    via CB_IMAGE_PROVIDER): "seedream" (default, Seedream 5 Pro via fal.ai) or "nanobanana" (NB2 via direct
    Gemini API, kept live for rollback). `model=` is NB2-specific (a Gemini model id) and ignored by the
    Seedream path; passing it explicitly forces the nanobanana path's model regardless of IMAGE_PROVIDER,
    matching the old function's own back-compat contract for any caller that still passes model= explicitly."""
    if model or IMAGE_PROVIDER == "nanobanana":
        return _generate_image_nanobanana(prompt, refs, aspect, out, model or IMAGE_MODEL, image_size)
    return _generate_image_seedream(prompt, refs, aspect, out, image_size)

def _generate_image_seedream(prompt, refs=None, aspect="16:9", out="keyframe.png", image_size="2K"):
    """Seedream 5 Pro (bytedance/seedream/v5/pro/edit, fal.ai) — the default keyframe model as of 2026-07-09
    (see IMAGE_PROVIDER's doctrine comment above). Same reference-image contract as the NB2 path: a list of
    local file paths, uploaded to fal then passed as image_urls alongside the identical prompt text — the
    prompt/reference doctrine (rule 5's appearance-non-leak law, the four-anchor-style reference stack) is
    model-agnostic by design, so no prompt-building code changes for this swap."""
    _need(FAL_KEY, "FAL_KEY")
    os.environ["FAL_KEY"] = FAL_KEY
    import fal_client
    ref_urls = [_fal_upload(str(pathlib.Path(r))) for r in (refs or [])]
    # FIXED 2026-07-11 (full-codebase audit): this call never sent the requested aspect ratio or resolution at
    # all — both were silently dropped, despite generate_image()'s own public signature accepting them (and
    # the cost sidecar already logging aspect= as if it had been honoured). fal.ai's ByteDance-family image
    # endpoints accept "image_size" (a preset string, e.g. "square_hd"/"portrait_4_3"/"landscape_16_9", or a
    # {width,height} object) and "aspect_ratio" — mapped here to the SAME image_size convention this module's
    # NB2 path already uses ("2K" etc.) plus the beat's own aspect string, rather than silently omitted.
    #
    # PROVIDER ROUTING (2026-07-19 fix): SEEDREAM_ENDPOINT is edit-mode-only and fal.ai deterministically
    # 422s an empty image_urls list — never send it there. A call with real reference(s) uses the edit
    # endpoint exactly as before; a call with none uses the configured text-to-image endpoint, or refuses
    # loudly (no network call made) if none is configured, rather than inventing an endpoint id.
    if ref_urls:
        endpoint = SEEDREAM_ENDPOINT
        args = {"prompt": prompt, "image_urls": ref_urls, "image_size": image_size, "aspect_ratio": aspect}
    else:
        if not SEEDREAM_T2I_ENDPOINT:
            raise RuntimeError(
                "REFUSED — no reference image supplied and no supported Seedream text-to-image "
                "endpoint is configured (CB_SEEDREAM_T2I_ENDPOINT is unset). Refusing rather than "
                f"sending an empty image_urls list to the edit endpoint ({SEEDREAM_ENDPOINT}), which "
                "fal.ai always rejects with a 422 (confirmed 2026-07-19). Set "
                "CB_SEEDREAM_T2I_ENDPOINT to a real fal.ai text-to-image model id, or supply a "
                "reference image, before generating.")
        endpoint = SEEDREAM_T2I_ENDPOINT
        args = {"prompt": prompt, "image_size": image_size, "aspect_ratio": aspect}
    result = _fal_subscribe(endpoint, arguments=args, with_logs=False)
    url = None
    if result.get("images"):
        url = result["images"][0].get("url")
    elif result.get("image"):
        url = result["image"].get("url")
    if not url:
        raise SystemExit(f"Seedream returned no image url: {json.dumps(result)[:900]}")
    img = _rget(url, timeout=120)
    outp = MEDIA / out
    outp.write_bytes(img.content)
    cb_costs.log_spend("keyframe_image", cb_costs.estimate_image_cost(provider="seedream5pro"),
                        out=out, meta={"model": endpoint, "num_refs": len(ref_urls)})
    cb_costs.write_gen_sidecar(outp, op="keyframe_image", model=endpoint, aspect=aspect,
                                num_image_refs=len(ref_urls))
    return str(outp)

def _generate_image_nanobanana(prompt, refs=None, aspect="16:9", out="keyframe.png",
                   model=IMAGE_MODEL, image_size="2K"):  # Nano Banana 2 (latest) — 2K + best ref-hold; CB_IMAGE_MODEL overrides
    _need(GEMINI_KEY, "GEMINI_API_KEY")
    parts = [{"text": prompt}]
    for r in (refs or []):
        mime, data = _b64(r)
        parts.append({"inline_data": {"mime_type": mime, "data": data}})
    # imageSize lifts the render off the ~1K default (1376x768) to 2K — the single biggest sharpness lever for
    # feature-grade keyframes. Retries aspect-only if the model rejects the field.
    img_cfg = {"aspectRatio": aspect}
    if image_size:
        img_cfg["imageSize"] = image_size
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": img_cfg,
        },
    }
    url = f"{GLA}/v1beta/models/{model}:generateContent"
    def _post(b):
        return requests.post(url, headers={"x-goog-api-key": GEMINI_KEY,
                                           "Content-Type": "application/json"},
                             json=b, timeout=300)
    resp = _post(body)
    if resp.status_code == 400 and image_size and "imageSize" in resp.text:
        # model doesn't accept imageSize on this tier — retry aspect-only so we still get a frame
        print(f"  (imageSize '{image_size}' rejected — retrying at default resolution)")
        body["generationConfig"]["imageConfig"] = {"aspectRatio": aspect}
        resp = _post(body)
    # FIXED 2026-07-12 (full-codebase audit continued): this used to hand-roll its own 429/500/503 backoff
    # loop (8/16/32/60/60s, no jitter) — a second, already-drifted retry policy for the exact transient-failure
    # class this file's own shared _retry()/_retryable() (lines 85-94) already exists to handle, and that
    # every other call in this file (_rpost/_rget/_fal_upload/_fal_subscribe) already uses (cb_qa.vision_verdict
    # independently reimplements a THIRD copy of the same policy for the identical failure class). Now routed
    # through the shared _retry — only the bespoke "model rejects the imageSize field outright" 400 branch
    # above stays special-cased, since that's a real request-SHAPE correction (inspecting resp.text to mutate
    # the body before re-firing), not a transient-failure retry; _retry's own 4xx-vs-5xx/429 classifier already
    # treats a persistent 400 as non-retryable and raises immediately, same as this bespoke branch handles it
    # once, up front.
    if resp.status_code in _RETRY_STATUS:
        try:
            resp = _retry(lambda: _checked(_post(body)), what="Image API (nanobanana)")
        except requests.exceptions.HTTPError as e:
            resp = e.response   # retries exhausted — fall through to the same SystemExit below, unchanged message
    if resp.status_code != 200:
        raise SystemExit(f"Image API {resp.status_code}: {resp.text[:900]}")
    rj = resp.json()
    if not rj.get("candidates"):
        raise SystemExit(f"Image API returned no candidates (likely a safety block): {json.dumps(rj)[:900]}")
    for part in rj["candidates"][0]["content"]["parts"]:
        blob = part.get("inline_data") or part.get("inlineData")
        if blob and blob.get("data"):
            outp = MEDIA / out
            outp.write_bytes(base64.b64decode(blob["data"]))
            cb_costs.log_spend("keyframe_image", cb_costs.estimate_image_cost(provider="nanobanana2"), out=out, meta={"model": model})
            cb_costs.write_gen_sidecar(outp, op="keyframe_image", model=model, aspect=aspect, image_size=image_size)
            return str(outp)
    raise SystemExit("No image returned. Response: " + json.dumps(rj)[:500])

# ── Veo 3.1 — image-to-video (Camera) ────────────────────────────────────────
def generate_video(prompt, keyframe, aspect="16:9", resolution="720p", out="clip.mp4", production_route=None):
    _require_production_route(production_route, "generate_video")
    _need(GEMINI_KEY, "GEMINI_API_KEY")
    mime, data = _b64(keyframe)
    body = {
        "instances": [{"prompt": prompt,
                       "image": {"bytesBase64Encoded": data, "mimeType": mime}}],
        "parameters": {"aspectRatio": aspect, "resolution": resolution},
    }
    base = f"{GLA}/v1beta/models/veo-3.1-generate-preview"
    h = {"x-goog-api-key": GEMINI_KEY, "Content-Type": "application/json"}
    op = _rpost(f"{base}:predictLongRunning", headers=h, json=body, timeout=120)
    if op.status_code != 200:
        raise SystemExit(f"Veo submit {op.status_code}: {op.text[:900]}")
    name = op.json()["name"]
    print(f"  video op: {name} — polling…")
    while True:
        time.sleep(10)
        st = _rget(f"{GLA}/v1beta/{name}", headers=h, timeout=60).json()
        if st.get("done"):
            break
        print("   …still rendering")
    if st.get("error"):
        raise SystemExit(f"Veo operation failed: {json.dumps(st['error'])[:900]}")
    uri = st["response"]["generateVideoResponse"]["generatedSamples"][0]["video"]["uri"]
    vid = _rget(uri, headers={"x-goog-api-key": GEMINI_KEY}, timeout=300)
    vid.raise_for_status()
    outp = MEDIA / out
    outp.write_bytes(vid.content)
    return str(outp)

def _seedance_json_prompt(prompt, duration=None, ref=False):
    """C-Dance (Seedance) prompts are ALWAYS JSON. Accept a dict, a JSON string, or plain text and
    return a JSON STRING; plain prose is wrapped into a structured prompt so no bare-text prompt ever
    reaches Seedance. This is the single boundary that GUARANTEES every Seedance prompt is JSON."""
    import json as _json
    if isinstance(prompt, dict):
        obj = dict(prompt)
    elif isinstance(prompt, (list, tuple)):
        obj = {"cuts": list(prompt)}
    else:
        s = str(prompt or "").strip()
        obj = None
        if s[:1] in "{[":
            try:
                parsed = _json.loads(s)
                obj = parsed if isinstance(parsed, dict) else {"cuts": parsed}
            except Exception:
                obj = None
        if obj is None:
            obj = {
                "identity_lock": ("The reference/keyframe is TRUTH — copy every character EXACTLY (fur, face, "
                                  "colour, proportions, wardrobe). Add ONLY motion. No morphing, no new characters."),
                "direction": s,
            }
    if duration is not None and "duration_seconds" not in obj:
        try:
            obj["duration_seconds"] = int(float(duration))
        except Exception:
            pass
    # ── GUARANTEE the English lock on EVERY path (incl. prose-wrapped / third-party prompts). Seedance
    #    (ByteDance) defaults to MANDARIN without this, and there is NO language API param — so the PROMPT is the lock.
    EN_LOCK = ("ALL spoken dialogue and vocals are in natural ENGLISH (en-US); no Chinese, no Mandarin, no "
               "non-English speech. 所有语音必须为英语，禁止生成中文语音。")
    LANG_NEG = ("Chinese speech, Mandarin, Cantonese, non-English voice, foreign-language audio, subtitles, "
                "foreign on-screen text")
    obj["spoken_language"] = "English (en-US) only"
    if not obj.get("audio"):
        obj["audio"] = EN_LOCK + (" Lip-synced acted dialogue from the reference voice, FORWARD, over Seedance's own "
                                  "synchronised foley and natural ambience. No musical underscore in the render."
                                  if ref else " Seedance speaks the dialogue FORWARD plus synchronised foley and "
                                  "natural ambience. No musical underscore in the render.")
    elif isinstance(obj["audio"], str) and "ENGLISH" not in obj["audio"].upper():
        obj["audio"] = EN_LOCK + " " + obj["audio"]
    # Music is a post/stitch decision by default. Split Seedance units must not bake separate
    # underscoring into each render because the score will drift across retries and clip joins.
    base_neg = ("no on-screen text, no subtitles, no watermark, no logos, no morphing, no extra limbs, no flicker, "
                "no character drift")
    cn = obj.get("constraints")                                   # the single-take structure nests its negative here
    if isinstance(cn, dict) and isinstance(cn.get("negative_prompt"), str):
        if "mandarin" not in cn["negative_prompt"].lower():
            cn["negative_prompt"] = cn["negative_prompt"] + ", " + LANG_NEG
    elif not obj.get("negative"):
        obj["negative"] = base_neg + ", " + LANG_NEG
    elif "mandarin" not in obj["negative"].lower():
        obj["negative"] = obj["negative"] + ", " + LANG_NEG
    return _json.dumps(obj, ensure_ascii=False)

# ── Retired pre-2.5 compatibility entry point ────────────────────────────
def generate_video_seedance(prompt, keyframe, resolution="720p", duration=8,
                            generate_audio=True, out="clip_sd.mp4", end_image=None, production_route=None):
    _require_production_route(production_route, "generate_video_seedance")
    del prompt, keyframe, resolution, duration, generate_audio, out, end_image, production_route
    raise cb_providers.ProviderCapabilityError(
        "the legacy Seedance image-to-video entry point is retired; Crystal Bears is "
        "Seedance 2.5-only and no provider was contacted")

# ── ElevenLabs — TTS (V3 master) + Voice Changer (S2S) ───────────────────────
def generate_video_seedance_ref(prompt, image_urls, audio_urls=None, video_urls=None, resolution="720p",
                                duration="auto", out="clip_ref.mp4", fast=False, raw_prompt=False,
                                production_route=None, model_id=None,
                                comparison_run_id=None):
    _require_production_route(production_route, "generate_video_seedance_ref")
    """Seedance reference-to-video through the exact selected capability-gated transport.

    Feed reference image(s) plus the approved voice audio; the character lip-syncs to that
    audio. Reference assets in the prompt as @Image1/@Audio1. ``model_id`` is supplied from the
    sealed spend envelope so a configuration change between disclosure and firing cannot swap
    provider or model. ``comparison_run_id`` is accepted only for the explicitly disclosed
    fal 2.0 comparison inside cb_render's ordinary approval and candidate path.
    raw_prompt=True sends the prompt STRING verbatim (the DEFINITIVE bible prose already carries REFERENCE LAW / AUDIO /
    NEGATIVES — no JSON envelope, so nothing can contradict it). Otherwise the legacy path wraps prose into JSON.
    video_urls: RETIRED (found still describing this as a live, "additive" mechanism in the 2026-07-08
    contradiction sweep — every sibling module in this dependency chain, cb_beats.py/cb_qa.py/cb_golden.py/
    cb_segprompt.py, already carries its own 2026-07-07 retirement note; this docstring was the one gap the
    sweep never reached). @Video1 (rule 26) was built 2026-07-04 then explicitly retired 2026-07-07 (rule
    51 — Julian, watching real footage: "the video I don't like it either, I think it confuses things").
    No current call site ever passes a real value — cb_beats.py passes video_urls=None explicitly;
    cb_retake.py omits the argument entirely. The parameter stays in the signature (never removed, so a
    stale caller fails loud rather than with a silent TypeError) but must never be populated again without
    a fresh ruling."""
    if isinstance(image_urls, str):
        image_urls = [image_urls]
    else:
        image_urls = list(image_urls or [])
    if isinstance(audio_urls, str):
        audio_urls = [audio_urls]
    else:
        audio_urls = list(audio_urls or [])
    if isinstance(video_urls, str):
        video_urls = [video_urls]
    else:
        video_urls = list(video_urls or [])
    if video_urls:
        raise cb_providers.ProviderCapabilityError(
            "video references are retired from the approved Crystal Bears route; "
            "nothing was uploaded and no provider was contacted")
    contract_builder = (cb_providers.comparison_request_contract
                        if comparison_run_id else cb_providers.request_contract)
    contract_kwargs = {
        "fast": fast, "duration": duration, "resolution": resolution,
        "image_count": len(image_urls), "audio_count": len(audio_urls),
        "video_count": 0, "model_id": model_id,
    }
    if comparison_run_id:
        contract_kwargs["comparison_run_id"] = comparison_run_id
    contract = contract_builder(**contract_kwargs)
    _pr = (str(prompt) if raw_prompt or contract["transport"] == "byteplus-async" else
           _seedance_json_prompt(
               prompt, duration=(None if str(duration) == "auto" else duration), ref=True))

    if contract["transport"] == "byteplus-async":
        outp, task_id, task = _byteplus_generate_video(
            contract, _pr, image_urls, audio_urls, resolution, duration, out)
        seconds = float(duration)
        cb_costs.log_spend(
            "seedance_ref2vid",
            cb_costs.estimate_video_cost(contract["costRateKey"], seconds),
            out=out,
            meta={"resolution": resolution, "fast": False, "seconds": seconds,
                  "provider": "byteplus"})
        cb_costs.write_gen_sidecar(
            outp, op="seedance_ref2vid", endpoint=contract["endpoint"],
            providerModelId=contract["providerModelId"], modelVersion=contract["modelVersion"],
            transport=contract["transport"], providerTaskId=task_id,
            resolution=resolution, duration=str(duration), seconds=seconds, fast=False,
            num_image_refs=len(image_urls), num_audio_refs=len(audio_urls),
            returnedDuration=(task or {}).get("duration"),
            completionTokens=((task or {}).get("usage") or {}).get("completion_tokens"))
        return str(outp)

    if contract["transport"] != "fal-subscribe":
        raise cb_providers.ProviderCapabilityError(
            f"unsupported video transport: {contract['transport']}")
    _need(FAL_KEY, "FAL_KEY")
    os.environ["FAL_KEY"] = FAL_KEY
    import fal_client
    args = {
        "prompt": _pr,
        "image_urls": [_fal_asset_url(p) for p in image_urls],
        "resolution": resolution,
        "duration": str(duration),
        "aspect_ratio": "16:9",
        # generate_audio ON: Seedance carries the supplied @Audio1 dialogue timing plus synchronized foley/ambience.
        # Music is not auto-requested here; scene-level score is generated/selected in post after approved split
        # units are stitched, unless a deliberately approved single-shot prompt explicitly asks for native music.
        "generate_audio": True,
    }
    # Seedance 2.0 exposed bitrate_mode; the live 2.5 schema does not. Keep the
    # comparison request byte-compatible without sending an invalid field to 2.5.
    if contract["modelVersion"] == "2.0":
        args["bitrate_mode"] = "high"
    if audio_urls:
        args["audio_urls"] = [_fal_asset_url(p) for p in audio_urls]
    endpoint = contract["endpoint"]
    print(f"  seedance ref2vid ({endpoint}): rendering…")
    result = _fal_subscribe(endpoint, arguments=args, with_logs=False)
    url = (result.get("video") or {}).get("url")
    if not url:
        raise SystemExit(f"Seedance ref2vid returned no video url: {str(result)[:400]}")
    vid = _rget(url, timeout=300)
    outp = MEDIA / out; outp.write_bytes(vid.content)
    _secs = 15 if str(duration) == "auto" else float(duration)
    cb_costs.log_spend("seedance_ref2vid", cb_costs.estimate_video_cost(
        contract["costRateKey"], _secs),
        out=out, meta={"resolution": resolution, "fast": fast, "seconds": _secs})
    cb_costs.write_gen_sidecar(outp, op="seedance_ref2vid", endpoint=endpoint,
                                providerModelId=contract["providerModelId"],
                                modelVersion=contract["modelVersion"],
                                transport=contract["transport"], resolution=resolution,
                                duration=str(duration), seconds=_secs, fast=fast,
                                aspectRatio="16:9",
                                bitrateMode=("high" if contract["modelVersion"] == "2.0" else None),
                                comparisonRunId=contract.get("comparisonRunId"),
                                num_image_refs=len(image_urls), num_audio_refs=len(audio_urls))
    return str(outp)

def lipsync(video, audio, out="lipsync.mp4", model="fal-ai/latentsync", production_route=None):
    _require_production_route(production_route, "lipsync")
    """Drive a clip's mouth to a provided audio track (V3 acted VO) — solves timing.
    model: 'fal-ai/latentsync' (ByteDance, cheap) or 'fal-ai/sync-lipsync/v2/pro' (premium)."""
    _need(FAL_KEY, "FAL_KEY")
    os.environ["FAL_KEY"] = FAL_KEY
    import fal_client
    v = _fal_upload(str(pathlib.Path(video)))
    a = _fal_upload(str(pathlib.Path(audio)))
    print(f"  lipsync ({model}): rendering…")
    result = _fal_subscribe(model, arguments={"video_url": v, "audio_url": a}, with_logs=False)
    # FIXED 2026-07-12 (full-codebase audit continued): this indexed result["video"]["url"] directly, unlike
    # every sibling video-generation function in this file (generate_video_seedance, generate_video_seedance_ref,
    # _generate_image_seedream), which all guard against a missing/error-shaped fal response — a fal error shape
    # (e.g. {"error": ...}, no "video" key) would raise a bare, undiagnostic KeyError here instead of a clear
    # message naming what actually came back. Matched to the sibling pattern.
    url = (result.get("video") or {}).get("url")
    if not url:
        raise SystemExit(f"lipsync returned no video url: {str(result)[:400]}")
    vid = _rget(url, timeout=300)
    outp = MEDIA / out; outp.write_bytes(vid.content); return str(outp)

def eleven_tts(text, voice_id, model_id="eleven_v3", out="vo.mp3",
               stability=0.35, similarity_boost=0.9, style=0.0, production_route=None):
    _require_production_route(production_route, "eleven_tts")
    """V3 TTS with the canonical acting settings. stability MUST stay in the ~0.25-0.40 band — above ~0.40
    the [bracket] audio tags STOP FIRING and the read goes flat (CRYSTAL_BEARS_LOCKED_CANON.md:144-158).
    The tag sets the colour; the TEXT does the acting; 1-2 tags per segment. Never use_speaker_boost in v3."""
    _need_eleven_key()
    url = f"{XI}/v1/text-to-speech/{voice_id}"
    r = _rpost(url, headers={"xi-api-key": ELEVEN_KEY, "accept": "audio/mpeg",
                                    "Content-Type": "application/json"},
                      json={"text": text, "model_id": model_id,
                            "voice_settings": {"stability": stability,
                                               "similarity_boost": similarity_boost,
                                               "style": style}}, timeout=120)
    r.raise_for_status()
    outp = MEDIA / out; outp.write_bytes(r.content)
    cb_costs.log_spend("elevenlabs_tts", cb_costs.estimate_tts_cost(text), out=out, meta={"model": model_id})
    cb_costs.write_gen_sidecar(outp, op="elevenlabs_tts", model=model_id, voice_id=voice_id,
                                stability=stability, chars=len(text or ""))
    return str(outp)

def _ffprobe_duration(path):
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            check=True, text=True, capture_output=True)
        return max(0.0, float((result.stdout or "0").strip() or 0))
    except Exception:
        return 0.0


def _concat_audio_parts(parts, outp):
    if not parts:
        raise RuntimeError("ElevenLabs fallback produced no audio parts")
    if len(parts) == 1:
        outp.write_bytes(pathlib.Path(parts[0]).read_bytes())
        return
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        concat_file = pathlib.Path(f.name)
        for part in parts:
            safe = str(pathlib.Path(part).resolve()).replace("'", "'\\''")
            f.write(f"file '{safe}'\n")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
             "-f", "concat", "-safe", "0", "-i", str(concat_file),
             "-c", "copy", str(outp)],
            check=True, capture_output=True)
    finally:
        try:
            concat_file.unlink()
        except OSError:
            pass


def _eleven_dialogue_tts_fallback(inputs, out, model_id, generation_kind, error_text):
    """Operational fallback for production: if Text-to-Dialogue refuses, still create
    a usable line-ordered voice take. This is not the preferred performance route, but it
    prevents the Studio from dead-ending on a provider validation change."""
    parts = []
    segments = []
    cursor = 0.0
    total_chars = 0
    with tempfile.TemporaryDirectory(prefix="cb-eleven-fallback-") as tmp:
        tmp_path = pathlib.Path(tmp)
        for idx, item in enumerate(inputs or []):
            text = str(item.get("text") or "").strip()
            voice_id = item.get("voice_id")
            if not text or not voice_id:
                raise RuntimeError("ElevenLabs fallback requires text and voice_id for every line")
            total_chars += len(text)
            r = _rpost(
                f"{XI}/v1/text-to-speech/{voice_id}",
                headers={"xi-api-key": ELEVEN_KEY, "accept": "audio/mpeg",
                         "Content-Type": "application/json"},
                json={"text": text, "model_id": model_id,
                      "voice_settings": {"stability": 0.35, "similarity_boost": 0.75,
                                         "style": 0.25}},
                timeout=120)
            part = tmp_path / f"line_{idx:02d}.mp3"
            part.write_bytes(r.content)
            duration = _ffprobe_duration(part)
            segments.append({
                "voiceId": voice_id,
                "dialogueInputIndex": idx,
                "startTimeSec": cursor,
                "endTimeSec": cursor + duration,
                "characterStartIndex": 0,
                "characterEndIndex": len(text),
            })
            cursor += duration
            parts.append(part)
        outp = MEDIA / out
        outp.parent.mkdir(parents=True, exist_ok=True)
        _concat_audio_parts(parts, outp)
    timing_path = pathlib.Path(str(outp) + ".dialogue.json")
    timing_path.write_text(
        json.dumps({
            "schemaVersion": 1,
            "provider": "elevenlabs",
            "endpoint": "/v1/text-to-speech fallback after text-to-dialogue refusal",
            "model": model_id,
            "audioPath": str(outp.resolve()),
            "audioSha256": __import__("hashlib").sha256(outp.read_bytes()).hexdigest(),
            "inputCount": len(inputs or []),
            "voiceSegments": segments,
            "fallback": True,
            "fallbackReason": str(error_text)[:800],
        }, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    _billing = cb_costs.dialogue_billing(inputs, model_id=model_id,
                                          generation_kind=generation_kind)
    _billing["voices"] = len(inputs or [])
    _billing["fallback"] = "text-to-speech"
    cb_costs.log_spend("elevenlabs_dialogue_fallback", _billing["estimatedCostUsdExTax"],
                        out=out, meta=_billing)
    cb_costs.write_gen_sidecar(
        outp, op="elevenlabs_dialogue_fallback", model=model_id, stability=0.35,
        chars=total_chars, voices=len(inputs or []), billing=_billing,
        timestampEndpoint=False, dialogueTimingPath=str(timing_path),
        fallbackReason=str(error_text)[:800],
    )
    return str(outp)


def eleven_dialogue(inputs, out="vo.mp3", model_id="eleven_v3", stability=0.30,
                    generation_kind="generation", production_route=None):
    _require_production_route(production_route, "eleven_dialogue")
    """V3 TEXT-TO-DIALOGUE — the OPTIMUM for character acting. One request weaves the WHOLE exchange TOGETHER, in
    context: turn-taking, reaction timing, and prosody matched ACROSS speakers, each turn in its own voice, taking
    cues from the [audio tags]. This beats synthesising each line in isolation (a 2-word line alone reads flat — the
    v3 guide wants context, not one-liners). `inputs` = ordered [{"text","voice_id"}] (<=2000 chars total, <=10
    voices). Lower stability = broader emotional range (0.30 = the expressive 'Creative' zone; never use_speaker_boost)."""
    _need_eleven_key()
    try:
        r = _rpost(f"{XI}/v1/text-to-dialogue/with-timestamps",
                   headers={"xi-api-key": ELEVEN_KEY, "Content-Type": "application/json"},
                   json={"inputs": inputs, "model_id": model_id, "settings": {"stability": stability},
                         "apply_text_normalization": "auto"}, timeout=180)
    except requests.HTTPError as exc:
        if os.environ.get("CB_ELEVEN_DIALOGUE_TTS_FALLBACK", "1") != "0":
            return _eleven_dialogue_tts_fallback(inputs, out, model_id, generation_kind, exc)
        raise
    r.raise_for_status()
    try:
        payload = r.json()
        audio = base64.b64decode(payload["audio_base64"], validate=True)
        voice_segments = payload["voice_segments"]
    except (AttributeError, KeyError, TypeError, ValueError, base64.binascii.Error) as exc:
        raise RuntimeError(
            "ElevenLabs dialogue response omitted the timestamped audio contract"
        ) from exc
    expected_indexes = set(range(len(inputs or [])))
    try:
        returned_indexes = {
            int(item["dialogue_input_index"]) for item in voice_segments
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("ElevenLabs returned malformed dialogue timestamps") from exc
    if not audio or returned_indexes != expected_indexes:
        raise RuntimeError(
            "ElevenLabs did not return timing for every submitted dialogue line"
        )
    outp = MEDIA / out
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_bytes(audio)
    timing_path = pathlib.Path(str(outp) + ".dialogue.json")
    timing_payload = {
        "schemaVersion": 1,
        "provider": "elevenlabs",
        "endpoint": "/v1/text-to-dialogue/with-timestamps",
        "model": model_id,
        "audioPath": str(outp.resolve()),
        "audioSha256": __import__("hashlib").sha256(audio).hexdigest(),
        "inputCount": len(inputs or []),
        "voiceSegments": [
            {
                "voiceId": item.get("voice_id"),
                "dialogueInputIndex": int(item["dialogue_input_index"]),
                "startTimeSec": float(item["start_time_seconds"]),
                "endTimeSec": float(item["end_time_seconds"]),
                "characterStartIndex": item.get("character_start_index"),
                "characterEndIndex": item.get("character_end_index"),
            }
            for item in voice_segments
        ],
    }
    timing_path.write_text(
        json.dumps(timing_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _chars = sum(len(str(i.get("text") or "")) for i in (inputs or []))
    _billing = cb_costs.dialogue_billing(inputs, model_id=model_id,
                                          generation_kind=generation_kind)
    _billing["voices"] = len(inputs or [])
    cb_costs.log_spend("elevenlabs_dialogue", _billing["estimatedCostUsdExTax"], out=out,
                        meta=_billing)
    cb_costs.write_gen_sidecar(
        outp, op="elevenlabs_dialogue", model=model_id, stability=stability,
        chars=_chars, voices=len(inputs or []), billing=_billing,
        timestampEndpoint=True, dialogueTimingPath=str(timing_path),
    )
    return str(outp)

def eleven_music(prompt, length_ms=None, out="music.mp3", production_route=None):
    _require_production_route(production_route, "eleven_music")
    """ElevenLabs Music — generate an INSTRUMENTAL underscore bed (no vocals) that sits UNDER the dialogue
    (cb_post ducks it). length_ms ~ the scene's picture duration; if None the model picks a length from the prompt.
    Returns the mp3 path. If the Music API moves, THIS is the single place to update — endpoint/params verified
    against the current ElevenLabs Music docs (POST /v1/music; body: prompt, music_length_ms 3000–600000,
    force_instrumental). force_instrumental=True guarantees no sung vocals leak into the bed."""
    _need_eleven_key()
    body = {"prompt": prompt, "force_instrumental": True}
    if length_ms:
        body["music_length_ms"] = max(3000, min(int(length_ms), 600000))   # clamp 3s … 10 min (API range)
    r = _rpost(f"{XI}/v1/music",
                      headers={"xi-api-key": ELEVEN_KEY, "accept": "audio/mpeg", "Content-Type": "application/json"},
                      json=body, timeout=300)
    if r.status_code != 200:
        # RuntimeError (an Exception subclass) so cb_post's `except Exception` skips the bed gracefully;
        # SystemExit would escape that catch and kill the whole post run.
        raise RuntimeError(f"Music API {r.status_code}: {r.text[:300]}")
    outp = MEDIA / out; outp.write_bytes(r.content)
    cb_costs.log_spend("elevenlabs_music", cb_costs.estimate_music_cost(length_ms), out=out)
    cb_costs.write_gen_sidecar(outp, op="elevenlabs_music", length_ms=length_ms)
    return str(outp)

def voice_change(audio, voice_id, model_id="eleven_multilingual_sts_v2", out="swapped.mp3",
                 remove_noise=True, similarity=0.95, stability=0.4, style=0.0):
    """RETIRED (2026-07-08 software-wide fix batch): this IS the "post voice swap" mechanism CLAUDE.md rules
    4/29 forbid by name — "no native-voice fallback... no post voice swap... cb_post has no swap function by
    design; do not add one, to a two-step pipeline or any other." Zero production callers (confirmed — only
    this module's own CLI "swap" subcommand reached it, now guarded below too); kept for the record, raises
    loud rather than deleted outright, matching cb_prompts.py's identical RETIRED precedent for its own dead
    Law-6-violating builders. @Audio1 is the sole vocal source, generated once, never re-voiced afterward."""
    raise RuntimeError("cb_gen.voice_change is RETIRED — no post voice swap, ever (CLAUDE.md rules 4/29). The "
                        "voice is generated once (cb_voice.build_dialogue_track) and lip-synced from that same "
                        "take; there is no code path that re-voices it afterward.")
    import json as _json
    _need(ELEVEN_KEY, "ELEVENLABS_API_KEY")
    url = f"{XI}/v1/speech-to-speech/{voice_id}"
    data = {
        "model_id": model_id,
        "remove_background_noise": "true" if remove_noise else "false",
        "voice_settings": _json.dumps({
            "stability": stability, "similarity_boost": similarity, "style": style,
            "use_speaker_boost": True,
        }),
    }
    with open(audio, "rb") as f:
        r = _rpost(url, headers={"xi-api-key": ELEVEN_KEY},
                          files={"audio": f}, data=data, timeout=300)
    r.raise_for_status()
    outp = MEDIA / out; outp.write_bytes(r.content); return str(outp)

def eleven_sfx(text, duration=None, out="sfx.mp3", loop=False, production_route=None):
    _require_production_route(production_route, "eleven_sfx")
    """Text -> sound effect / ambience bed."""
    _need_eleven_key()
    body = {"text": text, "loop": loop}
    if duration:
        body["duration_seconds"] = duration
    r = _rpost(f"{XI}/v1/sound-generation",
                      headers={"xi-api-key": ELEVEN_KEY, "accept": "audio/mpeg",
                               "Content-Type": "application/json"},
                      json=body, timeout=120)
    if r.status_code != 200:
        raise SystemExit(f"SFX API {r.status_code}: {r.text[:300]}")
    outp = MEDIA / out; outp.write_bytes(r.content)
    cb_costs.log_spend("elevenlabs_sfx", cb_costs.RATES["elevenlabs_sfx_flat"][0], out=out)
    cb_costs.write_gen_sidecar(outp, op="elevenlabs_sfx", duration=duration, loop=loop)
    return str(outp)

def list_voices():
    _need_eleven_key()
    r = requests.get(f"{XI}/v1/voices", headers={"xi-api-key": ELEVEN_KEY}, timeout=30)
    r.raise_for_status()
    return [(v["voice_id"], v["name"]) for v in r.json().get("voices", [])]

def keycheck():
    """Validate both keys cheaply, without printing them."""
    # ElevenLabs
    try:
        n = len(list_voices())
        print(f"  ElevenLabs: OK ({n} voices on the account)")
    except Exception as e:
        print(f"  ElevenLabs: FAIL — {getattr(e,'response',None) and e.response.status_code or e}")
    # Gemini (list models)
    try:
        _need(GEMINI_KEY, "GEMINI_API_KEY")
        r = requests.get(f"{GLA}/v1beta/models", headers={"x-goog-api-key": GEMINI_KEY}, timeout=30)
        if r.status_code == 200:
            ids = [m["name"].split("/")[-1] for m in r.json().get("models", [])]
            has_img = any("flash-image" in i for i in ids)
            has_veo = any("veo" in i for i in ids)
            print(f"  Gemini: OK ({len(ids)} models; nano-banana={'yes' if has_img else 'no'}, veo={'yes' if has_veo else 'no'})")
        else:
            print(f"  Gemini: FAIL — HTTP {r.status_code}: {r.text[:160]}")
    except Exception as e:
        print(f"  Gemini: FAIL — {e}")

# THE CLI GENERATION COMMANDS ARE GONE (Julian's destructive cutover, 2026-07-16): every
# generation call enters through cb_render's authoritative route — disclosure -> sealed
# envelope -> spend token -> candidate batch. This module is a PROVIDER ADAPTER LIBRARY only.
if __name__ == "__main__":
    print("cb_gen.py is a provider adapter library — CLI generation was removed at the "
          "2026-07-16 cutover. Use: python3 cb_render.py (the single authoritative route).")
    raise SystemExit(1)
