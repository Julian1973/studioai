#!/usr/bin/env python3
"""
Crystal Bears — local generation module (the app's provider layer).

Wires the crew's prompts to the real APIs, locally (no Replit):
  - generate_image()  -> Nano Banana 2 (gemini-3.1-flash-image) [DP keyframes]
  - generate_video()  -> Veo 3.1 (veo-3.1-generate-preview)     [Camera i2v]
  - eleven_tts()      -> ElevenLabs TTS (V3 acted masters)
  - voice_change()    -> ElevenLabs speech-to-speech (the lip-sync voice swap)
  - list_voices()/keycheck -> cheap validity checks

Keys come from cb-gen/.env (gitignored): GEMINI_API_KEY, ELEVENLABS_API_KEY.
Endpoints verified against ai.google.dev + elevenlabs.io docs (June 2026).
"""
import os, sys, json, time, base64, mimetypes, argparse, pathlib
import requests

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
IMAGE_MODEL = os.environ.get("CB_IMAGE_MODEL", "gemini-3.1-flash-image")  # NB2 — the A/B winner for the cascade

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
ELEVEN_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
GLA = "https://generativelanguage.googleapis.com"
XI = "https://api.elevenlabs.io"
FAL_KEY = os.environ.get("FAL_KEY", "")
FAL = "https://queue.fal.run"

def _b64(path):
    data = pathlib.Path(path).read_bytes()
    mime = mimetypes.guess_type(path)[0] or "image/png"
    return mime, base64.b64encode(data).decode()

def _need(key, name):
    if not key:
        raise SystemExit(f"{name} not set — add it to cb-gen/.env")

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
    r.raise_for_status(); return r
def _rpost(url, **kw):
    kw.setdefault("timeout", 120)
    return _retry(lambda: _checked(requests.post(url, **kw)), what="POST " + str(url).rsplit("/", 1)[-1][:24])
def _rget(url, **kw):
    kw.setdefault("timeout", 120)
    return _retry(lambda: _checked(requests.get(url, **kw)), what="GET " + str(url).rsplit("/", 1)[-1][:24])
def _fal_upload(path):
    import fal_client
    return _retry(lambda: fal_client.upload_file(path), what="fal upload")
def _fal_subscribe(endpoint, arguments=None, with_logs=False):
    import fal_client
    return _retry(lambda: fal_client.subscribe(endpoint, arguments=arguments, with_logs=with_logs),
                  what="fal:" + str(endpoint).rsplit("/", 1)[-1])

# ── Last-frame extractor (first/last-frame chaining for continuous flow) ──────
def last_frame(clip, out="lastframe.png"):
    import subprocess
    subprocess.run(["ffmpeg", "-y", "-sseof", "-0.1", "-i", clip,
                    "-update", "1", "-frames:v", "1", out],
                   check=True, capture_output=True)
    return out

# ── Nano Banana — image (DP keyframes) ───────────────────────────────────────
def generate_image(prompt, refs=None, aspect="16:9", out="keyframe.png",
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
    # TRANSIENT-ERROR RETRY: the Pro image model can 429/500/503 under load — back off and retry, never crash the
    # whole chained build on a temporary blip.
    for attempt in range(5):
        if resp.status_code not in (429, 500, 503):
            break
        wait = min(60, 8 * (2 ** attempt))   # 8, 16, 32, 60, 60s
        print(f"  Image API {resp.status_code} (transient/high demand) — retry {attempt + 1}/5 in {wait}s...", flush=True)
        time.sleep(wait)
        resp = _post(body)
    if resp.status_code != 200:
        raise SystemExit(f"Image API {resp.status_code}: {resp.text[:900]}")
    for part in resp.json()["candidates"][0]["content"]["parts"]:
        blob = part.get("inline_data") or part.get("inlineData")
        if blob and blob.get("data"):
            outp = MEDIA / out
            outp.write_bytes(base64.b64decode(blob["data"]))
            return str(outp)
    raise SystemExit("No image returned. Response: " + json.dumps(resp.json())[:500])

# ── Veo 3.1 — image-to-video (Camera) ────────────────────────────────────────
def generate_video(prompt, keyframe, aspect="16:9", resolution="720p", out="clip.mp4"):
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
    # ── GUARANTEE the English lock + a music ask on EVERY path (incl. prose-wrapped / third-party prompts). Seedance
    #    (ByteDance) defaults to MANDARIN without this, and there is NO language API param — so the PROMPT is the lock.
    EN_LOCK = ("ALL spoken dialogue and vocals are in natural ENGLISH (en-US); no Chinese, no Mandarin, no "
               "non-English speech. 所有语音必须为英语，禁止生成中文语音。")
    LANG_NEG = ("Chinese speech, Mandarin, Cantonese, non-English voice, foreign-language audio, subtitles, "
                "foreign on-screen text")
    obj["spoken_language"] = "English (en-US) only"
    if not obj.get("audio"):
        obj["audio"] = EN_LOCK + (" Lip-synced acted dialogue from the reference voice, FORWARD, over Seedance's own "
                                  "synchronised SFX, with a musical underscore kept low underneath."
                                  if ref else " Seedance speaks the dialogue FORWARD plus synchronised SFX, with a "
                                  "musical underscore kept low underneath.")
    elif isinstance(obj["audio"], str) and "ENGLISH" not in obj["audio"].upper():
        obj["audio"] = EN_LOCK + " " + obj["audio"]
    # the single-take structure (visual_prompt/timeline/constraints) scores music in POST — don't auto-inject a music key
    if "visual_prompt" not in obj:
        obj.setdefault("music", ("A musical underscore plays throughout the take, low under dialogue, swelling on the "
                                 "action and resolving on the last frame. No sung lyrics."))
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

# ── Seedance 2.0 — image-to-video via fal.ai (best motion + native lip-sync) ──
def generate_video_seedance(prompt, keyframe, resolution="720p", duration=8,
                            generate_audio=True, out="clip_sd.mp4", end_image=None):
    _need(FAL_KEY, "FAL_KEY")
    os.environ["FAL_KEY"] = FAL_KEY
    import fal_client
    args = {
        "prompt": _seedance_json_prompt(prompt, duration=duration),
        "image_url": _fal_upload(str(pathlib.Path(keyframe))),
        "resolution": resolution,
        "duration": str(duration),
        "generate_audio": generate_audio,
    }
    if end_image:
        args["end_image_url"] = _fal_upload(str(pathlib.Path(end_image)))
        print("  seedance: start→end frames, animating the action between…")
    else:
        print("  seedance: submitted, rendering…")
    result = _fal_subscribe(
        "bytedance/seedance-2.0/image-to-video", arguments=args, with_logs=False)
    url = (result.get("video") or {}).get("url")
    if not url:
        raise SystemExit(f"Seedance returned no video url: {str(result)[:400]}")
    vid = _rget(url, timeout=300)
    vid.raise_for_status()
    outp = MEDIA / out
    outp.write_bytes(vid.content)
    return str(outp)

# ── ElevenLabs — TTS (V3 master) + Voice Changer (S2S) ───────────────────────
def generate_video_seedance_ref(prompt, image_urls, audio_urls=None, resolution="720p",
                                duration="auto", out="clip_ref.mp4", fast=False, raw_prompt=False):
    """Seedance reference-to-video: feed reference image(s) + your OWN voice audio (≤15s);
    the character lip-syncs to your audio. Reference assets in the prompt as @图1/@Audio1.
    raw_prompt=True sends the prompt STRING verbatim (the DEFINITIVE bible prose already carries REFERENCE LAW / AUDIO /
    NEGATIVES — no JSON envelope, so nothing can contradict it). Otherwise the legacy path wraps prose into JSON."""
    _need(FAL_KEY, "FAL_KEY")
    os.environ["FAL_KEY"] = FAL_KEY
    import fal_client
    if isinstance(image_urls, str): image_urls = [image_urls]
    _pr = (str(prompt) if raw_prompt else
           _seedance_json_prompt(prompt, duration=(None if str(duration) == "auto" else duration), ref=True))
    args = {
        "prompt": _pr,
        "image_urls": [_fal_upload(str(pathlib.Path(p))) for p in image_urls],
        "resolution": resolution,
        "duration": str(duration),
        # generate_audio ON: Seedance natively scores music + SFX + the lip-synced @Audio1 voice in ONE pass (fal docs —
        # cost is identical). The prompt REFERENCES @Audio1 as the spoken line (it does NOT write the words), so Seedance
        # uses the supplied ElevenLabs voice AS the speech instead of generating a duplicate (the old "nailed it" double).
        "generate_audio": True,
    }
    if audio_urls:
        if isinstance(audio_urls, str): audio_urls = [audio_urls]
        args["audio_urls"] = [_fal_upload(str(pathlib.Path(p))) for p in audio_urls]
    endpoint = ("bytedance/seedance-2.0/fast/reference-to-video" if fast
                else "bytedance/seedance-2.0/reference-to-video")
    print(f"  seedance ref2vid ({endpoint}): rendering…")
    result = _fal_subscribe(endpoint, arguments=args, with_logs=False)
    vid = _rget(result["video"]["url"], timeout=300)
    outp = MEDIA / out; outp.write_bytes(vid.content); return str(outp)

def lipsync(video, audio, out="lipsync.mp4", model="fal-ai/latentsync"):
    """Drive a clip's mouth to a provided audio track (V3 acted VO) — solves timing.
    model: 'fal-ai/latentsync' (ByteDance, cheap) or 'fal-ai/sync-lipsync/v2/pro' (premium)."""
    _need(FAL_KEY, "FAL_KEY")
    os.environ["FAL_KEY"] = FAL_KEY
    import fal_client
    v = _fal_upload(str(pathlib.Path(video)))
    a = _fal_upload(str(pathlib.Path(audio)))
    print(f"  lipsync ({model}): rendering…")
    result = _fal_subscribe(model, arguments={"video_url": v, "audio_url": a}, with_logs=False)
    url = result["video"]["url"]
    vid = _rget(url, timeout=300)
    outp = MEDIA / out; outp.write_bytes(vid.content); return str(outp)

def eleven_tts(text, voice_id, model_id="eleven_v3", out="vo.mp3",
               stability=0.35, similarity_boost=0.9, style=0.0):
    """V3 TTS with the canonical acting settings. stability MUST stay in the ~0.25-0.40 band — above ~0.40
    the [bracket] audio tags STOP FIRING and the read goes flat (CRYSTAL_BEARS_LOCKED_CANON.md:144-158).
    The tag sets the colour; the TEXT does the acting; 1-2 tags per segment. Never use_speaker_boost in v3."""
    _need(ELEVEN_KEY, "ELEVENLABS_API_KEY")
    url = f"{XI}/v1/text-to-speech/{voice_id}"
    r = _rpost(url, headers={"xi-api-key": ELEVEN_KEY, "accept": "audio/mpeg",
                                    "Content-Type": "application/json"},
                      json={"text": text, "model_id": model_id,
                            "voice_settings": {"stability": stability,
                                               "similarity_boost": similarity_boost,
                                               "style": style}}, timeout=120)
    r.raise_for_status()
    outp = MEDIA / out; outp.write_bytes(r.content); return str(outp)

def eleven_dialogue(inputs, out="vo.mp3", model_id="eleven_v3", stability=0.30):
    """V3 TEXT-TO-DIALOGUE — the OPTIMUM for character acting. One request weaves the WHOLE exchange TOGETHER, in
    context: turn-taking, reaction timing, and prosody matched ACROSS speakers, each turn in its own voice, taking
    cues from the [audio tags]. This beats synthesising each line in isolation (a 2-word line alone reads flat — the
    v3 guide wants context, not one-liners). `inputs` = ordered [{"text","voice_id"}] (<=2000 chars total, <=10
    voices). Lower stability = broader emotional range (0.30 = the expressive 'Creative' zone; never use_speaker_boost)."""
    _need(ELEVEN_KEY, "ELEVENLABS_API_KEY")
    r = _rpost(f"{XI}/v1/text-to-dialogue",
               headers={"xi-api-key": ELEVEN_KEY, "accept": "audio/mpeg", "Content-Type": "application/json"},
               json={"inputs": inputs, "model_id": model_id, "settings": {"stability": stability},
                     "apply_text_normalization": "auto"}, timeout=180)
    r.raise_for_status()
    outp = MEDIA / out; outp.write_bytes(r.content); return str(outp)

def eleven_music(prompt, length_ms=None, out="music.mp3"):
    """ElevenLabs Music — generate an INSTRUMENTAL underscore bed (no vocals) that sits UNDER the dialogue
    (cb_post ducks it). length_ms ~ the scene's picture duration; if None the model picks a length from the prompt.
    Returns the mp3 path. If the Music API moves, THIS is the single place to update — endpoint/params verified
    against the current ElevenLabs Music docs (POST /v1/music; body: prompt, music_length_ms 3000–600000,
    force_instrumental). force_instrumental=True guarantees no sung vocals leak into the bed."""
    _need(ELEVEN_KEY, "ELEVENLABS_API_KEY")
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
    outp = MEDIA / out; outp.write_bytes(r.content); return str(outp)

def voice_change(audio, voice_id, model_id="eleven_multilingual_sts_v2", out="swapped.mp3",
                 remove_noise=True, similarity=0.95, stability=0.4, style=0.0):
    """Strip-and-swap: re-voice existing audio to the canonical bear voice,
    preserving timing (the lip-sync default path).
    remove_noise strips baked-in ambient so the conversion locks the target voice;
    high similarity forces the target identity."""
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

def eleven_sfx(text, duration=None, out="sfx.mp3", loop=False):
    """Text -> sound effect / ambience bed."""
    _need(ELEVEN_KEY, "ELEVENLABS_API_KEY")
    body = {"text": text, "loop": loop}
    if duration:
        body["duration_seconds"] = duration
    r = _rpost(f"{XI}/v1/sound-generation",
                      headers={"xi-api-key": ELEVEN_KEY, "accept": "audio/mpeg",
                               "Content-Type": "application/json"},
                      json=body, timeout=120)
    if r.status_code != 200:
        raise SystemExit(f"SFX API {r.status_code}: {r.text[:300]}")
    outp = MEDIA / out; outp.write_bytes(r.content); return str(outp)

def list_voices():
    _need(ELEVEN_KEY, "ELEVENLABS_API_KEY")
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

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Crystal Bears generation module")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("keycheck")
    sub.add_parser("voices")
    pi = sub.add_parser("image"); pi.add_argument("prompt"); pi.add_argument("--ref", nargs="*", default=[]); pi.add_argument("--aspect", default="16:9"); pi.add_argument("--out", default="keyframe.png")
    pv = sub.add_parser("video"); pv.add_argument("prompt"); pv.add_argument("keyframe"); pv.add_argument("--out", default="clip.mp4")
    pd = sub.add_parser("sdvideo"); pd.add_argument("prompt"); pd.add_argument("keyframe"); pd.add_argument("--end"); pd.add_argument("--res", default="720p"); pd.add_argument("--duration", type=int, default=8); pd.add_argument("--no-audio", action="store_true"); pd.add_argument("--out", default="clip_sd.mp4")
    pt = sub.add_parser("tts"); pt.add_argument("text"); pt.add_argument("voice_id"); pt.add_argument("--out", default="vo.mp3")
    ps = sub.add_parser("swap"); ps.add_argument("audio"); ps.add_argument("voice_id"); ps.add_argument("--out", default="swapped.mp3")
    px = sub.add_parser("sfx"); px.add_argument("text"); px.add_argument("--duration", type=float); px.add_argument("--loop", action="store_true"); px.add_argument("--out", default="sfx.mp3")
    pm = sub.add_parser("music"); pm.add_argument("prompt"); pm.add_argument("--ms", type=int); pm.add_argument("--out", default="music.mp3")
    pl = sub.add_parser("lastframe"); pl.add_argument("clip"); pl.add_argument("--out", default="lastframe.png")
    pls = sub.add_parser("lipsync"); pls.add_argument("video"); pls.add_argument("audio"); pls.add_argument("--model", default="fal-ai/latentsync"); pls.add_argument("--out", default="lipsync.mp4")
    prv = sub.add_parser("refvideo"); prv.add_argument("prompt"); prv.add_argument("--img", nargs="+", required=True); prv.add_argument("--audio", nargs="*", default=[]); prv.add_argument("--res", default="720p"); prv.add_argument("--duration", default="auto"); prv.add_argument("--fast", action="store_true"); prv.add_argument("--out", default="clip_ref.mp4")
    a = ap.parse_args()
    if a.cmd == "keycheck": keycheck()
    elif a.cmd == "voices":
        for vid, name in list_voices(): print(f"  {name}: {vid}")
    elif a.cmd == "image": print("✓", generate_image(a.prompt, a.ref, a.aspect, a.out))
    elif a.cmd == "video": print("✓", generate_video(a.prompt, a.keyframe, out=a.out))
    elif a.cmd == "sdvideo": print("✓", generate_video_seedance(a.prompt, a.keyframe, a.res, a.duration, not a.no_audio, a.out, end_image=a.end))
    elif a.cmd == "tts": print("✓", eleven_tts(a.text, a.voice_id, out=a.out))
    elif a.cmd == "swap": print("✓", voice_change(a.audio, a.voice_id, out=a.out))
    elif a.cmd == "sfx": print("✓", eleven_sfx(a.text, a.duration, a.out, a.loop))
    elif a.cmd == "music": print("✓", eleven_music(a.prompt, a.ms, a.out))
    elif a.cmd == "lastframe": print("✓", last_frame(a.clip, a.out))
    elif a.cmd == "lipsync": print("✓", lipsync(a.video, a.audio, a.out, a.model))
    elif a.cmd == "refvideo": print("✓", generate_video_seedance_ref(a.prompt, a.img, a.audio or None, a.res, a.duration, a.out, a.fast))
    else: ap.print_help()
