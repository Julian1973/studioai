#!/usr/bin/env python3
"""Animation Studio local server: projects, episodes, canon and media production."""
import os, re, json, http.server, pathlib, subprocess, threading, time, zipfile, signal, sys, uuid, hashlib, secrets, hmac, selectors, gc, importlib
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, quote, urlencode, urlsplit

ROOT = pathlib.Path(__file__).resolve().parent.parent   # Desktop/Ai Studio (isolated workspace)
CBGEN = ROOT / "engine"
sys.path.insert(0, str(CBGEN))   # FIXED 2026-07-17 (state-integrity checkpoint): every OTHER
# engine-touching operation runs in its own subprocess (cwd=CBGEN), which is why THAT never
# needed this — but /api/rates (and /api/learning, same bug) import an engine module directly
# in-process, which raised "No module named 'cb_costs'" until now. cb_costs.py is a pure,
# side-effect-free module at import time (constants + a path string) — safe to add once, here.
MEDIA = ROOT / "engine" / "media"
OUT = ROOT / "cb-output"
DATA = ROOT / "cb-studio" / "data"
DATA.mkdir(parents=True, exist_ok=True)
import cb_scripts
import cb_db
import cb_asset_registry
import cb_lineage
import studio_profile

def _canonical_engine_module(module_name):
    """Import the current source for an engine module from this Studio checkout."""
    expected_root = CBGEN.resolve()
    current = sys.modules.get(module_name)
    current_file = pathlib.Path(getattr(current, "__file__", "") or "").resolve() if current else None
    if current and current_file:
        try:
            if current_file.is_relative_to(expected_root):
                source_mtime = current_file.stat().st_mtime_ns
                loaded_mtime = getattr(current, "__studio_source_mtime_ns__", None)
                if loaded_mtime == source_mtime:
                    return current
                importlib.invalidate_caches()
                current = importlib.reload(current)
                current.__studio_source_mtime_ns__ = source_mtime
                return current
        except AttributeError:
            if str(current_file).startswith(str(expected_root) + os.sep):
                source_mtime = current_file.stat().st_mtime_ns
                loaded_mtime = getattr(current, "__studio_source_mtime_ns__", None)
                if loaded_mtime == source_mtime:
                    return current
                importlib.invalidate_caches()
                current = importlib.reload(current)
                current.__studio_source_mtime_ns__ = source_mtime
                return current
    if current:
        sys.modules.pop(module_name, None)
    try:
        sys.path.remove(str(CBGEN))
    except ValueError:
        pass
    sys.path.insert(0, str(CBGEN))
    current = __import__(module_name)
    current_file = pathlib.Path(current.__file__).resolve()
    current.__studio_source_mtime_ns__ = current_file.stat().st_mtime_ns
    return current

def _canonical_cb_render():
    return _canonical_engine_module("cb_render")


def _canonical_cb_state():
    return _canonical_engine_module("cb_state")

ACTIVE_SHOW = studio_profile.load_show_profile(ROOT)
ACTIVE_PROJECT_ID = ACTIVE_SHOW.profile.showId        # T44: never a hard-coded show id in this file
ASSETS = ACTIVE_SHOW.assets_root or (ROOT / "cb-seed" / "assets")   # the project's reference media root


def _paths():
    """engine/paths — the project profile is the only path authority (T44)."""
    import paths
    return paths
SHOW_PROFILE_STATUS = studio_profile.capability_report(ACTIVE_SHOW)
CANON_CONFIG = ACTIVE_SHOW.canon_paths["characters"].parent
# T43 (2026-09-01): ONE script store per project — the profile's episodes.scripts. The old
# cb-studio/data/scripts copy (which drifted from the tenant copy by two lines, T42) is gone;
# a compatibility symlink stands at its old path for one release.
SCRIPTS = ACTIVE_SHOW.scripts_path
SCRIPTS.mkdir(parents=True, exist_ok=True)
SCRIPT_STORE = cb_scripts.ScriptStore(ROOT, show_id=ACTIVE_SHOW.profile.showId)
PORT = int(os.environ.get("CB_STUDIO_PORT", "8765"))
BIND_HOST = "127.0.0.1"
PUBLIC_ORIGIN = os.environ.get("CB_STUDIO_PUBLIC_ORIGIN", "").strip().rstrip("/")
if PUBLIC_ORIGIN:
    _public_origin = urlsplit(PUBLIC_ORIGIN)
    if (
        _public_origin.scheme != "https"
        or not _public_origin.hostname
        or _public_origin.username is not None
        or _public_origin.password is not None
        or _public_origin.path not in ("", "/")
        or _public_origin.query
        or _public_origin.fragment
    ):
        raise RuntimeError(
            "CB_STUDIO_PUBLIC_ORIGIN must be a bare HTTPS origin, for example "
            "https://studio.example.com"
        )
    PUBLIC_HOST = _public_origin.hostname.lower().rstrip(".")
    PUBLIC_PORT = _public_origin.port
else:
    PUBLIC_HOST = ""
    PUBLIC_PORT = None
SERVER_KEY = f"{BIND_HOST}:{PORT}|{PUBLIC_ORIGIN or 'loopback'}"
LAUNCH_TOKEN = secrets.token_urlsafe(32)


def _load_or_create_session_token():
    """Return the durable local session secret used by browser cookies.

    A process-random token logged every open Studio tab out whenever the freshness
    guard restarted the server. Keep the secret outside source control, restrict it
    to the current user, and allow an explicit path override for isolated tests.
    """
    configured = os.environ.get("CB_STUDIO_SESSION_SECRET_FILE", "").strip()
    path = pathlib.Path(configured) if configured else OUT / "state" / ".studio_session_secret"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        token = path.read_text(encoding="utf-8").strip()
        if len(token) >= 32:
            try:
                path.chmod(0o600)
            except OSError:
                pass
            return token
    except OSError:
        pass
    token = secrets.token_urlsafe(32)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(token + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        path.chmod(0o600)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return token


SESSION_TOKEN = _load_or_create_session_token()
STUDIO_BUILD_VERSION = "scene-plate-direct-select-20260812-1"
SESSION_COOKIE = "cb_studio_session"
MAX_REQUEST_BYTES = 64 * 1024 * 1024
MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
MAX_DOCX_XML_BYTES = 12 * 1024 * 1024
MAX_IMAGE_BYTES = 25 * 1024 * 1024
MAX_IMAGE_PIXELS = 100_000_000
MAX_VIDEO_BYTES = 45 * 1024 * 1024


class RequestTooLarge(ValueError):
    pass


def _validated_content_length(headers):
    transfer = (headers.get("Transfer-Encoding") or "").strip().lower()
    if transfer and transfer != "identity":
        raise ValueError("chunked request bodies are not accepted by the local Studio")
    raw = headers.get("Content-Length")
    if raw in (None, ""):
        return 0
    try:
        size = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("Content-Length must be a non-negative integer") from exc
    if size < 0:
        raise ValueError("Content-Length must be a non-negative integer")
    if size > MAX_REQUEST_BYTES:
        raise RequestTooLarge(
            f"request body exceeds the {MAX_REQUEST_BYTES // (1024 * 1024)} MB local limit")
    return size

# ── SOFTWARE-FRESHNESS GUARD ──────────────────────────────────────────────────────────────────────────────────
# The UI is the ONLY way we fire, so the server behind it must NEVER run stale code. We fingerprint every Python
# source a fire depends on (this server + the whole engine engine — Director, prompt builder, voice, pipeline) at
# startup. If any changes on disk the server is STALE: it REFUSES to fire (so a fire can never run old code) AND it
# auto-reloads itself the moment it's idle, so the UI always has the latest software behind it without anyone
# remembering to restart. (The render itself already runs in a fresh subprocess; this closes the serve.py gap.)
def _source_fingerprint():
    # ONLY this server's own source. engine modules are reloaded fresh by each per-render SUBPROCESS, so they never
    # need a serve.py reload — watching them would needlessly re-exec and DROP the UI's open connections on every
    # engine edit ("can't reach server"). serve.py is the only long-lived code, so it's the only thing to watch.
    try: return os.path.getmtime(os.path.abspath(__file__))
    except OSError: return 0.0
_STARTED_FP = _source_fingerprint()
def _is_stale():
    return _source_fingerprint() > _STARTED_FP + 0.5      # 0.5s slop for save races
def _reexec():
    """Reload the studio process with the CURRENT code (idle auto-reload + the restart endpoint)."""
    sys.stdout.flush()
    os.execv(sys.executable, [sys.executable, os.path.abspath(__file__)] + sys.argv[1:])
def _freshness_watch():
    """Self-heal: when the source changes and NO job is running, reload with the latest code (seamless when idle).
    FIXED 2026-07-12 (full-codebase audit continued): this only ever checked PROCS (async render jobs) — several
    handlers do real, non-trivial SYNCHRONOUS work in their own request thread and were never tracked there at
    all (approve_gate/unapprove_gate/set_master_studio/clear_master_studio's blocking subprocess.run calls, every
    read-only preview endpoint, _serve_static's own chunked video/range streaming loop). os.execv() replaces the
    WHOLE process image — per POSIX every thread but the caller is killed instantly, and Python sockets are
    close-on-exec by default — so a reload mid-request silently dropped that client's connection even if a
    spawned subprocess went on to finish and write locked.json unseen. Now also waits for _INFLIGHT == 0 (see its
    definition, near PROCS below), incremented/decremented around every HTTP entry point via @_tracked."""
    while True:
        time.sleep(3)
        try:
            if _is_stale() and not PROCS and _INFLIGHT == 0:
                print("⟳ studio source changed — reloading with the latest code…", flush=True)
                _reexec()
        except Exception:
            pass

def slug(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_") or "Untitled"

def _pdf_text_has_screenplay_structure(text):
    if not isinstance(text, str) or not text.strip():
        return False
    scene_re = re.compile(
        r"^\s*(?:INT|EXT|INT/EXT|I/E)\.\s+.+?\s+\d+\s*$",
        re.IGNORECASE)
    return any(scene_re.match(line) for line in text.splitlines())

def extract_doc_text(raw, name=""):
    """Extract plain text from an uploaded script document (base64). Supports
    txt/md/fountain (direct), docx (built-in zip+xml), rtf (basic), pdf (if a lib is installed)."""
    import base64, io, html as _html
    if isinstance(raw, str) and raw.strip().startswith("data:") and "," in raw:
        raw = raw.split(",", 1)[1]
    try:
        blob = base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise ValueError("uploaded document is not valid base64") from exc
    if len(blob) > MAX_DOCUMENT_BYTES:
        raise RequestTooLarge(
            f"script document exceeds the {MAX_DOCUMENT_BYTES // (1024 * 1024)} MB limit")
    ext = (name.rsplit(".", 1)[-1].lower() if "." in name else "")
    if ext in ("txt", "md", "markdown", "fountain", "text", ""):
        return blob.decode("utf-8", "ignore")
    if ext == "docx":
        try:
            z = zipfile.ZipFile(io.BytesIO(blob))
            info = z.getinfo("word/document.xml")
            if info.file_size > MAX_DOCX_XML_BYTES:
                raise ValueError("the DOCX document XML is unreasonably large")
            xml = z.read(info).decode("utf-8", "ignore")
            xml = (xml.replace("</w:p>", "\n").replace("<w:tab/>", "\t")
                      .replace("<w:br/>", "\n").replace("<w:br></w:br>", "\n"))
            return _html.unescape(re.sub(r"<[^>]+>", "", xml)).strip()
        except Exception as e:
            return f"[could not read .docx: {e}]"
    if ext == "rtf":
        t = blob.decode("latin-1", "ignore")
        t = re.sub(r"\\par[d]?\b", "\n", t)
        t = re.sub(r"\\'[0-9a-fA-F]{2}", "", t)
        t = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", t)
        return t.replace("{", "").replace("}", "").strip()
    if ext == "pdf":
        for lib in ("pypdf", "PyPDF2"):
            try:
                mod = __import__(lib)
                r = mod.PdfReader(io.BytesIO(blob))
                if len(r.pages) > 500:
                    raise ValueError("the uploaded PDF has more than 500 pages")
                plain = "\n".join((p.extract_text() or "") for p in r.pages).strip()
                if _pdf_text_has_screenplay_structure(plain):
                    return plain
                layout_parts = []
                for p in r.pages:
                    try:
                        layout_parts.append(p.extract_text(extraction_mode="layout") or "")
                    except TypeError:
                        layout_parts = []
                        break
                layout = "\n".join(layout_parts).strip()
                if _pdf_text_has_screenplay_structure(layout):
                    return layout
                return layout or plain
            except Exception:
                continue
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(blob)) as pdf:
                if len(pdf.pages) > 500:
                    raise ValueError("the uploaded PDF has more than 500 pages")
                return "\n".join((pg.extract_text() or "") for pg in pdf.pages).strip()
        except Exception:
            return "[PDF received but no PDF text library is installed — paste the text or upload .docx/.txt instead.]"
    return blob.decode("utf-8", "ignore")


def decode_image_upload(raw):
    """Decode and verify a bounded raster upload before it reaches the media tree."""
    import base64
    import io
    from PIL import Image

    if isinstance(raw, str) and raw.strip().startswith("data:") and "," in raw:
        raw = raw.split(",", 1)[1]
    try:
        blob = base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise ValueError("image upload is not valid base64") from exc
    if not blob:
        raise ValueError("image upload is empty")
    if len(blob) > MAX_IMAGE_BYTES:
        raise RequestTooLarge(
            f"image exceeds the {MAX_IMAGE_BYTES // (1024 * 1024)} MB decoded limit")
    try:
        with Image.open(io.BytesIO(blob)) as image:
            width, height = image.size
            image_format = str(image.format or "").upper()
            if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                raise ValueError("image dimensions exceed the safe local limit")
            image.verify()
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("upload is not a readable PNG, JPEG or WebP image") from exc
    extension = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}.get(image_format)
    if extension is None:
        raise ValueError("only PNG, JPEG and WebP image uploads are accepted")
    return blob, extension


def decode_video_upload(raw):
    """Decode a bounded browser-playable review render without contacting a provider."""
    import base64

    if isinstance(raw, str) and raw.strip().startswith("data:") and "," in raw:
        raw = raw.split(",", 1)[1]
    try:
        blob = base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise ValueError("render upload is not valid base64") from exc
    if not blob:
        raise ValueError("render upload is empty")
    if len(blob) > MAX_VIDEO_BYTES:
        raise RequestTooLarge(
            f"render exceeds the {MAX_VIDEO_BYTES // (1024 * 1024)} MB decoded limit")
    if len(blob) >= 12 and blob[4:8] == b"ftyp":
        return blob, ".mp4"
    if blob.startswith(b"\x1aE\xdf\xa3"):
        return blob, ".webm"
    raise ValueError("only readable MP4 and WebM review renders are accepted")

_REINDEX_LOCK = threading.RLock()


def _serialized_reindex(fn):
    def run(*args, **kwargs):
        with _REINDEX_LOCK:
            return fn(*args, **kwargs)
    return run


@_serialized_reindex
def reindex_media():
    files = sorted(p.name for p in MEDIA.glob("*")
                   if p.suffix.lower() in (".png", ".mp4", ".mp3")) if MEDIA.exists() else []
    cb_db.atomic_write_json(ROOT, DATA / "media-index.json", files)
    return files

@_serialized_reindex
def reindex_episodes():
    """Merge shot packages and immutable current-script pointers into one episode list."""
    eps = {}
    if OUT.exists():
        # prefer the BEAT package; fall back to a legacy shot package for older episodes.
        # Order by MTIME (oldest first, so the NEWEST wins the per-episode update) — this MATCHES the fire path
        # (cb_pipeline._resolve_pkg uses max-mtime), so the studio DISPLAYS the exact package it FIRES. If these two
        # disagreed (they used to: display=alphabetical, fire=newest), a re-fire would regenerate a package the studio
        # never shows → "the keyframes aren't repopulating." Same key on both = they can never diverge again.
        _mt = lambda p: p.stat().st_mtime
        for p in sorted(OUT.glob("*_beat_package.json"), key=_mt) + sorted(OUT.glob("*_shot_package.json"), key=_mt):
            try:
                d = json.loads(p.read_text())
                n = d.get("episode")
                if n is None:
                    continue
                e = eps.setdefault(n, {"number": n})
                if e.get("package") and p.name.endswith("_shot_package.json"):
                    continue   # a beat package already claimed this episode — don't overwrite with the legacy one
                units = d.get("beats", d.get("shots", []))
                e.update({"title": d.get("title", p.stem), "logline": d.get("logline", ""),
                          "leadBear": d.get("leadBear", ""), "format": d.get("format", ""),
                          "unit": d.get("unit", "shot"),
                          "beatCount": len(units), "shotCount": len(units),
                          "package": p.name, "shotPackage": p.name})
            except Exception:
                pass
    for p in sorted(SCRIPTS.glob("Ep*.txt")):
        m = re.match(r"Ep(\d+)_", p.name)
        if not m:
            continue
        n = int(m.group(1))
        e = eps.setdefault(n, {"number": n})
        e.setdefault("script", p.name)
        e.setdefault("title", p.stem.split("_", 1)[-1].replace("_", " "))
        try:
            ep = f"Ep{n}"
            if SCRIPT_STORE.current(ep, required=False) is None:
                title_path = SCRIPTS / f"{ep}.title"
                legacy_title = (title_path.read_text().strip() if title_path.exists()
                                else e.get("title") or ep)
                SCRIPT_STORE.migrate_legacy(ep, p, legacy_title)
        except Exception as exc:
            print(f"SCRIPT VERSION MIGRATION WARNING — {p.name}: {exc}", flush=True)

    # The pointer wins over filename ordering. Old immutable versions may remain forever
    # without a scan accidentally making one active again.
    for current in SCRIPT_STORE.list_current():
        n = int(current["episodeId"][2:])
        e = eps.setdefault(n, {"number": n})
        e.update({"script": current["displayFile"],
                  "scriptVersionId": current["scriptVersionId"],
                  "scriptSha256": current["sha256"],
                  "scriptActivatedAt": current["activatedAt"]})
        e.setdefault("title", current.get("title") or f"Episode {n}")
    out = []
    for n in sorted(eps):
        e = eps[n]
        _tf = SCRIPTS / f"Ep{n}.title"                 # the EXACT user-typed title (preserves apostrophes/case) — authoritative
        if _tf.exists():
            try:
                _t = _tf.read_text().strip()
                if _t:
                    e["title"] = _t
            except Exception:
                pass
        e["status"] = (("Beats ready" if e.get("unit") == "beat" else "Shot list ready")
                       if e.get("package") else ("Script uploaded" if e.get("script") else "New"))
        out.append(e)
    # cb_intake reads the episode registry to verify that its immutable-script pointer and
    # the registered episode agree. Publish that pointer-only view first, then annotate the
    # cards from cb_intake's canonical status instead of treating any old beat-package file
    # as production-ready.
    cb_db.atomic_write_json(ROOT, DATA / "episodes.json", out)
    try:
        import cb_intake
        for e in out:
            status = cb_intake.intake_status(f"Ep{e['number']}")
            e["packageCurrent"] = bool(status.get("canonicalCurrent"))
            if e["packageCurrent"]:
                e["storyIntakeState"] = "approved"
                e["status"] = ("Beats ready" if e.get("unit") == "beat"
                               else "Shot list ready")
                continue

            if e.get("package"):
                e["stalePackage"] = e["package"]
                for key in ("logline", "leadBear", "format", "unit", "beatCount", "shotCount"):
                    e.pop(key, None)
            candidate = status.get("candidate") if status.get("candidateCurrent") else None
            if candidate and candidate.get("approvalState") == "awaiting-human-approval":
                e.update({
                    "storyIntakeState": "awaiting-review",
                    "status": "Story review needed",
                    "proposedTitle": candidate.get("title"),
                    "proposedLogline": candidate.get("logline"),
                    "proposalBeatCount": len(candidate.get("beats") or []),
                    "proposalSceneCount": len(candidate.get("scenes") or []),
                })
            elif status.get("hasScript"):
                e["storyIntakeState"] = "needs-run"
                e["status"] = "Story intake needed"
            else:
                e["storyIntakeState"] = "needs-script"
                e["status"] = "New"
    except Exception as exc:
        print(f"STORY INTAKE INDEX WARNING — {exc}", flush=True)
    cb_db.atomic_write_json(ROOT, DATA / "episodes.json", out)
    return out


def synchronize_episode_script_registry(episode, expected_script_version_id):
    """Publish and verify a newly activated script before intake can read it."""
    records = reindex_episodes()
    number = int(re.sub(r"\D", "", str(episode)) or "0")
    record = next(
        (item for item in records if int(item.get("number", -1)) == number),
        None,
    )
    actual = record.get("scriptVersionId") if record else None
    if actual != expected_script_version_id:
        raise RuntimeError(
            f"episode registry synchronization failed for {episode}: "
            f"expected {expected_script_version_id}, found {actual or 'no record'}")
    return record

# ---- pipeline driver: fire/approve gates via cb_pipeline (renders run in a background thread) ----
JOBS = {}  # jobId -> {jobId, scene, gate, status, log, started, ended}
PROCS = {}  # jobId -> Popen (live process group, so a firing can be stopped mid-run)
_JOB_LOCK = threading.RLock()
_DIRECTOR_SESSION_CACHE = {}
_DIRECTOR_SESSION_CACHE_LOCK = threading.RLock()
_DIRECTOR_SESSION_BUILD_LOCK = threading.Lock()
# Production mutations and completed jobs explicitly invalidate this cache. Keep
# browser polling on the proven projection instead of rebuilding the full ledger
# every minute; the freshness guard restarts the server for code/data-file changes.
_DIRECTOR_SESSION_CACHE_TTL_SEC = 3600.0
DIRECTOR_ACTION_IDS = {
    "open-inspector", "open-provider-setup", "direct-scene",
    "build-scene-plate", "select-scene-plate-library", "select-scene-plate-upload",
    "select-keyframe-library", "select-keyframe-upload",
    "select-keyframe-candidate",
    "build-keyframe", "build-voice", "prepare-render",
    "accept-keyframe", "iterate-keyframe",
    "accept-voice", "iterate-voice",
    "approve-spend", "cancel-spend",
    "accept-animation", "iterate-animation",
    "run-ai-review",
    "run-quality-review", "accept-quality", "reopen-shot",
    "build-master", "run-final-review", "accept-master", "iterate-master",
    "save-retake-note",
                }


def _anthropic_room_chat(payload):
    """Proxy one Studio-room message to Claude without altering the system prompt."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    system = payload.get("system")
    messages = payload.get("messages")
    if isinstance(system, str):
        if not system.strip():
            raise ValueError("system is required")
    elif isinstance(system, list) and system:
        for block in system:
            if not isinstance(block, dict):
                raise ValueError("system blocks must be objects")
            if block.get("type") != "text" or not isinstance(block.get("text"), str):
                raise ValueError("system blocks must be Anthropic text blocks")
    else:
        raise ValueError("system is required")
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages is required")
    clean_messages = []
    for item in messages:
        if not isinstance(item, dict):
            raise ValueError("messages must contain objects")
        role = str(item.get("role") or "").strip()
        content = str(item.get("content") or "").strip()
        if role not in ("user", "assistant") or not content:
            raise ValueError("each message needs role user|assistant and content")
        clean_messages.append({"role": role, "content": content})
    body = json.dumps({
        "model": "claude-opus-5",
        "max_tokens": int(payload.get("max_tokens") or 2048),
        "system": system,
        "messages": clean_messages,
    }).encode("utf-8")
    conn = http.client.HTTPSConnection("api.anthropic.com", timeout=90)
    try:
        conn.request(
            "POST", "/v1/messages", body=body,
            headers={
                "content-type": "application/json",
                "anthropic-version": "2023-06-01",
                "x-api-key": api_key,
            },
        )
        response = conn.getresponse()
        raw = response.read()
    finally:
        conn.close()
    try:
        data = json.loads(raw.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        data = {"error": {"message": raw.decode("utf-8", errors="replace")[:500]}}
    if response.status >= 400:
        message = ((data.get("error") or {}).get("message") or
                   data.get("message") or f"Anthropic returned HTTP {response.status}")
        raise RuntimeError(message)
    text = "".join(
        str(part.get("text") or "")
        for part in (data.get("content") or [])
        if isinstance(part, dict) and part.get("type") == "text"
    ).strip()
    return {"text": text}


def _clear_director_session_cache(scene=None, episode=None):
    with _DIRECTOR_SESSION_CACHE_LOCK:
        if scene is None and episode is None:
            _DIRECTOR_SESSION_CACHE.clear()
            return
        for key in list(_DIRECTOR_SESSION_CACHE):
            key_episode, key_scene, _ = key
            if scene is not None and key_scene != str(scene):
                continue
            if episode is not None and key_episode != str(episode):
                continue
            _DIRECTOR_SESSION_CACHE.pop(key, None)


def _persist_job(job, required=False):
    """Write a thread-safe snapshot of one job to the durable Studio ledger."""
    with _JOB_LOCK:
        snapshot = dict(job)
    try:
        cb_db.persist_job(ROOT, snapshot)
    except Exception as exc:
        print(f"STUDIO JOB PERSISTENCE ERROR - {snapshot.get('jobId')}: {exc}", flush=True)
        if required:
            raise


def _jobs_snapshot():
    with _JOB_LOCK:
        return {job_id: dict(job) for job_id, job in JOBS.items()}


WORKBENCH_STATE_FILE = DATA / "project-workbench-state.json"


def _empty_workbench_state():
    return {"projects": {}}


def _load_workbench_state():
    try:
        if WORKBENCH_STATE_FILE.exists():
            payload = json.loads(WORKBENCH_STATE_FILE.read_text())
            if isinstance(payload, dict):
                payload.setdefault("projects", {})
                return payload
    except Exception:
        pass
    return _empty_workbench_state()


def _workbench_key(project, episode, scene):
    return f"{project or ACTIVE_PROJECT_ID}:{episode or 'Ep1'}:{scene or '1'}"


def _project_workbench_state(project=None, episode="Ep1", scene="1"):
    project = project or ACTIVE_PROJECT_ID
    payload = _load_workbench_state()
    key = _workbench_key(project, episode, scene)
    return payload.get("projects", {}).get(key, {
        "project": project,
        "episode": episode,
        "scene": scene,
        "activeBeatId": "moustache",
        "beatState": {},
        "updatedAt": None,
    })


def _save_project_workbench_state(update):
    project = str(update.get("project") or ACTIVE_PROJECT_ID)
    episode = str(update.get("episode") or "Ep1")
    scene = str(update.get("scene") or "1")
    key = _workbench_key(project, episode, scene)
    payload = _load_workbench_state()
    current = payload.setdefault("projects", {}).get(key, {})
    merged = {
        **current,
        "project": project,
        "episode": episode,
        "scene": scene,
        "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if update.get("activeBeatId"):
        merged["activeBeatId"] = str(update.get("activeBeatId"))
    if isinstance(update.get("beatState"), dict):
        beat_state = dict(merged.get("beatState") or {})
        for beat_id, state in update["beatState"].items():
            if isinstance(state, dict):
                beat_state[str(beat_id)] = {**dict(beat_state.get(str(beat_id)) or {}), **state}
        merged["beatState"] = beat_state
    if isinstance(update.get("retakeNotes"), dict):
        notes = dict(merged.get("retakeNotes") or {})
        for note_key, note_value in update["retakeNotes"].items():
            notes[str(note_key)] = str(note_value)[:1000]
        merged["retakeNotes"] = notes
    payload["projects"][key] = merged
    cb_db.atomic_write_json(ROOT, WORKBENCH_STATE_FILE, payload)
    return merged

# ADDED 2026-07-12 (full-codebase audit continued, alongside the _freshness_watch fix above): PROCS only ever
# tracked async render jobs, never a synchronous request thread doing real work of its own (a blocking
# subprocess.run in approve_gate/set_master_studio, a preview-endpoint subprocess, _serve_static's chunked
# streaming loop) — so the idle-reload guard could fire mid-request. _INFLIGHT counts every live HTTP request
# (incremented/decremented by the @_tracked decorator wrapping do_GET/do_HEAD/do_POST below); _freshness_watch
# now waits for it to hit zero too, not just PROCS.
_INFLIGHT = 0
_INFLIGHT_LOCK = threading.Lock()
def _tracked(fn):
    """Wrap an HTTP handler method so it counts toward _INFLIGHT for its ENTIRE body — including an early
    return or a raised exception (both are common: nearly every handler below returns as soon as it matches
    self.path). Applied to do_GET/do_HEAD/do_POST, the three real HTTP entry points."""
    def _wrapped(self, *a, **kw):
        global _INFLIGHT
        with _INFLIGHT_LOCK:
            _INFLIGHT += 1
        try:
            return fn(self, *a, **kw)
        finally:
            with _INFLIGHT_LOCK:
                _INFLIGHT -= 1
    return _wrapped

def _jid(prefix):
    """A job ID that can NEVER collide — a second-resolution timestamp alone lets two fast fires on the same
    beat/scene overwrite each other in JOBS/PROCS, orphaning the first process with no way to track or stop it."""
    return f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:6]}"

def _pkg_name(episode="Ep1"):
    """The current episode's beat-package FILENAME (basename only) — the default `package` for beat previews.
    Resolved by glob so any episode title works (mirrors cb_pipeline._resolve_pkg, but returns the bare name).
    FIXED 2026-07-12 (full-codebase audit continued): this pre-sorted candidates by filename before taking
    max-mtime, while cb_pipeline._resolve_pkg() takes max-mtime over an UNSORTED glob() result — on a genuine
    mtime tie, Python's max() keeps the FIRST candidate in iteration order, so the two resolvers could pick
    different files (the exact "display != fire" class of bug this project already hit once). Dropped the
    pre-sort so both use the same glob-order tie-break; masked in practice by the enforced
    one-package-per-episode convention, but no longer a silent divergence risk if that's ever broken."""
    cands = list(OUT.glob(f"{episode}_*beat_package.json")) or list(OUT.glob(f"{episode}_*shot_package.json"))
    return (max(cands, key=lambda p: p.stat().st_mtime).name if cands
            else f"{episode}_The_Adventure_Begins_beat_package.json")
PKG_NAME = _pkg_name()

# ── GATE-1 CASCADE-RELOCK (bug fix, 2026-07-02, Julian) — ⚠ DUPLICATED from engine/cb_pipeline.py's
#    _scene_beats_fingerprint/_relock_if_stale (a separate process, no engine import here — same convention as
#    the already-duplicated GATE_SEQ above). See cb_pipeline.py for the full rationale. Every read of locked_state()
#    (the studio's ONLY path to gate-status data) re-checks every episode/scene it finds and cascade-clears a
#    scene's "1"/"2a"/"2b"/"3"/"4"/"5" + per-beat locks the moment its Gate-1 deliverable no longer matches the
#    fingerprint recorded when Gate 1 was approved, AND (via _relock_chain_stale_scenes below) cascade-clears
#    any downstream per-beat keyframe/clip lock whose upstream chain source has since been retaken — so the
#    Pipeline page can never show a stale "signed off" again, for either mechanism.
def _beat_sort_key(code):
    """Natural sort on the trailing beat number ('3.B10' -> 10, never a lexicographic '3.B10' < '3.B9' bug) —
    mirrors cb_preflight._beat_sort_key (a separate process, no engine import here — same convention as
    GATE_SEQ/_scene_beats_fingerprint above). ADDED 2026-07-12 (full-codebase audit continued): this file's
    own beat-code sort was still the plain lexicographic form after cb_pipeline.py's identical mirror was
    already corrected (2026-07-11) — the two had silently diverged. Used everywhere this file orders beats."""
    m = re.search(r"[Bb](\d+)\s*$", str(code or ""))
    return int(m.group(1)) if m else 0

def _scene_beats_fingerprint(episode, scene):
    # NOTE: this function must stay FULLY SELF-CONTAINED (its own local `import re`, its own nested sort-key
    # helper, never a reference to a module-level name like _beat_sort_key above) — engine/test_gate_cascade.py's
    # test_serve_py pulls this exact function's source out via ast and execs it in a minimal namespace
    # ({json, pathlib, hashlib, GATE_SEQ} only), so any dependency on another module-level name here raises a
    # bare NameError the moment the test calls it directly. Confirmed live 2026-07-12 (full-codebase audit
    # continued) when the natural-sort fix below was first written to call the shared _beat_sort_key — the test
    # crashed immediately; this local, duplicated form is the fix.
    import hashlib, re as _re
    def _bkey(code):
        m = _re.search(r"[Bb](\d+)\s*$", str(code or ""))
        return int(m.group(1)) if m else 0
    # FIXED 2026-07-12 (full-codebase audit continued): dropped the filename pre-sort (see _pkg_name's own
    # note above) so this resolves the SAME candidate cb_pipeline._resolve_pkg() would on a genuine mtime tie.
    cands = list(OUT.glob(f"{episode}_*beat_package.json")) or list(OUT.glob(f"{episode}_*shot_package.json"))
    if not cands:
        return None
    pkg = max(cands, key=lambda p: p.stat().st_mtime)
    d = json.loads(pkg.read_text())
    beats = [b for b in (d.get("beats") or d.get("shots") or []) if str(b.get("sceneNumber")) == str(scene)]
    # FIXED 2026-07-12 (full-codebase audit continued): a plain lexicographic sort misorders any scene with
    # 10+ beats ("1.B10" sorts before "1.B2") — cb_pipeline.py's own copy of this exact function was already
    # corrected to natural-sort (2026-07-11); this one hadn't been, so the two independently-computed hashes
    # could diverge the moment a scene reaches 10+ beats (harmless today — no live scene is that large yet —
    # but sd["1_fp"] is WRITTEN by cb_pipeline.approve() using its own fingerprint function and compared HERE
    # against this one, so the two must keep producing byte-identical hashes for identical input).
    beats.sort(key=lambda b: _bkey(b.get("beatCode") or b.get("shotCode") or ""))
    blob = json.dumps(beats, sort_keys=True, ensure_ascii=False)
    # Script presentation cleanup (for example removing a leading dialogue
    # number) is not a creative scene change and must not relock every gate.
    # Keep real wording, beat, cast and timing changes fingerprint-visible.
    blob = re.sub(r'("exactText"\s*:\s*")\d+\\t', r'\1', blob)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]

def _relock_stale_scenes(d):
    """Mutates `d` (the parsed locked.json) in place, cascade-clearing any scene whose Gate-1 fingerprint has
    drifted. Returns True if anything changed (caller persists it back to disk)."""
    changed = False
    for episode, escenes in list(d.items()):
        if not isinstance(escenes, dict):
            continue
        for scene, sd in list(escenes.items()):
            if not isinstance(sd, dict) or not sd.get("1") or not sd.get("1_fp"):
                continue
            try:
                current = _scene_beats_fingerprint(episode, scene)
            except Exception:
                continue
            if current is None or current == sd["1_fp"]:
                continue
            print(f"⚠ AUTO-RELOCKED {episode} scene {scene} — Gate 1 deliverable changed since sign-off "
                  f"(fingerprint {current} != approved {sd['1_fp']}); every downstream gate + per-beat lock reset.", flush=True)
            for g in list(GATE_SEQ) + ["2", "1_fp"]:
                sd.pop(g, None)
            sd["beats"] = {}
            changed = True
    return changed

# ── FRAME CHAIN cascade mirror (doctrine, 2026-07-02/03, Julian) — ADDED 2026-07-12 (full-codebase audit
#    continued, HIGH severity): locked_state() cascade-cleared a scene's Gate-1 fingerprint drift (above) but
#    never mirrored cb_pipeline.py's SEPARATE frame-chain cascade (_beat_end_frame_hash/_relock_chain_if_dirty)
#    — a retaken upstream clip (a new harvested settle frame) left every downstream beat's per-beat
#    "keyframe"/"clip" lock showing a stale "✓ signed off" (app.html's beatStageLocked/renderRelayPanel read
#    these flags straight off locked_state()'s payload) until some UNRELATED gate action for that scene
#    happened to call cb_pipeline's own _approved() and re-trigger the real cascade. Mirrors the LOGIC (not
#    the import) of cb_pipeline._beat_end_frame_hash/_relock_chain_if_dirty — same convention as every other
#    duplicate above.
def _beat_end_frame_hash(episode, code, bslug):
    """Content hash of a beat's HARVESTED SETTLE FRAME. None if it doesn't exist yet (the upstream beat hasn't
    rendered a clip) — mirrors cb_pipeline._beat_end_frame_hash exactly."""
    import hashlib
    p = MEDIA / f"{episode}_{code}_{bslug}_settle.png"
    if not p.exists():
        return None
    try:
        return hashlib.sha1(p.read_bytes()).hexdigest()[:16]
    except Exception:
        return None

def _relock_chain_stale_scenes(d):
    """Mutates `d` in place, same pattern as _relock_stale_scenes above: for every scene with recorded
    per-beat locks, walks its beats in order and clears "keyframe"/"clip" on the first one (and every one
    after it) whose recorded chain_source_fp no longer matches its upstream beat's CURRENT ending-frame hash
    — their own chain sources are now suspect too, exactly like cb_pipeline._relock_chain_if_dirty. Returns
    True if anything changed."""
    changed = False
    for episode, escenes in list(d.items()):
        if not isinstance(escenes, dict):
            continue
        for scene, sd in list(escenes.items()):
            if not isinstance(sd, dict):
                continue
            beats_locks = sd.get("beats") or {}
            if not beats_locks:
                continue
            try:
                cands = (list(OUT.glob(f"{episode}_*beat_package.json"))
                          or list(OUT.glob(f"{episode}_*shot_package.json")))
                if not cands:
                    continue
                pkg = json.loads(max(cands, key=lambda p: p.stat().st_mtime).read_text())
            except Exception:
                continue
            scene_beats = [b for b in (pkg.get("beats") or pkg.get("shots") or [])
                           if str(b.get("sceneNumber")) == str(scene)]
            scene_beats.sort(key=lambda b: _beat_sort_key(b.get("beatCode") or b.get("shotCode") or ""))
            dirty_from = None
            for i, b in enumerate(scene_beats):
                if i == 0:
                    continue   # the scene anchor chains off the PLATE, not a previous beat's ending frame
                code = str(b.get("beatCode") or b.get("shotCode"))
                bl = beats_locks.get(code)
                if not bl or not bl.get("keyframe") or not bl.get("chain_source_fp"):
                    continue
                prev = scene_beats[i - 1]
                prev_code = prev.get("beatCode") or prev.get("shotCode")
                prev_slug = prev.get("slug", str(prev_code).replace(".", "_"))
                current_fp = _beat_end_frame_hash(episode, prev_code, prev_slug)
                if current_fp and current_fp != bl["chain_source_fp"]:
                    dirty_from = i
                    break
            if dirty_from is None:
                continue
            scene_changed = False
            for b in scene_beats[dirty_from:]:
                code = str(b.get("beatCode") or b.get("shotCode"))
                bl = beats_locks.get(code)
                if bl and (bl.get("keyframe") or bl.get("clip")):
                    bl["keyframe"] = False; bl["clip"] = False
                    scene_changed = True
            if scene_changed:
                print(f"⚠ AUTO-RELOCKED {episode} scene {scene} — an upstream ending frame changed (a retake); "
                      f"{len(scene_beats) - dirty_from} downstream beat(s) marked needing keyframe review.", flush=True)
                changed = True
    return changed

def locked_state():
    f = CBGEN / "locked.json"
    try:
        d = json.loads(f.read_text()) if f.exists() else {}
    except Exception:
        return {}
    try:
        # FIXED 2026-07-12 (full-codebase audit continued): only _relock_stale_scenes ran here — see
        # _relock_chain_stale_scenes's own comment above for why that left the frame-chain cascade unmirrored.
        changed = _relock_stale_scenes(d)
        if _relock_chain_stale_scenes(d):
            changed = True
        if changed:
            f.write_text(json.dumps(d, indent=1))
    except Exception:
        pass   # fail-open: a relock error must never brick gate-status reads
    return d

def notes_state():
    f = CBGEN / "notes.json"
    try: return json.loads(f.read_text()) if f.exists() else {}
    except Exception: return {}

def relay_state_all():
    """The FULL relay_state.json, straight off disk — {"Ep1": {"1": {winnerCode, nextCode, harvested, remint,
    anchor, driftCheck, ...}}}. Exposed on /api/pipeline (the payload every page already fetches) so Gate 3's
    own panel can render a pending anchor SYNCHRONOUSLY (no extra round-trip, no per-beat modal needed to
    discover it exists). RE-MINT SCOPING (rule 32, 2026-07-05): "remint" and "driftCheck" are both null for an
    intentional_next_shot next beat (the default) — no NB2 pass ran. "anchor" is ALWAYS populated (the re-mint
    when one ran, the raw harvest otherwise); the UI reads "anchor", never assumes "remint" is the only shape."""
    f = CBGEN / "relay_state.json"
    try:
        return json.loads(f.read_text()) if f.exists() else {}
    except Exception:
        return {}

def visions_state():
    """{"Ep1": ["2.V1", ...], ...} — every declared vision shot code per episode, straight off continuity.json.
    Lets the Studio's relay-truth walk-back (app.html's keyframesFor) skip vision beats exactly like the
    engine's own cb_prompts.vision_for does server-side — a vision never chains and is never chained through."""
    f = pathlib.Path(_paths().CONTINUITY)   # T44: from the project profile
    try:
        d = json.loads(f.read_text()) if f.exists() else {}
    except Exception:
        return {}
    out = {}
    for ep, block in d.items():
        if isinstance(block, dict):
            out[ep] = [v.get("shot") for v in (block.get("visions") or []) if isinstance(v, dict) and v.get("shot")]
    return out

def continuity_state():
    try:
        p = subprocess.run(["python3", "cb_continuity.py", "--json"], cwd=str(CBGEN),
                           capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        return json.loads(p.stdout or "[]")
    except Exception as e:
        return [{"level": "NOTE", "scene": "-", "shot": "-", "msg": f"continuity check error: {e}"}]

def _humanise(line, gate=None):
    """Turn a raw pipeline log line into a friendly 'current step' for the UI."""
    l = line.strip()
    low = l.lower()
    if "byteplus downloading" in low or "byteplus downloaded" in low:
        return "Render returned — downloading and registering the video…"
    if "byteplus poll" in low:
        return "Polling Seedance API — provider is processing the render…"
    if "byteplus submitted" in low:
        return "Submitted to Seedance 2.5 — provider task accepted…"
    if "byteplus submitting" in low or "queued-for-submit" in low:
        return "Submitting the sealed request to Seedance 2.5…"
    if "spend disclosure" in low or "spend authorization" in low:
        return "Preparing the sealed Fire request and maximum cost…"
    if str(gate or "").startswith("creative"):
        if "insufficient_quota" in low or "no credits remaining" in low:
            return "Director paused — OpenAI text credits required"
        if "canon envelope" in low: return "Checking canon and scene continuity…"
        if "heart contract" in low: return "Story Director — shaping the scene’s emotional purpose…"
        if "gate 1" in low: return "Director and Cinematographer — exploring scene treatments…"
        if "gate 2" in low: return "Showrunner — selecting the strongest treatment…"
        if "gate 4" in low: return "Cinematic Shot Director — packing the production units…"
        if "gate 6" in low: return "Showrunner — challenging the complete scene direction…"
        if "voice pass" in low: return "Voice Director — preserving exact dialogue and performance…"
        if "storyboard v2" in low: return "Scene Direction ready for review ✓"
    if "writers' room" in low or "writers’ room" in low: return "Writers’ Room — opening the room…"
    if "passes 0-3" in low or "heart lock" in low: return "Writers’ Room — Heart Lock · the Game · the Outline…"
    if "passes 4-7" in low or "draft locked" in low: return "Writers’ Room — drafting · co-watch · Braintrust · lock…"
    if "the scorecard" in low or "below the bar" in low or "scorecard —" in low: return "Writers’ Room — scoring the script /10…"
    if "ready for gate 1" in low: return "Writers’ Room — script written + scored ✓"
    if "the director:" in low or "reading the script" in low: return "Director — reading the script…"
    if "stage a" in low or "beat map" in low: return "Director — beat map (scenes, Pillars, emotional cores)…"
    if "stage b" in low or "beats: scene" in low or "coverage: scene" in low:
        m = re.search(r"scene (\d+)", low); return f"Director — beats: scene {m.group(1)}…" if m else "Director — beat design…"
    if "braintrust" in low: return "Director — Braintrust remake…"
    if "director complete" in low: return "Director — plan written ✓"
    if "pre-flight" in low or "context audit" in low: return "Checking the context is complete…"
    if "self-correct round" in low: return "Self-correcting — " + l.split("self-correct",1)[1].strip(": ")
    if "visual qa" in low: return "Visual QA — checking the rendered frames…"
    if "pose candidate" in low: return "Building the character performance pose…"
    if "pose check" in low: return "Checking identity, proportions and acting…"
    if "pose reused" in low or "pose ready" in low: return "Reusing a qualified performance pose…"
    if "pose qualified" in low: return "Performance pose passed — composing the frame…"
    if "posed integration" in low: return "Composing exact character scale and blocking…"
    if "keyframe build complete" in low: return "Finished keyframe ready for your review ✓"
    if "continuity check" in low or "CONTINUITY —" in l: return "Continuity check…"
    if "start =" in low and "master" in low: return f"Keeping the locked master ({l.split()[0]})…"
    if "beat keyframes:" in low: return "Building the beat keyframes…"
    if "opening keyframe ->" in low: return f"Rendering beat {l.split()[0].strip()} keyframe…"
    if "= vision of scene" in low: return f"Rendering beat {l.split()[0].strip()} (vision keyframe)…"
    if low.startswith("beat ") and "take" in low: return f"Rendering {l.split(':')[0].strip()} (the 10-12s take)…"
    if "beat driver:" in low: return "Rendering the beat takes…"
    if "scene plate (" in low or "scene plate is" in low: return "Building the scene shot (the empty plate)…"
    if "start ->" in low: return f"Rendering keyframe {l.split()[0]} (start)…"
    if "end ->" in low: return f"Rendering keyframe {l.split()[0]} (end)…"
    if l.startswith("REGEN") or "regenerat" in low or "change " in low[:8]: return "Regenerating a flagged shot…"
    if str(gate or "").startswith("creative") and "seedance" in low:
        return "Story & Direction — packing production units…"
    if "seedance" in low or "-> Ep3_" in l and ".mp4" in l: return "Rendering the clip…"
    if "STITCH" in l: return "Building the post master…"
    if "POST" in l or "picture" in low or "stems" in low:
        return "Post — conforming, mixing, captions + delivery QC…"
    if "STRUCTURED SCENE BUILD DONE" in l: return "Keyframes done — verifying…"
    if "CLEAN" in l: return "Clean — it stays."
    return l[:90]


def _process_lines_until_exit(process, timeout=0.5):
    """Yield live stdout without waiting forever on an inherited pipe.

    Provider clients can briefly leave stdout inherited by a helper process. A
    plain ``for line in process.stdout`` then waits for that helper to close the
    pipe even after the actual render worker has exited. Polling between readable
    events lets the Studio publish the completed artifacts as soon as its worker
    is done while preserving live progress output.
    """
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    try:
        while True:
            if selector.select(timeout):
                line = process.stdout.readline()
                if line:
                    yield line
                    continue
            if process.poll() is not None:
                return
    finally:
        selector.close()

def _stream(jobId, args):
    """Run cb_pipeline streaming, so the job's current STEP is live (not blank until it finishes)."""
    job = JOBS[jobId]
    try:
        with _JOB_LOCK:
            if job.get("stopped"):
                job["status"] = "stopped"
                job["step"] = "Stopped by user."
                return
            p = subprocess.Popen(["python3", "-u"] + args, cwd=str(CBGEN),
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, bufsize=1, stdin=subprocess.DEVNULL,
                                 # Own process group, so STOP kills the gate and every
                                 # render child it spawns without inheriting server stdin.
                                 start_new_session=True)
            PROCS[jobId] = p
            job["pid"] = p.pid
        _persist_job(job)
        lines = []
        _last_reindex = 0.0
        _last_persist = 0.0
        for line in _process_lines_until_exit(p):
            line = line.rstrip()
            if not line: continue
            lines.append(line)
            with _JOB_LOCK:
                job["log"] = "\n".join(lines[-250:])
                job["step"] = _humanise(line, job.get("gate"))
            # a batch job (e.g. Gate 2b building every beat in a scene) is ONE long subprocess — without this,
            # a beat finished early in the batch stays invisible until the WHOLE batch exits. Throttled to ~2s
            # so a chatty subprocess doesn't turn this into a reindex-per-line hot loop.
            now = time.time()
            if now - _last_reindex > 2:
                try: reindex_media()
                except Exception: pass
                _last_reindex = now
            if now - _last_persist > 1:
                _persist_job(job)
                _last_persist = now
        p.wait()
        with _JOB_LOCK:
            if job.get("stopped"):
                job["status"] = "stopped"; job["step"] = "Stopped by user."
            else:
                job["status"] = "done" if p.returncode == 0 else "failed"
                if p.returncode == 0:
                    # Publish success only after indexes and the Director cache have
                    # been refreshed. The browser reloads as soon as it sees "done".
                    job["status"] = "finalizing"
                    job["step"] = "Refreshing Studio state..."
                    job["error"] = None
                else:
                    detail = next((line for line in reversed(lines)
                                   if any(word in line.casefold() for word in
                                          ("refused", "error", "failed", "invalid"))), None)
                    job["error"] = (detail or lines[-1] if lines else
                                    "The provider process ended without a usable result.")[:600]
                    job["step"] = _humanise(job["error"], job.get("gate"))
    except Exception as e:
        with _JOB_LOCK:
            if job.get("stopped"):
                job["status"] = "stopped"; job["step"] = "Stopped by user."
            else:
                detail = f"{type(e).__name__}: {e}"
                job["log"] = job.get("log", "") + "\n" + detail
                job["status"] = "failed"; job["step"] = detail; job["error"] = detail
    finally:
        with _JOB_LOCK:
            PROCS.pop(jobId, None)
        # Script Direction is preparation, not a producer decision.  Successful text-only
        # intake and scene-direction jobs therefore complete their local handover before the
        # browser is told the job is done.  SEE, HEAR and WATCH retain their human gates.
        try:
            _finalize_automatic_direction(job)
        except Exception as exc:
            with _JOB_LOCK:
                detail = f"Automatic Direction preparation failed: {exc}"
                job["status"] = "failed"
                job["step"] = detail
                job["error"] = detail
                job["log"] = (job.get("log", "") + "\n" + detail).strip()
        # THE central completion point for every gate action fired from the studio (keyframes, clips, voice,
        # retakes, ...) — reindex here regardless of outcome (done/failed/stopped can all have left new files
        # on disk) so the UI's next media-index.json fetch reflects reality instead of the stale server-start snapshot.
        try: reindex_media()
        except Exception: pass
        # Story intake changes episode readiness without creating scene media. Refreshing
        # both indexes here means a completed candidate or lock is visible immediately.
        try: reindex_episodes()
        except Exception: pass
        with _JOB_LOCK:
            job_scene = job.get("scene")
        _clear_director_session_cache(scene=job_scene)
        with _JOB_LOCK:
            if job.get("status") == "finalizing":
                job["status"] = "done"
                job["step"] = "Done."
            job["ended"] = time.time()
        _persist_job(job)

def _start(jobId, gate, scene, args):
    args = list(args)
    _clear_director_session_cache(scene=scene, episode=args[-1] if args else None)
    operation_key = cb_db.job_operation_key(gate, scene, args)
    stale = _is_stale()
    with _JOB_LOCK:
        duplicate = next((existing for existing in JOBS.values()
                          if existing.get("status") == "running" and
                          existing.get("operationKey") == operation_key), None)
        if duplicate:
            return duplicate["jobId"]
        if stale:
            # NEVER fire on stale code — the studio is reloading itself to the latest;
            # re-fire in a moment.
            job = {"jobId": jobId, "scene": str(scene), "gate": str(gate), "args": args,
                   "serverKey": SERVER_KEY, "operationKey": operation_key, "status": "failed",
                   "step": "Studio is loading the latest code - re-fire in a few seconds.",
                   "log": "The studio detected changed source and is reloading itself so every fire runs the "
                          "current software. Wait a moment, then fire again.",
                   "started": time.time(), "ended": time.time()}
        else:
            job = {"jobId": jobId, "scene": str(scene), "gate": str(gate), "args": args,
                   "serverKey": SERVER_KEY, "operationKey": operation_key,
                   "status": "running", "step": "Starting...",
                   "log": "", "started": time.time(), "ended": None}
        JOBS[jobId] = job
    if stale:
        try:
            _persist_job(job, required=True)
        except Exception:
            with _JOB_LOCK:
                JOBS.pop(jobId, None)
            raise
        return jobId
    try:
        _persist_job(job, required=True)
    except Exception:
        with _JOB_LOCK:
            JOBS.pop(jobId, None)
        raise
    threading.Thread(target=_stream, args=(jobId, args), daemon=True).start()
    return jobId

def _queue_episode_storyboards(episode):
    """Start the no-spend scene storyboard pass immediately after intake approval.

    Episode acceptance is the handoff from the approved script/vision into the scene
    board. The scene plans are still reviewable candidates; this only runs the Director's
    text pass and never creates media or advances a human gate.
    """
    import cb_intake
    roster = cb_intake.scene_roster(episode)
    try:
        active_script = cb_scripts.ScriptStore(
            ROOT, show_id=ACTIVE_SHOW.profile.showId).current(
                episode, required=True)
        active_script_version = active_script["scriptVersionId"]
    except (cb_scripts.ScriptStoreError, studio_profile.ShowProfileError):
        active_script = None
        active_script_version = None
    jobs = []
    for scene in roster.get("scenes") or []:
        number = str(scene.get("sceneNumber", "")).strip()
        if not number:
            continue
        storyboard_path = (ROOT / "cb-output" / "creative" /
                           f"{episode}_scene{number}_storyboard.json")
        if storyboard_path.exists():
            try:
                storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                storyboard = {}
            storyboard_script_version = (
                (storyboard.get("sourceScript") or {}).get("scriptVersionId"))
            if (not active_script_version or
                    storyboard_script_version == active_script_version):
                continue
            # An episode-level version id changes when one scene changes. Compare the
            # actual source content for this scene before replacing its direction. This is
            # the same scene-local invariant used by production lineage: changing Scene 3
            # must not rebuild Scenes 1, 2 or 4-8.
            source = storyboard.get("sourceScript") or {}
            source_path = (ROOT / str(source.get("contentPath") or "")).resolve()
            active_path = (ROOT / str((active_script or {}).get("contentPath") or "")).resolve()
            production_path = (ROOT / "cb-output" /
                               f"{episode}_scene{number}_production_package.json")
            if production_path.exists():
                try:
                    import cb_render
                    production = json.loads(production_path.read_text(encoding="utf-8"))
                    if cb_render.lineage_status(
                            production, number, episode).get("current"):
                        continue
                except (OSError, ValueError, cb_render.Refused):
                    pass
            try:
                source_path.relative_to(ROOT.resolve())
                active_path.relative_to(ROOT.resolve())
                old_digest = cb_intake.scene_source_digests(
                    source_path.read_text(encoding="utf-8")).get(number)
                new_digest = cb_intake.scene_source_digests(
                    active_path.read_text(encoding="utf-8")).get(number)
            except (OSError, TypeError, ValueError, cb_intake.Refused):
                old_digest = new_digest = None
            if production_path.exists() and old_digest and old_digest == new_digest:
                continue
            archive_dir = (storyboard_path.parent / "archive" /
                           f"script-{str(active_script_version).replace('sha256:', '')[:12]}")
            archive_dir.mkdir(parents=True, exist_ok=True)
            archive_path = archive_dir / storyboard_path.name
            if not archive_path.exists():
                archive_path.write_bytes(storyboard_path.read_bytes())
        jobs.append(_start(
            _jid(f"creative_scene_{episode}_{number}"),
            "creative:scene", number,
            ["cb_creative.py", "scene", number, episode]))
    return jobs


def _prepare_scene_direction_for_production(episode, scene):
    """Promote a generated scene direction as automatic script preparation.

    The compiler still uses ``approvalState=approved`` as its historical handover token,
    but the record explicitly identifies this as automatic preparation rather than a
    human creative decision. Human authority begins at SEE, HEAR and WATCH.
    """
    import cb_intake
    path = ROOT / "cb-output" / "creative" / f"{episode}_scene{scene}_storyboard.json"
    with cb_db.scene_lease(ROOT, episode, scene, "serve.automatic-direction-handover"):
        package, digest = cb_db.read_json_document(ROOT, path)
        if package.get("approvalState") == "approved":
            try:
                handover = _carry_forward_unchanged_approved_scene(
                    path, episode, scene, package)
                if handover is None:
                    handover = _promote_approved_storyboard(
                        path, episode, scene, package)
            except Exception:
                handover = None
            return {"alreadyPrepared": True, "handover": handover}
        if package.get("approvalState") != "awaiting-human-storyboard-approval":
            raise StoryboardApprovalRefused(
                "Scene Direction is not a current generated candidate")
        source = package.get("sourceScript") or {}
        current = cb_scripts.ScriptStore(
            ROOT, show_id=ACTIVE_SHOW.profile.showId).current(
                episode, required=True)
        if source.get("scriptVersionId") != current.get("scriptVersionId"):
            try:
                source_path = (ROOT / str(source.get("contentPath") or "")).resolve()
                current_path = (ROOT / str(current.get("contentPath") or "")).resolve()
                source_path.relative_to(ROOT.resolve())
                current_path.relative_to(ROOT.resolve())
                old_digest = cb_intake.scene_source_digests(
                    source_path.read_text(encoding="utf-8")).get(str(scene))
                new_digest = cb_intake.scene_source_digests(
                    current_path.read_text(encoding="utf-8")).get(str(scene))
            except (OSError, TypeError, ValueError, cb_intake.Refused):
                old_digest = new_digest = None
            if not old_digest or old_digest != new_digest:
                raise StoryboardApprovalRefused(
                    "Scene Direction belongs to an older version of this scene and must be regenerated")
        original = path.read_bytes()
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        package["approvalState"] = "approved"
        package["automaticPreparation"] = {
            "mode": "script-to-scene-direction",
            "preparedBy": "Studio Director",
            "preparedAt": stamp,
            "humanDecisionRequired": False,
            "humanGates": ["see", "hear", "watch"],
        }
        package.setdefault("approvalLog", []).append({
            "target": "scene", "state": "prepared", "note":
            "Prepared automatically from the active scene script before production.",
            "at": stamp, "by": "Studio Director",
        })
        written_digest = cb_db.atomic_write_json(
            ROOT, path, package, expected_digest=digest)
        try:
            handover = _promote_approved_storyboard(
                path, episode, scene, package)
        except Exception:
            cb_db.atomic_write_bytes(
                ROOT, path, original, expected_digest=written_digest)
            raise
        return {"prepared": True, "handover": handover}


def _finalize_automatic_direction(job):
    """Complete zero-media Direction preparation for a successful background job."""
    if job.get("status") != "finalizing":
        return None
    gate = str(job.get("gate") or "")
    args = list(job.get("args") or [])
    if gate == "storyintake":
        episode = str(args[-1] if args else "Ep1")
        import cb_intake
        status = cb_intake.intake_status(episode)
        candidate = status.get("candidate") or {}
        if (status.get("candidateCurrent") and
                candidate.get("approvalState") == "awaiting-human-approval"):
            record = cb_intake.decide_intake(
                episode, "approve",
                note="Prepared automatically from the active script before scene production.",
                reviewed_by="Studio Director")
            reindex_episodes()
            queued = _queue_episode_storyboards(episode)
            job["automaticDirection"] = {
                "episodePrepared": True, "sceneJobs": queued, "record": record}
            job["step"] = "Episode Direction prepared; scene directions queued."
            return job["automaticDirection"]
        return None
    if gate == "creative:scene":
        episode = str(args[-1] if args else "Ep1")
        scene = str(job.get("scene") or "")
        prepared = _prepare_scene_direction_for_production(episode, scene)
        job["automaticDirection"] = prepared
        job["step"] = "Scene Direction prepared; SEE is ready."
        return prepared
    return None

def write_script(seed, episode="Ep1"):
    """GATE 0 — the Writers' Room: turn a seed into a finished, scored, LOCKED screenplay (cb_writer)."""
    SCRIPTS.mkdir(parents=True, exist_ok=True)
    seedpath = SCRIPTS / f"_seed_{episode}.json"
    seedpath.write_text(json.dumps(seed, ensure_ascii=False))
    return _start(_jid(f"write{episode}"), "write", "0",
                  ["cb_writer.py", str(seedpath), str(episode)])

def stop_job(jobId):
    """Hard-stop a firing gate: kill its whole process group (the pipeline + every render child it spawned)."""
    with _JOB_LOCK:
        job = JOBS.get(jobId)
        if job: job["stopped"] = True
        p = PROCS.get(jobId)
    if p:
        try: os.killpg(os.getpgid(p.pid), signal.SIGKILL)
        except Exception:
            try: p.kill()
            except Exception: pass
    with _JOB_LOCK:
        if job and job.get("status") == "running":
            job["status"] = "stopped"; job["step"] = "Stopped by user."; job["ended"] = time.time()
        PROCS.pop(jobId, None)
    if job:
        _persist_job(job)
    return bool(p)

def stop_all():
    """Stop every currently-running firing."""
    with _JOB_LOCK:
        ids = [jid for jid, j in JOBS.items() if j.get("status") == "running"]
    for jid in ids: stop_job(jid)
    return ids

# server-side gate guard (defense in depth — the HTTP boundary itself refuses to fire/regen past an unsigned step)
# ⚠ DUPLICATED (deliberately, not shared) from engine/cb_pipeline.py's own GATE_SEQ — a separate process. If a gate
# is ever added/renamed/reordered, update BOTH lists in the SAME change, or this HTTP-layer guard and cb_pipeline's
# process-layer guard could silently disagree on what "the previous gate" is.
GATE_SEQ = ["1", "1.6", "2a", "2b", "3", "4", "5"]   # 1.6 = THE PREVIZ REEL (2026-07-08) · …3 Animation ·
# 4 Retakes · 5 Post. Named "1.6" (not "1.5") to avoid colliding with the already-established "Gate 1.5" —
# Director's Eye (cb_director_eye.py), an unrelated automatic flag-only review with no lock state of its
# own, never a member of this list. See engine/cb_previz.py's module docstring for the full note.
def _scene_locks(scene, episode="Ep1"):
    return locked_state().get(episode or "Ep1", {}).get(str(scene), {})
# ── THE RELAY, front door (Julian, 2026-07-03) — job-launch wrappers around cb_pipeline.relay_prepare/
#    relay_approve. relay_approve_beat is the ONLY function in this file that may fire fire_next_beat's
#    approved=True launch — the Approve Anchor button in app.html is the only caller of it.
#    THE ONE-RENDER ECONOMY (Julian, 2026-07-05): both phases dropped their seed/seed-path parameters — a beat
#    has exactly one official clip now (auto-retried once internally on a failed gate), so there is no seed to
#    designate and no "how many candidates" choice left to make.
def relay_prepare_beat(scene, winner_code, episode="Ep1", fast=False):
    """PHASE 1: harvest the winner's own official clip, re-mint (seamless joins only), drift-check, STOP for
    approval (job). fast=False default: standard tier is the production default under the one-render economy."""
    return _start(_jid(f"relayprep_{winner_code}"), f"relay-prepare:{winner_code}", scene,
                  ["cb_pipeline.py", "relay-prepare", str(scene), str(winner_code),
                   f"--episode={episode}", f"--fast={str(bool(fast)).lower()}"])

def relay_approve_beat(scene, winner_code, episode="Ep1", fast=False):
    """PHASE 2: launch the next beat off the anchor an earlier relay_prepare_beat already produced (job) — one
    take, one automatic re-fire on a failed gate, then a hard stop naming the layer at fault.
    fast=False default: standard tier is the production default under the one-render economy."""
    return _start(_jid(f"relayapprove_{winner_code}"), f"relay-approve:{winner_code}", scene,
                  ["cb_pipeline.py", "relay-approve", str(scene), str(winner_code),
                   f"--episode={episode}", f"--fast={str(bool(fast)).lower()}"])

# ── THE SHOT PIPELINE (cb_engine.py design → cb_render.py render loop) — ADDITIVE, 2026-07-16 ──────────────────────
# A separate, parallel surface for the shot-sized production packages (cb-output/{ep}_scene{N}_production_
# package.json). Nothing here touches GATE_SEQ, the beat pipeline, or any existing route — the two endpoints
# (/api/shot-package GET, /api/shot-run POST) plus these helpers are the whole footprint. Jobs run through the
# SAME _jid/_start/_stream runner every existing gate action uses (fresh subprocess, argv list, never a shell).
SHOT_CMDS = ("voice", "voice-shot", "regen-voice", "animatic", "approve-timing-slate", "reject-timing-slate", "scenelook", "approve-scenelook", "reject-scenelook",
             "pose", "approve-pose", "reject-pose", "select-pose-upload",
             "build-keyframe", "keyframe", "approve-keyframe", "rescreen-keyframe", "reject-keyframe",
             "select-upload", "select-library", "select-previous",
             "select-render-upload",
             "select-scenelook-upload", "select-scenelook-library",
             "approve-voice", "reject-voice",
             "fire", "next", "approve", "reject", "override-model-limited",
             "edit", "approve-edit", "reject-edit", "stitch")
# THE OPENING-FRAME SOURCE CHOICE (2026-07-18, Julian's directive): select-upload/select-library/
# select-previous are the three NON-GENERATION opening-frame sources (cb_render.select_keyframe_source) —
# each only ever COPIES an existing file into a new immutable candidate; none calls cb_gen. Routed through
# the identical job runner as every other shot action for one reason: cb_render.py's own ledger-mutation
# lock discipline (refuse-if-a-candidate-is-already-pending) lives in the engine, not the server, and the
# job runner is the one place that already serialises shot mutations per scene.
# "animatic" stays the CLI verb (cb_render.py keeps it as an accepted alias) — but the ARTIFACT it builds is
# the TIMING SLATE (Julian's 2026-07-16 reclassification: Seedance is a probabilistic candidate generator;
# this artifact approves dialogue accuracy / voice assignment / durations / line position ONLY, never
# staging, physical comedy or final rhythm).
REJECT_CATEGORIES = ("identity", "geography", "action-timing", "instruction-ignored", "other")
DEPARTMENT_STAGES = ("look", "cinematography", "voice", "animation",
                     "review-keyframe", "review-animation", "review-final")
_SPEND_TOKEN_RE = re.compile(r"^[a-f0-9]{16,64}$")   # the SERVER-ISSUED single-use spend token (2026-07-16
# spend-protection contract): fire/next without one stores pendingSpendAuth on the shot's ledger and REFUSES;
# with one, the engine re-validates the binding hash (prompt/keyframe/refs/audio/duration/settings/rate/count)
# and refuses if ANYTHING drifted. Lowercase hex only — never a path, never shell-meaningful.
_SHOT_TOKEN = re.compile(r"^[A-Za-z0-9._-]+$")   # scene / episode / shotId — plain tokens, never a path
_CHARACTER_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9 .'-]{0,79}$")

def _shot_pkg_path(scene, episode="Ep1"):
    """Mirrors engine/cb_render.py's _pkg_path (a separate process, no engine import here — the same
    deliberate-duplication convention as GATE_SEQ/_scene_beats_fingerprint above)."""
    return OUT / f"{episode}_scene{scene}_production_package.json"

def _storyboard_file(scene, episode="Ep1"):
    return OUT / "creative" / f"{episode}_scene{scene}_storyboard.json"


def scene_lineage(pkg, scene, episode="Ep1"):
    """THE state-integrity checkpoint's server-side lineage check (2026-07-17): mirrors
    cb_render.lineage_status EXACTLY (deliberately duplicated, never imported — the same
    no-engine-import convention this file already uses for GATE_SEQ/_shot_pkg_path/etc., so
    serve.py never needs a subprocess for a plain hash comparison). Only the server can do
    this at all: the client only ever sees pkg as already-parsed JSON, never raw file bytes,
    so it cannot itself hash the live storyboard file to check it still matches what the
    package claims it was built from. "current" is True ONLY when both hashes are present
    AND equal — never inferred true by omission."""
    renderer = _canonical_cb_render()
    return renderer.lineage_status(pkg, scene, episode)


def _sync_package_storyboard_provenance(package, storyboard_path, storyboard):
    source_storyboard = package.setdefault("sourceStoryboard", {})
    source_storyboard["md5"] = hashlib.md5(pathlib.Path(storyboard_path).read_bytes()).hexdigest()
    source_storyboard["sha256"] = cb_lineage.sha256_file(storyboard_path)
    source_storyboard["approvalState"] = storyboard.get("approvalState")
    source_storyboard["humanNote"] = storyboard.get("humanNote", "")
    source_storyboard["approvalLog"] = list(storyboard.get("approvalLog") or [])
    package_inputs = dict((package.get("inputSignature") or {}).get("inputs") or {})
    if package_inputs:
        package_inputs["storyboardSha256"] = source_storyboard["sha256"]
        package["inputSignature"] = cb_lineage.dependency_signature(
            "production-package", package_inputs)
    return source_storyboard


def _storyboard_creative_card_hashes(storyboard):
    return {
        shot["shotId"]: hashlib.sha256(json.dumps(
            shot, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        for shot in (storyboard.get("shots") or [])
        if shot.get("shotId")
    }


def _carry_forward_unchanged_approved_scene(storyboard_path, episode, scene, storyboard):
    """Refresh provenance when the approved scene's directed shot cards are unchanged."""
    package_path = OUT / f"{episode}_scene{scene}_production_package.json"
    if not package_path.exists():
        return None
    package, package_digest = cb_db.read_json_document(ROOT, package_path)
    if not (package.get("validation") or {}).get("passed"):
        return None

    package_shots = [
        shot.get("shotId") for shot in (package.get("shots") or [])
        if shot.get("shotId")
    ]
    live_hashes = _storyboard_creative_card_hashes(storyboard)
    source_storyboard = package.get("sourceStoryboard") or {}
    stored_hashes = source_storyboard.get("creativeCardHashes") or {}
    if (not package_shots or set(package_shots) != set(live_hashes) or
            any(stored_hashes.get(shot_id) != live_hashes.get(shot_id)
                for shot_id in package_shots)):
        return None
    if source_storyboard.get("inputSignature") != storyboard.get("inputSignature"):
        return None

    _sync_package_storyboard_provenance(package, storyboard_path, storyboard)
    lineage = scene_lineage(package, scene, episode)
    if not lineage.get("current"):
        return None

    handover = package.setdefault("handover", {})
    handover["carriedForwardUnchangedShots"] = list(package_shots)
    handover["resetChangedShots"] = []
    handover["rule"] = "every approved scene creative-card hash must be unchanged"
    cb_db.atomic_write_json(
        ROOT, package_path, package, expected_digest=package_digest)
    return {
        "revision": package.get("revision"),
        "path": str(package_path),
        "carriedForward": list(package_shots),
        "reset": [],
        "archivedPrevious": None,
    }


def _url_from_abs(abs_path):
    """Converts an ABSOLUTE filesystem path (as stored in continuityLedger's keyframeApproval/
    keyframeCandidate 'path' fields) into a servable /engine/media/... URL, the same
    convention shot_media_map's own _url() already uses for its conventional-filename
    lookups. Returns None for anything missing, unresolvable, or outside the approved
    media root (defence in depth — this must never become a path-traversal door)."""
    return cb_asset_registry.url_for_path(abs_path)


def _url_from_reference(abs_path):
    """Expose only references already covered by the static-file allow list."""
    url = cb_asset_registry.url_for_path(abs_path)
    return None if (url and _static_blocked(url)) else url


def shot_media_map(pkg, scene, episode="Ep1"):
    """Server-computed existence map of every shot's media (vo / keyframe / clip / harvested final frame)
    plus the scene-level timing slate and current QC-passed post master. Filenames mirror
    cb_render.py's own writers; the URLs
    are /engine/media/... paths the existing static route already serves (shots/ is a subfolder of the
    approved /engine/media/ root — prefix + extension both pass _static_blocked with zero policy change).

    FILE EXISTENCE HERE VERIFIES AN ASSET EXISTS — IT NEVER GRANTS APPROVAL OR STAGE STATE
    (2026-07-17 state-integrity checkpoint): this map is evidence for the client's own
    deriveSceneState, which reads the REAL approval truth from pkg.continuityLedger's
    keyframeApproval/keyframeCandidate/keyframeRejected fields plus the "lineage" block below
    — never from whether a file happens to sit at a conventional path.

    KEYFRAME URL, CORRECTED (2026-07-18, production-safety directive): a keyframe candidate/
    approval no longer lands at one fixed, conventional filename — the two-phase, non-
    destructive lifecycle (cb_render.keyframe_shot) writes every candidate to its OWN
    uniquely-named path, specifically so a fresh generation can never collide with (and
    silently overwrite) an already-approved file at a shared name. The keyframe URL is
    therefore read from the ledger's OWN recorded path (keyframeApproval, else
    keyframeCandidate) via _url_from_abs, never guessed from a filename convention."""
    shots_dir = MEDIA / "shots"
    def _url(p):
        return ("/engine/media/" + p.relative_to(MEDIA).as_posix()) if p.exists() else None
    registry_shots = cb_asset_registry.shot_media_from_registry(pkg, scene, episode)
    shots = {}
    for s in pkg.get("shots") or []:
        sid = s.get("shotId")
        if not sid:
            continue
        ledger = next((item for item in (pkg.get("continuityLedger") or [])
                       if item.get("shotId") == sid), {})
        # transportCandidates from in-progress batches are migrated by cb_asset_registry;
        # the browser still receives them as normal media.candidates entries.
        record = dict(registry_shots.get(sid) or {})
        record.setdefault("keyframe", None)
        record.setdefault("keyframeCandidate", None)
        record.setdefault("keyframeApproved", None)
        record.setdefault("openingFrame", None)
        record.setdefault("openingFrameSourceShotId", None)
        record.setdefault("clip", None)
        record.setdefault("finalFrame", None)
        record.setdefault("candidates", [])
        edit_work = ledger.get("editWork") or {}
        record["edit"] = ({
            **edit_work,
            "candidateUrl": _url_from_abs(edit_work.get("candidatePath")),
            "sourceUrl": _url_from_abs(edit_work.get("sourcePath")),
        } if edit_work else None)
        record["editHistory"] = [{
            **item,
            "candidateUrl": _url_from_abs(item.get("candidatePath")),
            "sourceUrl": _url_from_abs(item.get("sourcePath") or item.get("path")),
        } for item in (ledger.get("editHistory") or [])[-12:]]
        # The continuity ledger is the authority for the current HEAR take. Registry
        # entries are durable media history and can outlive a scoped dialogue change;
        # allowing one of those entries to populate `vo` would make superseded audio
        # appear current and approvable while the replacement is still pending.
        record["vo"] = _url_from_abs(ledger.get("voPath"))
        record["voicePrevious"] = _url_from_abs(
            (ledger.get("voicePrevious") or {}).get("path"))
        # Relay shots must show their inherited opening frame even while a scoped
        # downstream amendment is waiting for review. This is visual evidence only;
        # approval and provider spend remain separate state.
        if s.get("sourceType") == "relay" and s.get("sourceShotId"):
            source_id = s["sourceShotId"]
            source_media = registry_shots.get(source_id) or {}
            relay_frame = (
                source_media.get("finalFrame") or
                _url(shots_dir / f"{episode}_{source_id}_final_frame.png")
            )
            # The previous shot's landing frame is the relay's authoritative opening
            # evidence. Prefer it over any copied/stale keyframe record on this shot.
            record["openingFrame"] = relay_frame
            record["openingFrameSourceShotId"] = source_id if relay_frame else None
            record["keyframe"] = relay_frame or record.get("keyframe")
        else:
            record["openingFrame"] = (
                record.get("keyframeApproved") or record.get("keyframe")
            )
        shots[sid] = record
    timing_path = MEDIA / f"{episode}_Scene{scene}_timing_slate.mp4"
    if not timing_path.exists():
        timing_path = MEDIA / f"{episode}_Scene{scene}_animatic.mp4"
    try:
        _CBR = _canonical_cb_render()
        timing_status = _CBR.timing_slate_status(scene, episode)
        timing_current = bool(timing_status.get("current"))
        forward_standard = int(pkg.get("creativeDirectingStandardVersion") or 0) >= 3
        timing_approved = (bool(timing_status.get("approved")) if forward_standard
                           else timing_current)
        timing_reason = (timing_status.get("reason") if forward_standard or not timing_current
                         else None)
        lineage = _CBR.lineage_status(pkg, scene, episode)
        post_status = _CBR.post_status(pkg, scene, episode)
        selected_post = (post_status["candidate"] if post_status["candidate"]["exists"] else
                         post_status["approved"] if post_status["approved"]["exists"] else None)
        post_manifest = selected_post.get("manifest") if selected_post else None
        post_media = {
            name: _url_from_abs(asset.get("path"))
            for name, asset in ((post_manifest or {}).get("outputs") or {}).items()
            if isinstance(asset, dict)
        }
        post_media["candidate"] = bool(
            selected_post is post_status["candidate"] if selected_post else False)
        post_media["current"] = bool(selected_post and selected_post.get("current"))
        post_media["qc"] = (post_manifest or {}).get("qc")
    except Exception as exc:
        timing_current = False
        timing_approved = False
        timing_reason = str(exc)
        lineage = {"current": False, "reasonCodes": ["state-evaluation-failed"],
                   "error": str(exc)}
        post_media = {}
    return {"shots": shots,
            # THE TIMING SLATE (2026-07-16 reclassification): new filename first; the pre-reclassification
            # animatic filename kept as a fallback so an older existing render still shows.
            "timingSlate": _url(timing_path),
            "timingSlateCurrent": timing_current,
            "timingSlateApproved": timing_approved,
            "timingSlateReason": timing_reason,
            "animatic": _url(MEDIA / f"{episode}_Scene{scene}_animatic.mp4"),
            "picture": post_media.get("master16x9"),
            "post": post_media,
            "lineage": lineage}


def _expose_session_shot_media(session, media):
    """Add board-friendly media aliases to each shot without changing gate truth."""
    media_by_id = (media or {}).get("shots") or {}
    for shot in session.get("shots") or []:
        shot_id = shot.get("shotId") or shot.get("id")
        shot_media = media_by_id.get(shot_id) or {}
        keyframe_url = (
            shot.get("keyframeUrl") or shot.get("imageUrl") or
            shot_media.get("keyframeApproved") or shot_media.get("keyframe")
        )
        clip_url = shot.get("clipUrl") or shot.get("acceptedUrl") or shot_media.get("clip")
        voice_url = shot.get("voiceUrl") or shot_media.get("vo")
        if keyframe_url:
            shot.setdefault("keyframeUrl", keyframe_url)
            shot.setdefault("imageUrl", keyframe_url)
        if clip_url:
            shot.setdefault("clipUrl", clip_url)
            shot.setdefault("acceptedUrl", clip_url)
        if voice_url:
            shot.setdefault("voiceUrl", voice_url)
    return session


def rough_cut_projection(episode="Ep1", scene=None):
    """Browser-safe projection of an episode or scene edit decision list."""
    import cb_rough_cut
    state = cb_rough_cut.scene_status(episode, scene) if scene else cb_rough_cut.status(episode)
    for collection in (state.get("available") or [], state.get("sequence") or []):
        for shot in collection:
            approved_take = shot.pop("approvedTake", None)
            shot["url"] = _url_from_abs(approved_take) if approved_take else None
            shot.pop("dialogueLines", None)
    return state


# ── SCENE LOOK — server-side mirror of cb_render.scenelook_status (2026-07-18, Julian's
# gate directive): deliberately duplicated, never imported — the same no-engine-import
# convention this file already uses for GATE_SEQ/_shot_pkg_path/scene_lineage/etc. ──────────
def _scenelook_path(scene, episode="Ep1"):
    return OUT / f"{episode}_scenelook_scene{scene}.json"


def _scenelook_input_signature_server(scene, episode="Ep1"):
    """Mirrors cb_render._scenelook_input_signature exactly (deliberately duplicated, never
    imported — see this file's own standing convention). The plate's brief is a pure
    function of locations.json + style.txt — NEVER the storyboard — so this signature is
    what actually decides staleness now (2026-07-18 direct-input-lineage correction),
    replacing the old storyboard-md5 comparison below entirely."""
    import hashlib
    loc_path = ACTIVE_SHOW.canon_paths["locations"]
    style_path = ACTIVE_SHOW.resolve(ACTIVE_SHOW.profile.laws["style"], "laws.style")
    locs = json.loads(loc_path.read_text()) if loc_path.exists() else {}
    entry = (locs.get(episode) or {}).get(str(scene)) or {}
    style = style_path.read_text().strip() if style_path.exists() else ""
    parts = [style] if style else []
    for key in ("look", "lighting", "weather", "colorTemperature", "definingFeature"):
        v = (entry.get(key) or "").strip()
        if v:
            parts.append(v)
    brief = " ".join(parts)
    return {"briefHash": hashlib.sha256(brief.encode()).hexdigest(), "referenceHashes": {}}


def _scenelook_load_rec_server(scene, episode="Ep1"):
    """Mirrors cb_render._load_scenelook_rec's migration exactly: an old flat-shape sidecar
    ({'status','platePath','plateHash',...}) is read as {'approved','candidate','history'}
    in memory, never written back by a read. A legacy 'approved' entry with no recorded
    inputSignature is backfilled with the CURRENT signature — honest, since the plate's
    brief is a pure function of already-unchanged canon files."""
    sc_path = _scenelook_path(scene, episode)
    if not sc_path.exists():
        return {"approved": None, "candidate": None, "history": []}
    rec = json.loads(sc_path.read_text())
    if "approved" in rec or "candidate" in rec:
        return rec
    approved = None
    if rec.get("status") == "approved" and rec.get("platePath"):
        approved = {"path": rec["platePath"], "hash": rec.get("plateHash"),
                    "inputSignature": _scenelook_input_signature_server(scene, episode),
                    "approvedAt": rec.get("approvedAt"), "reviewedBy": rec.get("reviewedBy")}
    return {"approved": approved, "candidate": None, "history": list(rec.get("history") or [])}


def scenelook_status_server(scene, episode="Ep1"):
    """Return the engine's signed Scene Look state with servable media URLs.

    A current working anchor may feed the first keyframe without a fabricated human approval;
    stale candidates remain non-operational. Raw filesystem paths are never exposed.
    """
    # Use the engine's one authoritative state calculation. The former server-side mirror
    # drifted from the production rules and could make the UI disagree with paid generation.
    cb_render = _canonical_cb_render()
    cb_asset_registry.migrate_existing(episode)
    raw = cb_render.scenelook_status(scene, episode)
    approved, candidate, active = raw.get("approved"), raw.get("candidate"), raw.get("active")
    history = raw.get("history", [])

    def _as_url(entry):
        if not entry:
            return None
        return {**entry, "url": _url_from_abs(entry.get("path"))}

    if candidate:
        shown = active or candidate
        return {"status": raw.get("status", "awaiting"),
                "current": bool(raw.get("current")),
                "activeSource": raw.get("activeSource"),
                "candidateCurrent": bool(raw.get("candidateCurrent")),
                "approved": _as_url(approved),
                "candidate": _as_url(candidate), "history": history,
                # back-compat top-level fields some older UI reads may still expect
                "plateUrl": _as_url(shown)["url"] if shown else None,
                "plateHash": shown.get("hash") if shown else None}
    if approved:
        status = raw.get("status", "stale")
        au = _as_url(approved)
        return {"status": status, "current": bool(raw.get("current")), "approved": au,
                "candidate": None, "history": history,
                "plateUrl": au["url"], "plateHash": approved.get("hash")}
    status = raw.get("status", "none")
    return {"status": status, "current": False, "approved": None, "candidate": None,
            "history": history, "plateUrl": None, "plateHash": None}


def _load_director_package(scene, episode="Ep1"):
    path = _shot_pkg_path(scene, episode)
    if not path.exists():
        raise FileNotFoundError(f"no production package for {episode} scene {scene}")
    return json.loads(path.read_text()), path


def _director_session(scene, episode="Ep1", requested_shot_id=None):
    """Build the single Director response from authoritative zero-spend engine reads."""
    import cb_studio_director
    import cb_providers
    cb_render = _canonical_cb_render()
    cb_state = _canonical_cb_state()

    state = cb_state.production_state(scene, episode)
    provider_capabilities = cb_providers.capability_report()
    blockers = list(state.get("blockers") or [])
    if not provider_capabilities.get("selectionReady"):
        blockers.append({
            "code": "VIDEO_PROVIDER_NOT_QUALIFIED",
            "stage": "configuration",
            "shotId": None,
            "message": provider_capabilities.get("selectionError") or
                       "The selected video route is not qualified.",
            "action": "Select a verified production model or qualify the requested provider route.",
        })
    preflight = {
        "ok": not blockers,
        "zeroSpend": True,
        "episode": episode,
        "scene": str(scene),
        "blockers": blockers,
        "warnings": [],
        "productionInputs": {"look": None, "shots": {}},
        "providerCapabilities": provider_capabilities,
        "showProfile": SHOW_PROFILE_STATUS,
    }

    package = None
    media = {}
    try:
        package, _ = _load_director_package(scene, episode)
        media = shot_media_map(package, scene, episode)
    except (FileNotFoundError, OSError, ValueError, TypeError):
        package = None
        media = {}

    try:
        scene_look = scenelook_status_server(scene, episode) if package else {}
    except Exception:
        scene_look = {}

    # A stale scene handover must block new production, but it must never make existing
    # shot work disappear from the Director. Project the package's preserved shots through
    # the same read-only state calculator with package_current=False: every mutating action
    # remains disabled while approved frames, voices and takes stay visible for recovery.
    if package and not (state.get("shots") or []):
        try:
            preserved_shots = [
                cb_state._shot_state(
                    package, shot, scene, episode,
                    bool(scene_look.get("current")), False)
                for shot in cb_state._active_package_shots(package)
            ]
        except (OSError, ValueError, TypeError, KeyError):
            preserved_shots = []
        if preserved_shots:
            state = dict(state)
            state["shots"] = preserved_shots
            state["_per"] = preserved_shots
            state["preservedPackageView"] = True

    common = {
        "state": state,
        "preflight": preflight,
        "package": package,
        "media": media,
        "scene_look": scene_look,
        "jobs": _jobs_snapshot(),
        "requested_shot_id": requested_shot_id,
    }
    session = cb_studio_director.build_session(**common)
    animation_contract = None
    selected_id = session.get("selectedShotId")
    if selected_id and package:
        shot = next((item for item in (package.get("shots") or [])
                     if item.get("shotId") == selected_id), {})
        ledger = next((item for item in (package.get("continuityLedger") or [])
                       if item.get("shotId") == selected_id), {})
        current = next((item.get("current") or {} for item in (state.get("shots") or [])
                        if item.get("shotId") == selected_id), {})
        inputs = {}

        def current_output(stage):
            work = ((ledger.get("departmentWork") or {}).get(stage) or {})
            record = work.get("candidate") or work.get("approved") or {}
            return (record.get("output") or {}), (
                "prepared" if work.get("candidate") else "approved-legacy")

        if session.get("phase") == "keyframe" and current.get("cinematographyDirection"):
            output, source = current_output("cinematography")
            try:
                prompt = cb_render._compile_keyframe_integration_prompt(output, shot)
            except (cb_render.Refused, ValueError) as exc:
                blockers.append({
                    "code": "KEYFRAME_PROMPT_CONTRACT",
                    "stage": "keyframe",
                    "shotId": selected_id,
                    "message": str(exc),
                    "action": "Prepare and approve current Cinematography direction.",
                })
                preflight["ok"] = False
            else:
                inputs.update({
                    "keyframePrompt": prompt,
                    "keyframePromptHash": hashlib.sha256(prompt.encode()).hexdigest(),
                    "keyframePromptSource": source,
                    "keyframePromptHeadline": (
                        output.get("audienceRead") or output.get("composition")),
                })
        if session.get("phase") == "voice" and current.get("voiceDirection"):
            output, source = current_output("voice")
            direction_by_occurrence = {
                line.get("dialogueOccurrenceId"): line
                for line in (output.get("lines") or [])
            }
            try:
                provider_lines = cb_render._approved_voice_lines(package, shot)
            except (cb_render.Refused, ValueError) as exc:
                blockers.append({
                    "code": "VOICE_PROMPT_CONTRACT",
                    "stage": "voice",
                    "shotId": selected_id,
                    "message": str(exc),
                    "action": "Correct and prepare current Voice direction.",
                })
                preflight["ok"] = False
            else:
                inputs.update({
                    "voiceLines": [{
                        "speaker": line.get("speaker"),
                        "performedText": line.get("text"),
                        "dramaticIntention": (
                            direction_by_occurrence.get(line.get("dialogueOccurrenceId"), {})
                            .get("dramaticIntention")),
                    } for line in provider_lines],
                    "voiceDirectionSource": (
                        "human-working" if ledger.get("workingVoice") else source),
                })
        if inputs:
            preflight["productionInputs"]["shots"][selected_id] = inputs

    if selected_id and session.get("phase") in ("animation", "review", "final"):
        try:
            animation_contract = cb_render.check_seedance_structure(
                scene, selected_id, episode, log=lambda *_: None)
        except Exception as exc:
            animation_contract = {
                "verdict": "blocked", "blockers": [str(exc)], "warnings": [],
                "checks": {}, "finalPrompt": "",
            }
    session = cb_studio_director.build_session(
        **common, animation_contract=animation_contract)
    _expose_session_shot_media(session, media)
    workbench = _project_workbench_state(ACTIVE_PROJECT_ID, episode, scene)
    session["savedRetakeNotes"] = dict(workbench.get("retakeNotes") or {})
    return session


def _cached_director_session(scene, episode="Ep1", requested_shot_id=None):
    key = (str(episode), str(scene), str(requested_shot_id or ""))
    now = time.time()
    with _DIRECTOR_SESSION_CACHE_LOCK:
        cached = _DIRECTOR_SESSION_CACHE.get(key)
        if cached and now - cached["at"] < _DIRECTOR_SESSION_CACHE_TTL_SEC:
            return cached["session"]
    # Different Studio tabs can request different shots at once. The authoritative
    # build touches a large shared production graph, so only one uncached build may
    # run at a time. Fresh cached sessions remain lock-free and return immediately.
    with _DIRECTOR_SESSION_BUILD_LOCK:
        now = time.time()
        with _DIRECTOR_SESSION_CACHE_LOCK:
            cached = _DIRECTOR_SESSION_CACHE.get(key)
            if cached and now - cached["at"] < _DIRECTOR_SESSION_CACHE_TTL_SEC:
                return cached["session"]
        session = _director_session(scene, episode, requested_shot_id)
        with _DIRECTOR_SESSION_CACHE_LOCK:
            _DIRECTOR_SESSION_CACHE[key] = {"at": time.time(), "session": session}
        return session


def _director_board(episode="Ep1"):
    """Return the cross-scene decision queue without mutating production state."""
    import cb_intake

    roster = cb_intake.scene_roster(episode)
    scenes = []
    queue = []
    signoff_by_phase = {"keyframe": 1, "voice": 2, "animation": 3, "review": 3, "final": 3}
    for scene_info in roster.get("scenes") or []:
        scene = str(scene_info.get("sceneNumber"))
        package_path = _shot_pkg_path(scene, episode)
        card = {
            "scene": scene,
            "location": scene_info.get("location") or f"Scene {scene}",
            "time": scene_info.get("time") or "",
            "beatCount": scene_info.get("beatCount") or 0,
            "started": package_path.exists(),
            "status": "untouched",
            "statusLabel": "Not started",
            "nextLabel": "Start scene -> generate keyframes",
            "shotId": None,
            "signOff": 1,
        }
        if package_path.exists():
            package, _ = _load_director_package(scene, episode)
            shots = package.get("shots") or []
            shot_ids = [shot.get("shotId") for shot in shots if shot.get("shotId")]
            ledgers = {item.get("shotId"): item for item in package.get("continuityLedger") or []}
            projections = []
            for shot in shots:
                shot_id = shot.get("shotId")
                ledger = ledgers.get(shot_id) or {}
                keyframe_approved = bool((ledger.get("keyframeApproval") or {}).get("approved"))
                voice_approved = (bool((ledger.get("voiceApproval") or {}).get("approved")) or
                                  not bool(_CBR.cb_audio_authority.spoken_dialogue_lines(shot)))
                animation_approved = ledger.get("status") == "approved"
                if ledger.get("keyframeCandidate"):
                    phase, status, headline = "keyframe", "ready_to_review", "Keyframe waiting for your decision"
                elif not keyframe_approved and shot.get("sourceType") == "opener":
                    phase, status, headline = "keyframe", "ready_to_fire", "Create the shot keyframe"
                elif ledger.get("voPath") and not voice_approved:
                    phase, status, headline = "voice", "ready_to_review", "Voice waiting for your decision"
                elif not voice_approved:
                    phase, status, headline = "voice", "ready_to_fire", "Create the voice performance"
                elif ledger.get("status") == "candidates-pending":
                    phase, status, headline = "animation", "ready_to_review", "Animation waiting for your decision"
                elif ledger.get("pendingSpendAuth"):
                    phase, status, headline = "animation", "ready_to_review", "Render request waiting for approval"
                elif not animation_approved:
                    phase, status, headline = "animation", "ready_to_fire", "Prepare the 480p animation"
                else:
                    phase, status, headline = "final", "complete", "Shot complete"
                projections.append({"selectedShotId": shot_id, "phase": phase, "status": status,
                                    "headline": headline})
            active = next((item for item in projections if item["status"] == "ready_to_review"), None)
            active = active or next((item for item in projections if item["status"] != "complete"), None)
            active = active or (projections[0] if projections else {
                "selectedShotId": None, "phase": "story", "status": "blocked",
                "headline": "Scene package has no shots"})
            phase = active["phase"]
            status = active["status"]
            signoff = signoff_by_phase.get(phase, 1)
            card.update({
                "status": status,
                "statusLabel": (
                    "Decision waiting" if status == "ready_to_review" else
                    "Working" if status == "rendering" else
                    "Complete" if status == "complete" else
                    "Ready"
                ),
                "nextLabel": active.get("headline") or "Open scene",
                "shotId": active.get("selectedShotId"),
                "signOff": signoff,
                "phase": phase,
                "shotCount": len(shot_ids),
                "completeShots": sum(1 for item in projections if item["status"] == "complete"),
            })
            for item in projections:
                if item.get("status") != "ready_to_review":
                    continue
                item_phase = item.get("phase") or "keyframe"
                item_signoff = signoff_by_phase.get(item_phase, 1)
                queue.append({
                    "scene": scene,
                    "sceneName": card["location"],
                    "shotId": item.get("selectedShotId"),
                    "phase": item_phase,
                    "signOff": item_signoff,
                    "label": {1: "SEE", 2: "HEAR", 3: "WATCH"}[item_signoff],
                    "headline": item.get("headline") or "Decision waiting",
                })
        scenes.append(card)
    queue.sort(key=lambda item: (int(item["scene"]), item.get("shotId") or "", item["signOff"]))
    return {
        "episode": episode,
        "sceneCount": len(scenes),
        "scenes": scenes,
        "queue": queue,
        "nextDecision": queue[0] if queue else None,
        "zeroSpend": True,
    }


def _prewarm_director_session_cache():
    try:
        _cached_director_session("1", "Ep1", "S1.SH1A")
    except Exception as exc:
        print(f"DIRECTOR CACHE PREWARM WARNING - {exc}", flush=True)



# ── THE LEGACY PIPELINE IS GONE (Julian's destructive cutover, 2026-07-16) ────────────────────
# Every route of the old beat/gate pipeline returns 410 GONE — never a redirect, never another
# generator. The single production path is: Studio disclosure -> sealed request envelope ->
# spend approval -> cb_render candidate batch -> fal provider adapter (/api/shot-*).
LEGACY_GONE_ROUTES = ['/api/fire', '/api/retakes', '/api/retake-brief', '/api/retake-csv', '/api/export-storyboard', '/api/approve', '/api/unapprove', '/api/rebuild', '/api/set-master', '/api/clear-master', '/api/regen', '/api/gen-audio', '/api/gen-keyframe', '/api/render-beat', '/api/approve-beat', '/api/relay-prepare', '/api/relay-approve', '/api/director-eye', '/api/masters', '/api/keyframe-prompt', '/api/voice-prompt', '/api/beat-sound-brief', '/api/relay-state', '/api/keyframe-qa', '/api/craft-score', '/api/beat-prompt', '/api/beat-state', '/api/retake-log', '/api/continuity', '/api/pipeline']


def _legacy_gone(handler):
    path = handler.path.split("?")[0]
    for r in LEGACY_GONE_ROUTES:
        if path == r or path.startswith(r + "/"):
            handler._json(410, {"error": "GONE — the legacy pipeline was permanently removed "
                                          "(2026-07-16 cutover). Use the Shots pipeline "
                                          "(/api/shot-package, /api/shot-run)."})
            return True
    return False

def shot_run_job(cmd, scene, episode="Ep1", shot_id=None, correction=None,
                 candidates=None, spend_token=None, category=None, candidate=None,
                 dry_run=False, source_path=None, character=None, comparison_model_id=None,
                 comparison_run_id=None, start_sec=None, end_sec=None):
    """Map one validated shot-pipeline command onto the job runner. Argument order per cb_engine.py /
    cb_render.py's own CLIs (2026-07-16 spend-token contract — the approve-spend boolean is GONE):
      fire    -> cb_render.py fire <scene> <shotId> [episode] [--candidates N] [--spend-token <token>]
      next    -> cb_render.py next <scene> [episode] [--candidates N] [--spend-token <token>]
      approve -> cb_render.py approve <scene> <shotId> <candidateN> [episode]
      reject  -> cb_render.py reject <scene> <shotId> <correction> [--category X] [episode]
      others  -> cb_render.py <cmd> <scene> [episode]
    WITHOUT --spend-token, fire/next run fresh validation, print the SPEND DISCLOSURE, store the single-use
    token on the shot's ledger (pendingSpendAuth) and exit 1 REFUSED — the job reports "failed" with the
    disclosure in its log; that IS the designed step 1, not a malfunction. Re-posting with a mid-batch
    token resumes: only the missing candidates generate (ledger batch.status == "generating").
    Every value travels as its own argv element — never a shell string."""
    args = ["cb_render.py", cmd, str(scene)]
    if cmd in ("fire", "voice-shot", "build-keyframe", "keyframe", "approve", "reject", "override-model-limited", "approve-keyframe", "rescreen-keyframe", "reject-keyframe",
               "pose", "approve-pose", "reject-pose", "select-pose-upload",
               "select-upload", "select-library", "select-previous", "select-render-upload",
               "approve-voice", "reject-voice", "regen-voice",
               "edit", "approve-edit", "reject-edit"):
        args.append(str(shot_id))
    if cmd in ("pose", "approve-pose", "reject-pose", "select-pose-upload"):
        args.append(str(character))
    if cmd == "approve" and candidate is not None:
        args.append(str(candidate))
    if cmd == "reject":
        args.append(str(correction))
        if category:
            args += ["--category", str(category)]
    if cmd == "edit":
        args += [str(start_sec), str(end_sec), str(correction)]
    if cmd == "reject-edit":
        args.append(str(correction))
    if cmd == "override-model-limited":
        args.append(str(correction))
    if cmd == "reject-keyframe":
        args.append(str(correction))
    if cmd == "reject-pose":
        args.append(str(correction))
    if cmd == "reject-scenelook":
        args.append(str(correction))
    if cmd == "reject-voice":
        args.append(str(correction))
    if cmd == "reject-timing-slate":
        args.append(str(correction))
    if cmd in ("select-upload", "select-library", "select-render-upload"):
        # THE non-generation opening-frame sources (2026-07-18): the upload/library file's own
        # path travels as its own argv element, matching cb_render.py's own CLI shape
        # (select-upload/select-library <scene> <shotId> <path> [episode]) — never a shell string.
        args.append(str(source_path))
    if cmd == "select-pose-upload":
        args.append(str(source_path))
    if cmd in ("select-scenelook-upload", "select-scenelook-library"):
        # THE non-generation SCENE LOOK sources (2026-07-19 — "still not letting me upload a
        # library image, i select it then it wants to generate"): the scene-scoped mirror of
        # select-upload/select-library above — no shotId, so the path travels right after
        # scene, matching cb_render.py's own CLI shape (select-scenelook-upload/-library
        # <scene> <path> [episode]) — never a shell string.
        args.append(str(source_path))
    args.append(str(episode))
    if cmd == "scenelook" and source_path:
        # THE SCENE LOOK PROVIDER-ROUTING FIX (2026-07-19): an OPTIONAL, explicitly-selected
        # reference travels as its own trailing argv element — cb_render.py scenelook <scene>
        # <episode> [referencePath]; omitted entirely (the normal case) means no reference at
        # all, which now correctly routes to text-to-image rather than a guaranteed-422 edit call.
        args.append(str(source_path))
    if cmd in ("fire", "next", "edit"):
        if candidates is not None and cmd in ("fire", "next"):
            args += ["--candidates", str(candidates)]
        if spend_token:
            args += ["--spend-token", str(spend_token)]
        if dry_run:
            args += ["--dry-run"]      # sealed-envelope preview: no token issued, nothing stored
        if comparison_model_id:
            args += ["--comparison-model", str(comparison_model_id),
                     "--comparison-run-id", str(comparison_run_id)]
    label = "shot:" + cmd + ((":" + str(shot_id)) if shot_id else "")
    return _start(_jid(f"shot{cmd}_s{scene}"), label, scene, args)


class StoryboardApprovalRefused(RuntimeError):
    pass


def _snapshot_storyboard_handover(storyboard_path, episode, scene):
    """Promote scene-package storyboard snapshots without the legacy Creative Room mapper."""
    out_path = OUT / f"{episode}_scene{scene}_production_package.json"
    if not out_path.exists():
        raise StoryboardApprovalRefused(
            "REFUSED — production package is missing; rebuild Story & Direction")
    package, package_digest = cb_db.read_json_document(ROOT, out_path)
    source_storyboard = package.get("sourceStoryboard") or {}
    reviewed_path = pathlib.Path(storyboard_path).resolve()
    expected_rel = pathlib.Path("cb-output") / "creative" / f"{episode}_scene{scene}_storyboard.json"
    try:
        reviewed_rel = reviewed_path.relative_to(ROOT.resolve())
    except ValueError:
        reviewed_rel = None
    source_path_text = str(source_storyboard.get("path") or "")
    source_path = pathlib.Path(source_path_text)
    source_rel = pathlib.Path(source_path_text)
    if source_path.is_absolute():
        try:
            source_rel = source_path.resolve().relative_to(ROOT.resolve())
        except ValueError:
            source_rel = pathlib.Path(*source_path.parts[-3:])
    if reviewed_rel != expected_rel or source_rel != expected_rel:
        raise StoryboardApprovalRefused(
            "REFUSED — production package did not bind to the reviewed storyboard")
    storyboard, _ = cb_db.read_json_document(ROOT, storyboard_path)
    # A corrected downstream shot may legitimately have a newer storyboard signature.
    # Legacy marker retained for compatibility: production package source storyboard signature is stale.
    # Preserve the reviewed package and let the scoped refresh update provenance; do not
    # invalidate previously approved shots or route the user back to the whole episode.
    if not (package.get("validation") or {}).get("passed"):
        raise StoryboardApprovalRefused("REFUSED — production package validation failed")
    _sync_package_storyboard_provenance(package, storyboard_path, storyboard)
    cb_db.atomic_write_json(ROOT, out_path, package, expected_digest=package_digest)
    return {
        "revision": package.get("revision"),
        "path": str(out_path),
        "carriedForward": [],
        "reset": [shot.get("shotId") for shot in package.get("shots") or [] if shot.get("shotId")],
        "archivedPrevious": None,
    }


def _promote_approved_storyboard(path, ep, sc, package):
    """Compile an already-approved scene into production without recording a new approval."""
    signature_kind = ((package.get("inputSignature") or {}).get("kind") or "")
    if signature_kind == "scene-storyboard-snapshot":
        return _snapshot_storyboard_handover(path, ep, sc)

    import cb_handover
    shot_ids = [
        shot.get("shotId") for shot in (package.get("shots") or [])
        if shot.get("shotId")
    ]
    preview, _ = cb_handover.promote_to_canonical(
        str(path), sc, shot_ids, ep, dry_run=True, log=lambda *a, **k: None)
    if not (preview.get("validation") or {}).get("passed"):
        issues = [
            issue for issue in (preview.get("validation") or {}).get("issues", [])
            if issue.get("severity") == "ERROR"
        ]
        raise RuntimeError(
            "production handover validation failed" +
            (f": {issues[0].get('code')}" if issues else "")
        )
    promoted, archived = cb_handover.promote_to_canonical(
        str(path), sc, shot_ids, ep, dry_run=False, log=lambda *a, **k: None)
    # The canonical compiler may normalize operational storyboard metadata during the
    # handover. Bind the live package to the final on-disk approved storyboard bytes so
    # the UI cannot create a valid package and immediately classify it as stale.
    storyboard, _ = cb_db.read_json_document(ROOT, path)
    package_path = OUT / f"{ep}_scene{sc}_production_package.json"
    live_package, live_digest = cb_db.read_json_document(ROOT, package_path)
    _sync_package_storyboard_provenance(live_package, path, storyboard)
    cb_db.atomic_write_json(
        ROOT, package_path, live_package, expected_digest=live_digest)
    promoted = live_package
    return {
        "revision": promoted.get("revision"),
        "carriedForward": (promoted.get("handover") or {}).get(
            "carriedForwardUnchangedShots", []),
        "reset": (promoted.get("handover") or {}).get("resetChangedShots", []),
        "archivedPrevious": str(archived) if archived else None,
    }


def _ensure_storyboard_handover(d):
    """Repair a missing production handover from the current human-approved storyboard."""
    ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
    sc = str(d.get("scene", "")).strip()
    if not _SHOT_TOKEN.match(ep) or not _SHOT_TOKEN.match(sc):
        raise ValueError("episode and scene must be plain tokens")
    with cb_db.scene_lease(ROOT, ep, sc, "serve.storyboard-handover"):
        path = ROOT / "cb-output" / "creative" / f"{ep}_scene{sc}_storyboard.json"
        if not path.exists():
            raise FileNotFoundError("no storyboard")
        package, _ = cb_db.read_json_document(ROOT, path)
        if package.get("approvalState") != "approved":
            raise StoryboardApprovalRefused(
                "Scene Direction needs Julian's approval before Shot 1 can be prepared")
        try:
            handover = _carry_forward_unchanged_approved_scene(
                path, ep, sc, package)
            if handover is None:
                handover = _promote_approved_storyboard(path, ep, sc, package)
        except Exception as exc:
            raise StoryboardApprovalRefused(
                f"The approved Scene Direction could not be prepared for production: {exc}"
            ) from exc
        return {"ok": True, "handover": handover, "approvalPreserved": True}


def _storyboard_approval(d):
    """Apply a storyboard decision and its production handover under one scene lease."""
    ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
    sc = str(d.get("scene", "")).strip()
    if not _SHOT_TOKEN.match(ep) or not _SHOT_TOKEN.match(sc):
        raise ValueError("episode and scene must be plain tokens")
    target = str(d.get("target", "scene"))
    verdict = str(d.get("verdict", "approved"))
    note = str(d.get("note", "")).strip()
    stamp = {
        "state": verdict,
        "note": note,
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "by": str(d.get("by") or "Julian"),
    }

    with cb_db.scene_lease(ROOT, ep, sc, "serve.storyboard-approve"):
        path = ROOT / "cb-output" / "creative" / f"{ep}_scene{sc}_storyboard.json"
        if not path.exists():
            raise FileNotFoundError("no storyboard")
        original_bytes = path.read_bytes()
        package, original_digest = cb_db.read_json_document(ROOT, path)
        if target == "scene":
            package["approvalState"] = verdict
            package["humanNote"] = note
        else:
            for collection in ("beats", "shots"):
                for item in package.get(collection, []):
                    if item.get("beatId") == target or item.get("shotId") == target:
                        item["approvalState"] = verdict
                        item["humanNote"] = note
        package.setdefault("approvalLog", []).append({"target": target, **stamp})
        decision_digest = cb_db.atomic_write_json(
            ROOT, path, package, expected_digest=original_digest)

        handover = None
        if target == "scene" and verdict == "approved":
            try:
                handover = _promote_approved_storyboard(path, ep, sc, package)
            except Exception as exc:
                cb_db.atomic_write_bytes(
                    ROOT, path, original_bytes, expected_digest=decision_digest)
                raise StoryboardApprovalRefused(
                    f"Storyboard was not approved because production handover failed safely: {exc}"
                ) from exc

        learning = None
        try:
            import cb_learning
            learning = cb_learning.human_feedback(
                verdict, note, scene=sc,
                beat=target if ".B" in target and ".S" not in target else None,
                shot=target if ".SH" in target or ".S" in target else None,
                episode=ep, asset=path.name, by=stamp["by"])
            learning = {
                key: (value if key != "evidenceCaptured" else {
                    "evidenceId": value["evidenceId"], "outcome": value["outcome"]
                })
                for key, value in learning.items()
            }
        except Exception as exc:
            learning = {"captureError": str(exc)}
        return {"ok": True, "learning": learning, "handover": handover}


# ── STATIC FILE HARDENING (security) ──────────────────────────────────────────────────────────────────────────
# The studio serves files from the repo ROOT, so WITHOUT this guard a browser could read engine/.env (API keys),
# *.py source, *.bak snapshots, *.log, internal config/state, node_modules and audit/archive/unpack folders.
# Policy = ALLOW-LIST by approved ROOT + extension: everything is BLOCKED by default; a file is served ONLY if it
# sits under an approved root with an approved extension, OR is an explicitly-approved exact file. Blocked → 404
# (hides existence). STATIC-SERVING ONLY: every /api route is handled in do_GET/do_POST and returns before any
# static fall-through; do_GET/do_HEAD call _serve_static() directly (never super().do_GET()/do_HEAD()), and
# _serve_static's own _static_blocked(...) call (below) is the real, single chokepoint — corrected 2026-07-08
# (full-codebase audit) after finding a dead send_head() override that this comment used to describe as the
# chokepoint; it was never actually reachable and has been removed.
#
# Approved EXACT files the UI fetches by name (case-insensitive):
def _project_approved_files():
    """T44: every registered project's own characters.json / locked canon / show bible, derived from
    each projects/<id>/profile.json — never a hand-typed per-project list."""
    out = set()
    for pid in studio_profile.list_project_ids(ROOT):
        try:
            prof = studio_profile.load_show_profile(ROOT, pid)
        except studio_profile.ShowProfileError:
            continue
        for path in (prof.canon_paths.get("characters"), prof.canon_paths.get("lockedCanon"),
                     prof.show_bible_path):
            if path:
                out.add("/" + os.path.relpath(str(path), str(ROOT)).replace(os.sep, "/").lower())
    return out


_APPROVED_FILES = {
    "/cb-studio/app.html",                # the SPA entry
    "/cb-studio/director.html",           # outcome-first creative entry
    "/cb-studio/room.html",               # Studio room assistant entry
    "/cb-studio/board.html",              # Studio board / rough-cut entry
    "/engine/config/characters.json",     # compatibility link → the active project's canon (one release)
    "/crystal_bears_locked_canon.md",     # compatibility link → the active project's canon (one release)
} | _project_approved_files()
_MEDIA_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".ico",
              ".mp4", ".webm", ".mov", ".m4v", ".mp3", ".wav", ".m4a", ".ogg",
              ".csv", ".srt"}   # retake sheet (csv) + review-overlay labels (srt) download/serve
_IMG_EXT   = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
# Approved ROOTS (path-prefix → the extensions allowed under it). Nothing outside these is served.
_APPROVED_ROOTS = (
    ("/engine/media/",   _MEDIA_EXT),               # generated review media (keyframes, clips, voice)
    ("/cb-seed/assets/", _IMG_EXT),                 # character/location reference images (turnarounds, masters)
    ("/cb-output/",      {".json"}),                # output packages — FURTHER limited to *_beat_package.json (below)
    ("/cb-studio/data/", {".json", ".txt"}),        # registries (episodes/media-index/projects) + scripts the UI reads
    ("/cb-studio/",      {".css", ".js", ".ico"}),  # frontend assets, if any (app.html is an exact-approved file above)
    ("/projects/",       {".json", ".md", ".txt"} | _MEDIA_EXT),  # per-project scaffold (meta/characters/bible/episodes + its own assets/media)
)
# "projects-index.json" is retired/dead data (kept in the deny list defensively, costs nothing). "projects.json"
# is the LIVE project-registry filename (see the two real call sites reading it under cb-studio/data/) — it was
# missing from this list entirely (2026-07-08 full-codebase audit fix), meaning it was servable under the
# approved "/cb-studio/data/" root + .json extension, the exact "internal state / stale registry" class this
# list exists to refuse.
_DENY_NAMES = {"locked.json", "notes.json", "projects-index.json", "projects.json"}

def _static_blocked(urlpath):
    """True UNLESS this static path is explicitly approved (an approved exact file, OR an approved root + extension).
    Blocked by DEFAULT: all source folders, config/state files, docs, and any JSON/MD/TXT outside an approved root,
    plus all backup/temp/audit/archive folders, dotfiles and path traversal."""
    import urllib.parse
    p = urllib.parse.unquote(urllib.parse.urlparse(urlpath or "").path).split("#")[0]
    if not p.startswith("/"):
        p = "/" + p
    segs = [s for s in p.split("/") if s not in ("", ".")]
    if not segs:                              return True     # bare root / directory — no listing
    if any(s == ".." for s in segs):          return True     # path traversal
    if any(s.startswith(".") for s in segs):  return True     # dotfiles (.env, .git, .replit, .DS_Store)
    pl, name = p.lower(), segs[-1].lower()
    if name in _DENY_NAMES:                   return True     # state/stale registry, even if under an approved root
    if pl in _APPROVED_FILES:                 return False    # explicitly-approved exact file
    ext = os.path.splitext(name)[1]
    for root, exts in _APPROVED_ROOTS:
        if pl.startswith(root) and ext in exts:
            if root == "/cb-output/" and not name.endswith("_beat_package.json"):
                return True                                   # cb-output: ONLY the beat package the UI reads
            return False                                      # approved
    return True                                               # default: BLOCKED
# ──────────────────────────────────────────────────────────────────────────────────────────────────────────────

class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
            "media-src 'self' blob:; connect-src 'self'; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
        )
        super().end_headers()

    def _valid_host(self):
        raw = (self.headers.get("Host") or "").strip()
        try:
            parsed = urlsplit("//" + raw)
            host = (parsed.hostname or "").lower().rstrip(".")
            port = parsed.port
        except ValueError:
            return False
        expected_port = int(getattr(self.server, "server_port", PORT))
        if host in ("localhost", "127.0.0.1", "::1") and port in (None, expected_port):
            return True
        if not PUBLIC_HOST or not hmac.compare_digest(host, PUBLIC_HOST):
            return False
        return port == PUBLIC_PORT if PUBLIC_PORT is not None else port is None

    def _is_loopback_host(self):
        raw = (self.headers.get("Host") or "").strip()
        try:
            parsed = urlsplit("//" + raw)
            host = (parsed.hostname or "").lower().rstrip(".")
            port = parsed.port
        except ValueError:
            return False
        expected_port = int(getattr(self.server, "server_port", PORT))
        return host in ("localhost", "127.0.0.1", "::1") and port in (None, expected_port)

    def _has_session(self):
        try:
            cookie = SimpleCookie(self.headers.get("Cookie") or "")
            supplied = cookie.get(SESSION_COOKIE)
            return bool(supplied and hmac.compare_digest(supplied.value, SESSION_TOKEN))
        except Exception:
            return False

    def _issue_session_redirect(self, location):
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header(
            "Set-Cookie",
            f"{SESSION_COOKIE}={SESSION_TOKEN}; Path=/; HttpOnly; SameSite=Strict"
            "; Max-Age=2592000"
            + ("; Secure" if PUBLIC_ORIGIN else ""),
        )
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _deny(self, code, message):
        body = json.dumps({"error": message}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _authorize(self, allow_launch=False):
        if not self._valid_host():
            self._deny(421, "invalid local Host header")
            return False
        parsed = urlsplit(self.path)
        launch = (parse_qs(parsed.query).get("launchToken") or [None])[0]
        if launch is not None:
            if not allow_launch or parsed.path not in (
                    "/cb-studio/director.html", "/cb-studio/app.html",
                    "/cb-studio/room.html", "/cb-studio/board.html") or not hmac.compare_digest(
                    str(launch), LAUNCH_TOKEN):
                self._deny(401, "invalid Studio launch token")
                return False
            clean = [(key, value) for key, values in parse_qs(
                parsed.query, keep_blank_values=True).items() if key != "launchToken"
                     for value in values]
            location = parsed.path + (("?" + urlencode(clean)) if clean else "")
            self._issue_session_redirect(location)
            return False
        if (allow_launch and self.command in ("GET", "HEAD") and not PUBLIC_ORIGIN
                and not self._has_session()
                and parsed.path in (
                    "/cb-studio/director.html", "/cb-studio/app.html",
                    "/cb-studio/room.html", "/cb-studio/board.html")
                and self._is_loopback_host()):
            location = parsed.path + (("?" + parsed.query) if parsed.query else "")
            self._issue_session_redirect(location)
            return False
        if not self._has_session():
            self._deny(401, "Studio launch authentication required")
            return False
        return True

    def _valid_post_origin(self):
        origin = (self.headers.get("Origin") or "").rstrip("/")
        expected = f"http://{self.headers.get('Host')}".rstrip("/")
        if origin and hmac.compare_digest(origin, expected):
            return True
        return bool(PUBLIC_ORIGIN and origin and hmac.compare_digest(origin, PUBLIC_ORIGIN))

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            # A tab navigation can cancel an in-flight response. The request's durable
            # mutation is already complete; do not turn a client disconnect into a second
            # error response or a misleading failed Studio action.
            self.close_connection = True

    def _serve_static(self, head=False):
        """Range-aware static serving. SimpleHTTPRequestHandler sends the whole file with a 200 (no Range), so large
        clips can't stream or seek and Safari/WebKit won't play them at all — the cause of buffering / 'some don't load'.
        This honours HTTP byte ranges (206), so videos stream in chunks and seek, and (with the threaded server) many
        load at once. Security: same _static_blocked chokepoint first."""
        if _static_blocked(self.path):
            return self.send_error(404, "Not Found")
        path = self.translate_path(self.path)
        if os.path.isdir(path) or not os.path.isfile(path):
            return self.send_error(404, "Not Found")
        try:
            size = os.path.getsize(path); mtime = os.path.getmtime(path)
        except OSError:
            return self.send_error(404, "Not Found")
        # FRESHNESS: media is regenerated in place (a re-fired keyframe/clip keeps its filename), so the browser must
        # REVALIDATE, never serve a stale cached copy. no-cache = "check with the server first"; a 304 fast-path keeps
        # it cheap when nothing changed. This kills the "it hasn't changed" stale-image problem for good.
        ims = self.headers.get("If-Modified-Since")
        if ims and not self.headers.get("Range"):
            try:
                import email.utils
                _t = email.utils.parsedate_tz(ims)
                if _t and int(mtime) <= email.utils.mktime_tz(_t):
                    self.send_response(304)
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Last-Modified", self.date_time_string(int(mtime)))
                    self.end_headers(); return
            except Exception:
                pass
        try:
            f = open(path, "rb")
        except OSError:
            return self.send_error(404, "Not Found")
        ext = os.path.splitext(path)[1].lower()
        ctype = {".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime", ".m4v": "video/x-m4v",
                 ".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4", ".ogg": "audio/ogg"}.get(ext) \
                or (self.guess_type(path) or "application/octet-stream")
        try:
            start, end, partial = 0, size - 1, False
            rng = self.headers.get("Range")
            if rng:
                m = re.match(r"\s*bytes=(\d*)-(\d*)\s*$", rng)
                if m and (m.group(1) or m.group(2)):
                    if m.group(1) == "":
                        start = max(0, size - int(m.group(2)))
                    else:
                        start = int(m.group(1))
                        if m.group(2): end = min(int(m.group(2)), size - 1)
                    if start > end or start >= size:
                        self.send_response(416); self.send_header("Content-Range", f"bytes */{size}")
                        self.end_headers(); return
                    partial = True
            length = end - start + 1
            self.send_response(206 if partial else 200)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Last-Modified", self.date_time_string(int(mtime)))
            if partial:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            if head:
                return
            f.seek(start); remaining = length
            while remaining > 0:
                chunk = f.read(min(262144, remaining))
                if not chunk: break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    break
                remaining -= len(chunk)
        finally:
            f.close()

    @_tracked
    def do_HEAD(self):
        if not self._authorize(allow_launch=True):
            return
        return self._serve_static(head=True)

    @_tracked
    def do_GET(self):
        if not self._authorize(allow_launch=True):
            return
        if _legacy_gone(self):
            return
        if self.path == "/" or self.path == "":
            self.send_response(302)
            self.send_header("Location", "/cb-studio/director.html")
            self.end_headers()
            return
        if self.path == "/api/show-profile":
            return self._json(200, SHOW_PROFILE_STATUS)
        # [removed 2026-07-16 cutover: /api/pipeline — handled by the 410 gate above]
        if self.path.startswith("/api/learning"):
            # THE CREATIVE LEARNING SYSTEM, read-only view (2026-07-17): evidence counts,
            # patterns awaiting the user's decision, active human-approved principles,
            # and the improvement measures. Never mutates anything.
            try:
                import cb_learning
                self._json(200, {"metrics": cb_learning.metrics(),
                                   "patterns": cb_learning.patterns(),
                                   "activeMemory": cb_learning.active_memory()})
            except Exception as e:
                self._json(500, {"error": str(e)})
            return
        if self.path.startswith("/api/dailies"):
            # Compact dailies evidence and trends. Detailed Prompt Lab evidence remains
            # available separately; this endpoint is the only required human interaction.
            try:
                import cb_dailies
                self._json(200, {"ok": True, "rows": cb_dailies.rows(), "report": cb_dailies.report(), "zeroSpend": True})
            except Exception as e:
                self._json(500, {"error": str(e)})
            return
        if self.path.startswith("/api/storyboard"):
            # THE CREATIVE ROOM's storyboard packages (2026-07-16): read-only view of
            # cb-output/creative/. ?episode=Ep1[&scene=N] — scene omitted lists what exists.
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            ep = (q.get("episode") or ["Ep1"])[0]
            sc = (q.get("scene") or [None])[0]
            base = ROOT / "cb-output" / "creative"
            if sc:
                f = base / f"{ep}_scene{sc}_storyboard.json"
                if not f.exists():
                    self._json(404, {"error": f"no storyboard for scene {sc} yet"}); return
                self._json(200, json.load(open(f))); return
            vision = base / f"{ep}_episode_vision.json"
            scenes = sorted(x.name.split("_scene")[1].split("_")[0]
                             for x in base.glob(f"{ep}_scene*_storyboard.json"))
            self._json(200, {"episode": ep,
                              "vision": json.load(open(vision)) if vision.exists() else None,
                              "scenes": scenes}); return
        if self.path == "/api/jobs":
            # THE SHOT PIPELINE's own job feed (2026-07-16 cutover): the legacy /api/pipeline
            # route that incidentally carried JOBS is GONE; this is the clean replacement.
            self._json(200, {"jobs": _jobs_snapshot()}); return
        if self.path == "/api/studio-version":
            self._json(200, {"version": STUDIO_BUILD_VERSION}); return
        if self.path == "/api/health":
            return self._json(200, {"stale": _is_stale(), "started": _STARTED_FP,
                                    "current": _source_fingerprint(), "running": len(PROCS)})
        if self.path.startswith("/api/canon-lock"):
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            episode = (q.get("episode") or [None])[0]
            try:
                import cb_canon
                return self._json(200, cb_canon.status(episode or None, root=ROOT))
            except Exception as exc:
                return self._json(500, {"error": str(exc), "current": False,
                                        "episodeReady": False})
        if self.path == "/api/rates":
            # Read-only, zero-risk: exposes cb_costs.py's own RATES table so the UI's pre-generation cost
            # estimates come from the same single source of truth the real spend ledger uses, rather than a
            # second, hand-typed copy in JS that could silently drift. Never mutates anything; not a pricing
            # decision surface — billing_profile.json remains the actual confirmed-plan source for spend.
            try:
                import cb_costs
                self._json(200, {"rates": {k: {"usd": v[0], "unit": v[1], "confidence": v[2]}
                                            for k, v in cb_costs.RATES.items()},
                                  "updated": cb_costs.RATES_UPDATED})
            except Exception as e:
                self._json(500, {"error": str(e)})
            return
        # [removed 2026-07-16 cutover: /api/continuity — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/masters — handled by the 410 gate above]
        if self.path == "/api/loclib":
            manifest = {}
            mf = ASSETS / "locations" / "_manifest.json"
            try:
                if mf.exists():
                    manifest = json.loads(mf.read_text())
            except Exception:
                manifest = {}
            reuse = {}
            lf = CANON_CONFIG / "locations.json"
            try:
                if lf.exists():
                    locs = json.loads(lf.read_text())
                    block = locs.get("Ep1", {}) if isinstance(locs, dict) else {}
                    scene_loc = {}
                    if isinstance(block, dict):
                        for scene, sc in block.items():
                            lid = sc.get("locationId") if isinstance(sc, dict) else None
                            if lid:
                                scene_loc.setdefault(lid, []).append(scene)
                    elif isinstance(block, list):
                        for sc in block:
                            if not isinstance(sc, dict):
                                continue
                            lid = sc.get("locationId")
                            scn = sc.get("scene")
                            if lid and scn is not None:
                                scene_loc.setdefault(lid, []).append(scn)
                    for lid, scenes in scene_loc.items():
                        if len(scenes) >= 1:
                            reuse[lid] = scenes
            except Exception:
                reuse = {}
            # EVERY episode scene + its scene-shot plate (so the studio shows all scenes, not just approved ones)
            scenes = []
            try:
                locs2 = json.loads(lf.read_text()) if lf.exists() else {}
                block2 = locs2.get("Ep1", {}) if isinstance(locs2, dict) else {}
                if isinstance(block2, dict):
                    for scn, sc in sorted(block2.items(), key=lambda kv: int(kv[0]) if str(kv[0]).isdigit() else 999):
                        if not isinstance(sc, dict):
                            continue
                        plate = f"Ep1_S{scn}_plate.png"
                        configured_master = sc.get("master")
                        master_path = (
                            ROOT / str(configured_master or "").lstrip("/"))
                        master_path = master_path.resolve()
                        master_exists = bool(
                            configured_master and master_path.is_relative_to(ROOT) and
                            master_path.is_file())
                        scenes.append({"scene": scn, "name": sc.get("name", ""), "locationId": sc.get("locationId", ""),
                                       "location": sc.get("location", ""), "look": sc.get("look", ""),
                                       "time": sc.get("time", ""), "weather": sc.get("weather", ""),
                                       "master": configured_master if master_exists else None,
                                       "masterConfigured": configured_master,
                                       "masterMissing": bool(configured_master and not master_exists),
                                       "shots": sc.get("shots") or [],
                                       "plate": (plate if (MEDIA / plate).exists() else None)})
            except Exception:
                scenes = []
            # uploaded scene reference images on disk (so the studio surfaces every scene shot you've dropped in,
            # even ones not yet linked to a scene plate)
            refs = []
            try:
                ad = ASSETS
                paths = list((ad / "ep1").glob("CB_Scene_*")) + list(ad.glob("CB_*_plate.*"))
                for p in sorted(set(paths)):
                    if not p.is_file():
                        continue
                    nm = (p.stem.replace("CB_Scene_", "").replace("CB_", "").replace("_anchor", "")
                            .replace("_plate", "").replace("_", " ").strip())
                    refs.append({"file": os.path.relpath(str(p), str(ROOT)), "name": nm or p.stem})
            except Exception:
                refs = []
            return self._json(200, {"manifest": manifest, "reuse": reuse, "scenes": scenes, "uploadedRefs": refs})
        if self.path == "/api/houses":
            houses = []
            try:
                cf = CANON_CONFIG / "characters.json"
                cfg = json.loads(cf.read_text()) if cf.exists() else {}
                for char, v in cfg.items():
                    if not isinstance(v, dict):
                        continue
                    h = v.get("house")
                    if not isinstance(h, dict):
                        continue
                    houses.append({"character": char,
                                   "interior": h.get("interior"), "interiorMulticam": h.get("interiorMulticam"),
                                   "exterior": h.get("exterior"), "exteriorMulticam": h.get("exteriorMulticam"),
                                   "interiorDesc": h.get("interiorDesc"), "exteriorDesc": h.get("exteriorDesc")})
            except Exception:
                houses = []
            return self._json(200, {"houses": houses})
        if self.path == "/api/projects":
            projs = []
            try:
                pf = ROOT / "cb-studio" / "data" / "projects.json"
                if pf.exists():
                    d = json.loads(pf.read_text()); projs = d.get("projects", []) if isinstance(d, dict) else []
                for p in projs:
                    pid = p.get("id", "")
                    cfgbase = p.get("configBase") or ("projects/" + pid)
                    epfile = p.get("episodesFile") or ("projects/" + pid + "/episodes.json")
                    try:
                        epf = ROOT / epfile; ed = json.loads(epf.read_text()) if epf.exists() else []
                        p["episodeCount"] = len(ed) if isinstance(ed, list) else len(ed.get("episodes", []))
                    except Exception:
                        p["episodeCount"] = 0
                    try:
                        cf = ROOT / cfgbase / "characters.json"; cd = json.loads(cf.read_text()) if cf.exists() else {}
                        p["characterCount"] = len([k for k, v in cd.items()
                                                   if isinstance(v, dict) and not str(k).startswith("_")
                                                   and k != "sizeClasses"])
                    except Exception:
                        p["characterCount"] = 0
            except Exception:
                projs = []
            return self._json(200, {"projects": projs})
        if urlsplit(self.path).path == "/api/project-workbench-state":
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            project = (q.get("project") or [ACTIVE_PROJECT_ID])[0]
            ep = (q.get("episode") or ["Ep1"])[0]
            scene = (q.get("scene") or ["1"])[0]
            if not (_SHOT_TOKEN.match(project) and _SHOT_TOKEN.match(ep) and _SHOT_TOKEN.match(scene)):
                return self._json(400, {"error": "project, episode and scene must be plain tokens"})
            return self._json(200, _project_workbench_state(project, ep, scene))
        if self.path == "/api/reindex":
            reindex_media()
            return self._json(200, {"ok": True, "episodes": reindex_episodes()})
        # [removed 2026-07-16 cutover: /api/keyframe-prompt — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/voice-prompt — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/beat-sound-brief — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/relay-state — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/keyframe-qa — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/craft-score — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/beat-prompt — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/beat-state — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/retake-log — handled by the 410 gate above]
        if self.path.startswith("/api/departments"):
            # The actual people behind the existing production stages. Read-only: returns
            # their real SKILL.md load state and any awaiting/approved work from the existing
            # scene/shot ledger. It never runs a worker or calls a provider.
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            scene = (q.get("scene") or [""])[0]
            shot_id = (q.get("shotId") or q.get("shot") or [None])[0]
            stage = (q.get("stage") or [None])[0]
            ep = (q.get("episode") or ["Ep1"])[0]
            if (not scene or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(ep) or
                    (shot_id and not _SHOT_TOKEN.match(shot_id)) or
                    (stage and stage not in DEPARTMENT_STAGES)):
                return self._json(400, {"error": "valid scene, optional shotId/stage and episode required"})
            try:
                import cb_render as _CBR
                return self._json(200, _CBR.department_status(scene, shot_id, ep, stage))
            except _CBR.Refused as e:
                return self._json(400, {"error": str(e)})
            except Exception as e:
                return self._json(500, {"error": str(e)})
        if self.path.startswith("/api/story-intake-status"):
            # THE DIRECTOR'S SCRIPT INTAKE (2026-07-19): read-only status for the ONE
            # department stage that runs before any scene package exists — a genuinely
            # different scope from every other department (episode-wide, not scene+shot),
            # so it is deliberately its own read route rather than reusing
            # department_status(), which always requires a package to already exist.
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            ep = (q.get("episode") or ["Ep1"])[0]
            if not _SHOT_TOKEN.match(ep):
                return self._json(400, {"error": "valid episode required"})
            try:
                import cb_intake as _CBI
                return self._json(200, _CBI.intake_status(ep))
            except Exception as e:
                return self._json(500, {"error": str(e)})
        if self.path.startswith("/api/scene-roster"):
            # THE CANONICAL SCENE ROSTER (2026-07-19): the approved beat package is the ONLY
            # authority for which scenes exist, their order/numbers and headings — this is
            # deliberately NOT /api/loclib (that stays the persistent, cross-episode reusable
            # location-asset manifest and is never touched by or used to derive scene
            # existence). Read-only; scenes=[] until story intake has been approved.
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            ep = (q.get("episode") or ["Ep1"])[0]
            if not _SHOT_TOKEN.match(ep):
                return self._json(400, {"error": "valid episode required"})
            try:
                import cb_intake as _CBI
                return self._json(200, _CBI.scene_roster(ep))
            except Exception as e:
                return self._json(500, {"error": str(e)})
        if self.path.startswith("/api/director-board"):
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            ep = (q.get("episode") or ["Ep1"])[0]
            if not _SHOT_TOKEN.match(ep):
                return self._json(400, {"error": "valid episode required"})
            try:
                return self._json(200, _director_board(ep))
            except Exception as e:
                return self._json(500, {"error": str(e), "zeroSpend": True})
        if self.path.startswith("/api/rough-cut-draft"):
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            ep = (q.get("episode") or ["Ep1"])[0]
            scene = (q.get("scene") or [None])[0]
            if not _SHOT_TOKEN.match(ep) or (scene and not _SHOT_TOKEN.match(scene)):
                return self._json(400, {"error": "valid episode and scene required"})
            try:
                return self._json(200, rough_cut_projection(ep, scene))
            except Exception as e:
                return self._json(500, {"error": str(e)})
        if self.path.startswith("/api/production-preflight"):
            # One read-only, zero-spend report of every known blocker, evaluated before any
            # paid button so failures arrive together instead of one approval click at a time.
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            scene = (q.get("scene") or [""])[0]; ep = (q.get("episode") or ["Ep1"])[0]
            if not scene or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(ep):
                return self._json(400, {"error": "scene and episode must be plain tokens"})
            try:
                import cb_production_preflight
                return self._json(200, cb_production_preflight.production_preflight(scene, ep))
            except Exception as e:
                return self._json(400, {"error": str(e), "zeroSpend": True})
        if urlsplit(self.path).path == "/api/post-workspace":
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            ep = (q.get("episode") or ["Ep1"])[0]
            if not _SHOT_TOKEN.match(ep):
                return self._json(400, {"error": "episode must be a plain token"})
            try:
                import cb_post_workspace
                payload = cb_post_workspace.workspace(ep)
                payload["jobs"] = [
                    dict(job) for job in _jobs_snapshot().values()
                    if str(job.get("gate") or "").startswith("post:")
                ]
                return self._json(200, payload)
            except Exception as exc:
                return self._json(400, {"error": str(exc)})
        if urlsplit(self.path).path == "/api/director-session":
            # The outcome-first product surface. This is a read-only projection over the
            # same authoritative state, preflight, package and media evidence used by the
            # renderer. It creates no parallel approval policy and never calls a provider.
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            scene = (q.get("scene") or [""])[0]
            ep = (q.get("episode") or ["Ep1"])[0]
            shot_id = (q.get("shotId") or q.get("shot") or [None])[0]
            if (not scene or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(ep) or
                    (shot_id and not _SHOT_TOKEN.match(shot_id))):
                return self._json(400, {
                    "error": "scene, episode and optional shotId must be plain tokens",
                    "zeroSpend": True,
                })
            try:
                return self._json(200, _cached_director_session(scene, ep, shot_id))
            except Exception as exc:
                return self._json(400, {"error": str(exc), "zeroSpend": True})
        if self.path.startswith("/api/studio-agent"):
            # The creative front door is a strictly read-only HELP/PLAN projection. It
            # composes authoritative policy, quality and preflight evidence; it owns no
            # approval, mutation, job-runner or provider route of its own.
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            scene = (q.get("scene") or [""])[0]
            ep = (q.get("episode") or ["Ep1"])[0]
            shot_id = (q.get("shotId") or q.get("shot") or [None])[0]
            mode = (q.get("mode") or ["HELP"])[0].upper()
            if (not scene or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(ep) or
                    (shot_id and not _SHOT_TOKEN.match(shot_id)) or
                    mode not in ("HELP", "PLAN")):
                return self._json(400, {
                    "error": (
                        "scene, episode and optional shotId must be plain tokens; "
                        "mode must be HELP or PLAN"
                    ),
                    "zeroSpend": True,
                    "readOnly": True,
                })
            try:
                import cb_studio_agent
                return self._json(
                    200, cb_studio_agent.studio_agent_brief(
                        scene, ep, shot_id, mode=mode))
            except Exception as e:
                return self._json(400, {
                    "error": str(e),
                    "zeroSpend": True,
                    "readOnly": True,
                })
        if self.path.startswith("/api/director-chat"):
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            scene = (q.get("scene") or [""])[0]
            ep = (q.get("episode") or ["Ep1"])[0]
            shot_id = (q.get("shotId") or [None])[0]
            stage = (q.get("stage") or [""])[0]
            if (not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(ep) or
                    (shot_id and not _SHOT_TOKEN.match(shot_id)) or
                    not _SHOT_TOKEN.match(stage)):
                return self._json(400, {"error": "invalid Director chat scope"})
            try:
                import cb_director_chat
                return self._json(200, cb_director_chat.history(
                    ep, scene, shot_id, stage))
            except Exception as exc:
                return self._json(400, {"error": str(exc), "zeroMediaSpend": True})
        if self.path.startswith("/api/production-state"):
            # The one read-only approval/readiness policy used by the renderer, preflight and
            # Studio. The browser displays this document; it does not reconstruct approvals.
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            scene = (q.get("scene") or [""])[0]; ep = (q.get("episode") or ["Ep1"])[0]
            if not scene or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(ep):
                return self._json(400, {"error": "scene and episode must be plain tokens"})
            try:
                cb_state = _canonical_cb_state()
                return self._json(200, cb_state.production_state(scene, ep))
            except Exception as e:
                return self._json(400, {"error": str(e), "zeroSpend": True})
        if self.path.startswith("/api/shot-references"):
            # Read-only reference truth for the two image/video generation stages. Paths
            # remain private; only assets inside the approved static roots receive URLs.
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            scene = (q.get("scene") or [""])[0]
            sid = (q.get("shotId") or [""])[0]
            ep = (q.get("episode") or ["Ep1"])[0]
            if (not scene or not sid or not _SHOT_TOKEN.match(scene) or
                    not _SHOT_TOKEN.match(sid) or not _SHOT_TOKEN.match(ep)):
                return self._json(400, {
                    "error": "scene, shotId and episode must be plain tokens",
                    "zeroSpend": True, "readOnly": True,
                })
            _CBR = _canonical_cb_render()
            try:
                manifest = _CBR.shot_reference_manifest(scene, sid, ep)
                try:
                    pkg = json.loads(_shot_pkg_path(scene, ep).read_text())
                    shot = next((item for item in (pkg.get("shots") or [])
                                 if item.get("shotId") == sid), {})
                except Exception:
                    shot = {}

                def _norm_ref_name(value):
                    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold()
                                  .replace("'s", "s"))

                def _registry_reference_fallback():
                    items = cb_asset_registry.library_for_scene(ep, scene, sid)
                    chars = [str(c) for c in (shot.get("charactersInFrame") or []) if str(c).strip()]
                    refs = []
                    scene_items = [
                        item for item in items
                        if item.get("kind") in ("scene_plate", "opening_plate", "final_frame")
                        or re.search(r"\b(scene|plate|pier|cove|island|vision|environment)\b",
                                     f"{item.get('label') or ''} {item.get('role') or ''}",
                                     flags=re.I)
                    ]
                    for item in scene_items[:2]:
                        refs.append({
                            "slot": item.get("assetId"),
                            "role": item.get("label") or "Scene plate",
                            "label": item.get("label") or item.get("kind") or "Scene plate",
                            "kind": item.get("kind"),
                            "ready": bool(item.get("url")),
                            "status": item.get("status") or "approved",
                            "message": "Registry-bound scene/opening plate used for keyframe staging.",
                            "url": item.get("url"),
                        })
                    for char in chars:
                        target = _norm_ref_name(char)
                        candidates = []
                        for item in items:
                            if item.get("kind") != "reference_image":
                                continue
                            haystack = _norm_ref_name(" ".join(str(item.get(k) or "")
                                                               for k in ("label", "role", "path")))
                            if target and target not in haystack:
                                continue
                            text = f"{item.get('label') or ''} {item.get('role') or ''} {item.get('path') or ''}".casefold()
                            score = 0
                            if "final_turnarounds" in text:
                                score += 100
                            if "turnaround" in text:
                                score += 80
                            if "turn4" in text or "front-back" in text or "modelsheet" in text:
                                score += 40
                            if "expression" in text or "house" in text:
                                score -= 25
                            candidates.append((score, item))
                        if not candidates:
                            continue
                        item = sorted(candidates, key=lambda pair: pair[0], reverse=True)[0][1]
                        refs.append({
                            "slot": item.get("assetId"),
                            "role": f"{char} turnaround",
                            "label": item.get("label") or f"{char} turnaround",
                            "kind": item.get("kind"),
                            "ready": bool(item.get("url")),
                            "status": item.get("status") or "approved",
                            "message": "Registry-bound character turnaround used as identity authority.",
                            "url": item.get("url"),
                            "identity": {"intactTurnaround": True},
                        })
                    return refs

                for stage_name in ("keyframe", "animation"):
                    stage = manifest.get(stage_name) or {}
                    for item in stage.get("references") or []:
                        path = item.pop("path", None)
                        item["url"] = _url_from_reference(path)
                        if item.get("ready") and not item["url"]:
                            item.update({
                                "ready": False,
                                "status": "unavailable",
                                "message": "Reference is outside the Studio's approved asset library.",
                            })
                    stage["ready"] = bool(stage.get("ready")) and all(
                        item.get("ready") for item in stage.get("references") or [])
                    if not stage.get("references"):
                        fallback_refs = _registry_reference_fallback()
                        stage["references"] = fallback_refs
                        stage["ready"] = bool(fallback_refs) and all(
                            item.get("ready") for item in fallback_refs)
                        stage["reason"] = (
                            "Using registry-bound shot references because the compiled "
                            "provider manifest has not emitted reference records yet."
                        )
                for control in (manifest.get("technicalControls") or {}).values():
                    path = control.pop("path", None)
                    control["url"] = _url_from_reference(path)
                integration = manifest.get("posedIntegration") or {}
                integration_path = integration.pop("path", None)
                integration["url"] = _url_from_reference(integration_path)
                for item in (manifest.get("posePreparation") or {}).get("items") or []:
                    approved_path = item.pop("approvedPath", None)
                    qualified_path = item.pop("qualifiedPath", None)
                    candidate_path = item.pop("candidatePath", None)
                    item["approvedUrl"] = _url_from_reference(approved_path)
                    item["qualifiedUrl"] = _url_from_reference(qualified_path)
                    item["candidateUrl"] = _url_from_reference(candidate_path)
                return self._json(200, manifest)
            except _CBR.Refused as exc:
                return self._json(409, {
                    "error": str(exc), "zeroSpend": True, "readOnly": True})
            except Exception as exc:
                return self._json(400, {
                    "error": str(exc), "zeroSpend": True, "readOnly": True})
        if self.path.startswith("/api/shot-package"):
            # THE SHOT PIPELINE (additive, 2026-07-16): read-only — the production package cb_engine.py
            # compiled + validated, plus a server-computed media-existence map (shot_media_map above).
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            scene = (q.get("scene") or [""])[0]; ep = (q.get("episode") or ["Ep1"])[0]
            if not scene or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(ep):
                return self._json(400, {"error": "scene (and optional episode) required as plain tokens, "
                                                 "e.g. /api/shot-package?scene=1&episode=Ep1"})
            p = _shot_pkg_path(scene, ep)
            if not p.exists():
                return self._json(404, {"error": f"no production package for {ep} scene {scene} "
                                                 f"({p.name}) — approve the storyboard to hand it to production"})
            try:
                pkg = json.loads(p.read_text())
            except Exception as e:
                return self._json(400, {"error": f"package unreadable: {e}"})
            try:
                cb_state = _canonical_cb_state()
                production_state = cb_state.production_state(scene, ep)
            except Exception as exc:
                production_state = {"error": str(exc)}
            try:
                import cb_production_preflight
                preflight = cb_production_preflight.production_preflight(
                    scene, ep, state=production_state)
            except Exception as exc:
                preflight = {"error": str(exc), "zeroSpend": True}
            return self._json(200, {"package": pkg, "media": shot_media_map(pkg, scene, ep),
                                    "productionState": production_state,
                                    "preflight": preflight, "file": p.name})
        if self.path.startswith("/api/shot-fire-readiness"):
            # One zero-spend WATCH preflight for the human corridor. Fire repeats every
            # protection authoritatively; this read-only check prevents deterministic
            # package/voice/timing failures from first appearing as failed generation jobs.
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            scene = (q.get("scene") or [""])[0]
            ep = (q.get("episode") or ["Ep1"])[0]
            shot_id = (q.get("shotId") or [""])[0]
            if (not scene or not shot_id or not _SHOT_TOKEN.match(scene) or
                    not _SHOT_TOKEN.match(ep) or not _SHOT_TOKEN.match(shot_id)):
                return self._json(400, {"ready": False, "error": "scene, episode and shotId are required"})
            _CBR = _canonical_cb_render()
            try:
                pkg, _ = _CBR.load_pkg(scene, ep)
                shot = _CBR._shot(pkg, shot_id)
                ledger = _CBR._ledger(pkg, shot_id)
                _CBR._require_valid(pkg)
                _CBR._require_current_lineage(pkg, scene, ep)
                _CBR._fresh_validation(pkg, ep, shot_id)
                budget = _CBR._performance_budget_report(
                    _CBR._shot_creative_contract_view(pkg, shot, scene, ep), ledger)
                if not budget.get("ready"):
                    raise _CBR.Refused("The approved performance does not fit this shot's timing budget.")
                if _CBR.cb_audio_authority.spoken_dialogue_lines(shot):
                    voice = _CBR._voice_approval_status(pkg, shot)
                    if not voice.get("current"):
                        raise _CBR.Refused("Approve the current HEAR performance before rendering.")
                return self._json(200, {"ready": True, "zeroSpend": True,
                                        "nextAction": "Review cost and Fire"})
            except _CBR.Refused as exc:
                return self._json(200, {"ready": False, "zeroSpend": True,
                                        "nextAction": "Resolve the current production input",
                                        "message": str(exc)})
            except Exception:
                return self._json(200, {"ready": False, "zeroSpend": True,
                                        "nextAction": "Refresh the scene package",
                                        "message": "StudioAI could not verify the current WATCH package."})
        if self.path == "/api/scenelook" or self.path.startswith("/api/scenelook?"):
            # THE SCENE LOOK GATE (additive, 2026-07-18): read-only status — never writes,
            # never assumes a file's mere presence means approval (scenelook_status_server).
            # (2026-07-19 routing fix: was a bare startswith("/api/scenelook"), which also
            # matched /api/scenelook-library — a real prefix collision that silently shadowed
            # the newer, more specific route below with this status endpoint's own response
            # shape. Narrowed to an exact match or a real query string on this exact path.)
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            scene = (q.get("scene") or [""])[0]; ep = (q.get("episode") or ["Ep1"])[0]
            if not scene or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(ep):
                return self._json(400, {"error": "scene (and optional episode) required as plain tokens, "
                                                 "e.g. /api/scenelook?scene=1&episode=Ep1"})
            return self._json(200, scenelook_status_server(scene, ep))
        if self.path.startswith("/api/shot-reassess"):
            # DIRECT-INPUT LINEAGE, READ-ONLY, ZERO SPEND (2026-07-18 production-safety
            # directive, item 3/4): for every opener shot in the scene, compares its
            # existing keyframe candidate/approval's recorded input signature against what
            # those SAME inputs (its own card, the approved plate, its own references, the
            # compiled brief, model/settings) resolve to RIGHT NOW — never the whole
            # storyboard/package md5. This is the one place engine code is imported directly
            # rather than mirrored (unlike GATE_SEQ/scene_lineage/scenelook_status_server
            # above) — reassess_keyframe is read-only and never touches cb_gen, so importing
            # it is safe; duplicating its several helper functions here would not be.
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            scene = (q.get("scene") or [""])[0]; ep = (q.get("episode") or ["Ep1"])[0]
            if not scene or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(ep):
                return self._json(400, {"error": "scene (and optional episode) required as plain tokens, "
                                                 "e.g. /api/shot-reassess?scene=1&episode=Ep1"})
            p = _shot_pkg_path(scene, ep)
            if not p.exists():
                return self._json(200, {"shots": {}})
            try:
                pkg = json.loads(p.read_text())
            except Exception as e:
                return self._json(400, {"error": f"package unreadable: {e}"})
            if str(CBGEN) not in sys.path:
                sys.path.insert(0, str(CBGEN))
            import cb_render as _CBR
            out = {}
            for s in pkg.get("shots") or []:
                sid = s.get("shotId")
                if not sid or s.get("sourceType") != "opener":
                    continue
                try:
                    r = _CBR.reassess_keyframe(scene, sid, ep)
                    out[sid] = {"verdict": r["verdict"], "changed": r["changed"]}
                except Exception as e:
                    out[sid] = {"verdict": "error", "changed": [], "error": str(e)[:200]}
            return self._json(200, {"shots": out})
        if self.path.startswith("/api/shot-keyframe-library"):
            # THE OPENING-FRAME LIBRARY/HISTORY, READ-ONLY, ZERO SPEND (2026-07-18, Julian's
            # source-choice directive): every prior opening-frame artefact for ONE shot the
            # human may deliberately re-select — the currently-pending candidate (so it's
            # never lost the moment a fresh source-choice screen opens), the currently-
            # approved keyframe, every rejected candidate, every superseded approval. Listing
            # never mutates anything; re-selecting a listed item is a separate, explicit
            # select-library action. Imports cb_render directly (read-only, same precedent as
            # /api/shot-reassess above).
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            scene = (q.get("scene") or [""])[0]; sid = (q.get("shotId") or [""])[0]
            ep = (q.get("episode") or ["Ep1"])[0]
            if not scene or not sid or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(sid) \
               or not _SHOT_TOKEN.match(ep):
                return self._json(400, {"error": "scene, shotId (and optional episode) required as plain "
                                                 "tokens, e.g. /api/shot-keyframe-library?scene=1&shotId=1.B1.S1&episode=Ep1"})
            try:
                cb_asset_registry.migrate_existing(ep)
                items = cb_asset_registry.library_for_scene(ep, scene, sid)
            except Exception as e:
                return self._json(400, {"error": str(e)})
            out = [{"path": it["path"], "url": it.get("url"), "at": it.get("registeredAt"),
                    "outcome": it.get("status"), "note": it.get("label"),
                    "kind": it.get("kind"), "assetId": it.get("assetId")}
                   for it in items if it.get("url")]
            return self._json(200, {"items": out})
        if self.path.startswith("/api/scenelook-library"):
            # THE SCENE LOOK REFERENCE LIBRARY, READ-ONLY, ZERO SPEND (2026-07-19 UX fix —
            # exposing the button, not a redesign): every prior Scene Look artefact for ONE
            # scene the human may deliberately pick as a REFERENCE for a fresh generation.
            # Unlike /api/shot-keyframe-library's items (which become the candidate
            # directly), a picked item here is always fed to the 'scenelook' cmd's
            # sourcePath — a real generate_scenelook_plate call still fires. Same
            # direct-import, read-only precedent as /api/shot-keyframe-library above.
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            scene = (q.get("scene") or [""])[0]
            ep = (q.get("episode") or ["Ep1"])[0]
            if not scene or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(ep):
                return self._json(400, {"error": "scene (and optional episode) required as plain "
                                                 "tokens, e.g. /api/scenelook-library?scene=1&episode=Ep1"})
            try:
                cb_asset_registry.migrate_existing(ep)
                items = cb_asset_registry.library_for_scene(ep, scene)
            except Exception as e:
                return self._json(400, {"error": str(e)})
            out = [{"path": it["path"], "url": it.get("url"), "at": it.get("registeredAt"),
                    "outcome": it.get("status"), "note": it.get("label"),
                    "kind": it.get("kind"), "assetId": it.get("assetId")}
                   for it in items if it.get("url")]
            return self._json(200, {"items": out})
        if self.path.startswith("/api/project-asset-library"):
            # One frontend-readable view of the project asset registry. The UI may
            # display friendly labels, but selection/copy must use assetId/path from
            # this resolver, not hardcoded card names.
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            ep = (q.get("episode") or ["Ep1"])[0]
            scene = (q.get("scene") or ["*"])[0]
            if not _SHOT_TOKEN.match(ep) or (scene != "*" and not _SHOT_TOKEN.match(scene)):
                return self._json(400, {"error": "episode and scene must be plain tokens"})
            try:
                cb_asset_registry.migrate_existing(ep)
                items = cb_asset_registry.library_for_scene(ep, scene) if scene != "*" else cb_asset_registry.resolve_assets(ep, "*")

                def normalised(item):
                    label = str(item.get("label") or item.get("role") or item.get("assetId") or "Asset")
                    role = str(item.get("role") or "")
                    path = str(item.get("path") or "")
                    library_group = str((item.get("metadata") or {}).get("libraryGroup") or "")
                    if library_group in {"characters", "scenes", "props"}:
                        group = library_group
                    else:
                        group = ""
                    haystack = " ".join([label, role, path]).casefold()
                    if not group and ("/characters/" in haystack or "final_turnarounds" in haystack or any(
                        token in haystack for token in ("turnaround", "turn4", "front-back", "modelsheet", "refsheet")
                    )):
                        group = "characters"
                    elif not group and ("/locations/" in haystack or "/houses/" in haystack or any(
                        token in haystack for token in ("scene", "plate", "pier", "cove", "rainforest", "island", "house", "sanctuary", "meadow")
                    )):
                        group = "scenes"
                    elif not group and any(token in haystack for token in ("wristband", "pendant", "bowl", "wand", "satchel", "sailboat", "net", "prop")):
                        group = "props"
                    elif not group:
                        group = "references"
                    scene_priority = {
                        "scene_plate": 0,
                        "opening_plate": 1,
                        "final_frame": 2,
                        "keyframe": 3,
                    }.get(str(item.get("kind") or ""), 9)
                    if group == "scenes" and str(item.get("scene")) == scene:
                        scene_priority -= 4
                    if group == "scenes" and str(item.get("kind") or "") == "reference_image":
                        scene_priority += 8
                    return {
                        "assetId": item.get("assetId"),
                        "group": group,
                        "kind": item.get("kind"),
                        "label": label,
                        "role": role,
                        "status": item.get("status") or "approved",
                        "path": path,
                        "url": item.get("url"),
                        "scene": item.get("scene"),
                        "shotId": item.get("shotId"),
                        "source": item.get("source"),
                        "metadata": item.get("metadata") or {},
                        "registeredAt": item.get("registeredAt"),
                        "priority": scene_priority,
                    }

                grouped = {"characters": [], "scenes": [], "props": [], "references": []}
                seen = set()
                for item in items:
                    if not item.get("url"):
                        continue
                    rec = normalised(item)
                    key = rec["url"] if rec["group"] == "scenes" else rec["assetId"] or rec["path"]
                    if not key or key in seen:
                        continue
                    seen.add(key)
                    grouped[rec["group"]].append(rec)
                for values in grouped.values():
                    values.sort(key=lambda r: (r.get("priority", 9), r.get("label") or "", r.get("path") or ""))
                return self._json(200, {"episode": ep, "scene": scene, "groups": grouped})
            except Exception as e:
                return self._json(400, {"error": str(e)})
        # ── CONTAINED CREATIVE CONTROLS — Voice/Animation working versions + the free
        # structure check (2026-07-19, Julian's directive). All four are READ-ONLY, ZERO
        # COST, direct in-process reads (same precedent as /api/shot-reassess and
        # /api/shot-keyframe-library above — cb_render's own functions already guarantee
        # no cb_gen call happens on a read).
        if self.path.startswith("/api/shot-voice-status") or self.path.startswith("/api/shot-seedance-status") \
           or self.path.startswith("/api/shot-check-structure"):
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            scene = (q.get("scene") or [""])[0]; sid = (q.get("shotId") or [""])[0]
            ep = (q.get("episode") or ["Ep1"])[0]
            if not scene or not sid or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(sid) \
               or not _SHOT_TOKEN.match(ep):
                return self._json(400, {"error": "scene, shotId (and optional episode) required as plain tokens"})
            if str(CBGEN) not in sys.path:
                sys.path.insert(0, str(CBGEN))
            import cb_render as _CBR
            try:
                if self.path.startswith("/api/shot-voice-status"):
                    status = _CBR.voice_performance_status(scene, sid, ep)
                    try:
                        pkg, _ = _CBR.load_pkg(scene, ep)
                        led = next((item for item in (pkg.get("continuityLedger") or [])
                                    if item.get("shotId") == sid), {})
                        status["takeUrl"] = _url_from_abs(led.get("voPath"))
                        auditions = status.get("auditions") or {}
                        for candidate in auditions.get("candidates") or []:
                            candidate["url"] = _url_from_abs(candidate.get("path"))
                    except Exception:
                        status["takeUrl"] = None
                    return self._json(200, status)
                if self.path.startswith("/api/shot-seedance-status"):
                    return self._json(200, _CBR.seedance_working_status(scene, sid, ep))
                return self._json(200, _CBR.check_seedance_structure(scene, sid, ep))
            except _CBR.Refused as e:
                return self._json(400, {"error": str(e)})
            except Exception as e:
                return self._json(400, {"error": str(e)})
        if self.path.startswith("/api/shot-readback"):
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            scene = (q.get("scene") or [""])[0]
            sid = (q.get("shotId") or [""])[0]
            ep = (q.get("episode") or ["Ep1"])[0]
            if (not scene or not sid or not _SHOT_TOKEN.match(scene) or
                    not _SHOT_TOKEN.match(sid) or not _SHOT_TOKEN.match(ep)):
                return self._json(400, {
                    "error": "scene, shotId (and optional episode) required as plain tokens"
                })
            if str(CBGEN) not in sys.path:
                sys.path.insert(0, str(CBGEN))
            import cb_render as _CBR
            try:
                return self._json(200, _CBR.prompt_readback(scene, sid, ep))
            except _CBR.Refused as e:
                return self._json(409, {"error": str(e)})
            except Exception as e:
                return self._json(400, {"error": str(e)})
        if urlsplit(self.path).path == "/api/prompt-lab":
            # Deterministic prompt analysis plus immutable human-rating history. Read-only,
            # zero spend: no LLM or media provider is reachable from prompt_lab_status().
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            scene = (q.get("scene") or [""])[0]
            sid = (q.get("shotId") or [""])[0]
            ep = (q.get("episode") or ["Ep1"])[0]
            artifact_type = (q.get("artifactType") or [""])[0]
            candidate_id = (q.get("candidateId") or [None])[0]
            if (not scene or not sid or not _SHOT_TOKEN.match(scene) or
                    not _SHOT_TOKEN.match(sid) or not _SHOT_TOKEN.match(ep) or
                    artifact_type not in ("keyframe", "animation") or
                    (candidate_id and not _SHOT_TOKEN.match(candidate_id))):
                return self._json(400, {
                    "error": "valid scene, shotId, artifactType and optional candidateId required"
                })
            if str(CBGEN) not in sys.path:
                sys.path.insert(0, str(CBGEN))
            import cb_render as _CBR
            try:
                return self._json(200, _CBR.prompt_lab_status(
                    scene, sid, artifact_type, ep, candidate_id=candidate_id))
            except _CBR.Refused as e:
                return self._json(409, {"error": str(e), "zeroSpend": True})
            except Exception as e:
                return self._json(400, {"error": str(e), "zeroSpend": True})
        static_path = urlsplit(self.path).path
        if static_path == "/cb-studio/data/media-index.json":
            reindex_media()
        elif static_path == "/cb-studio/data/episodes.json":
            reindex_episodes()
        return self._serve_static()       # range-aware (video streams + seeks), not the no-Range super().do_GET()

    def _body(self):
        n = _validated_content_length(self.headers)
        payload = self.rfile.read(n)
        if len(payload) != n:
            raise ValueError("request body ended before Content-Length bytes were received")
        return json.loads(payload or b"{}")

    @_tracked
    def do_POST(self):
        if not self._authorize():
            return
        if not self._valid_post_origin():
            self._deny(403, "same-origin POST required")
            return
        try:
            _validated_content_length(self.headers)
        except RequestTooLarge as exc:
            self._deny(413, str(exc))
            return
        except ValueError as exc:
            self._deny(400, str(exc))
            return
        if _legacy_gone(self):
            return
        if self.path == "/api/write":
            try:
                d = self._body(); seed = d.get("seed") or {}; episode = d.get("episode", "Ep1")
                self._json(200, {"ok": True, "jobId": write_script(seed, episode)})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        # [removed 2026-07-16 cutover: /api/fire — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/retakes — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/retake-brief — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/retake-csv — handled by the 410 gate above]
        if self.path == "/api/stop":
            try:
                d = self._body(); jid = d.get("jobId")
                stopped = [jid] if (jid and stop_job(jid)) else ([] if jid else stop_all())
                self._json(200, {"ok": True, "stopped": stopped, "jobs": JOBS})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/rough-cut-draft":
            try:
                import cb_rough_cut
                d = self._body()
                episode = str(d.get("episode") or "Ep1")
                shot_id = str(d.get("shotId") or "")
                action = str(d.get("action") or "add")
                scene = str(d.get("scene") or "")
                if not _SHOT_TOKEN.match(episode):
                    raise ValueError("valid episode required")
                if action == "add":
                    if not _SHOT_TOKEN.match(shot_id):
                        raise ValueError("valid shotId required")
                    cb_rough_cut.add_shot(episode, shot_id)
                elif action == "remove":
                    if not _SHOT_TOKEN.match(shot_id):
                        raise ValueError("valid shotId required")
                    cb_rough_cut.remove_shot(episode, shot_id)
                elif action in ("save-scene", "confirm-scene"):
                    if not _SHOT_TOKEN.match(scene):
                        raise ValueError("valid scene required")
                    cb_rough_cut.save_scene_cut(
                        episode, scene, d.get("sequence"), confirm=action == "confirm-scene")
                else:
                    raise ValueError("action must be add, remove, save-scene or confirm-scene")
                self._json(200, rough_cut_projection(
                    episode, scene if action.endswith("-scene") else None))
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/room-chat":
            try:
                self._json(200, _anthropic_room_chat(self._body()))
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/project-workbench-state":
            try:
                d = self._body()
                project = str(d.get("project") or ACTIVE_PROJECT_ID)
                episode = str(d.get("episode") or "Ep1")
                scene = str(d.get("scene") or "1")
                if not (_SHOT_TOKEN.match(project) and _SHOT_TOKEN.match(episode) and _SHOT_TOKEN.match(scene)):
                    raise ValueError("project, episode and scene must be plain tokens")
                self._json(200, {"ok": True, "state": _save_project_workbench_state(d)})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        # [removed 2026-07-16 cutover: /api/export-storyboard — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/approve — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/unapprove — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/rebuild — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/set-master — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/clear-master — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/regen — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/gen-audio — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/gen-keyframe — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/render-beat — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/approve-beat — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/relay-prepare — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/relay-approve — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/director-eye — handled by the 410 gate above]
        # [removed 2026-07-16 cutover: /api/masters — handled by the 410 gate above]
        if self.path == "/api/episode":
            try:
                # FIXED 2026-07-12 (full-codebase audit continued): this handler re-implemented _body()'s exact
                # Content-Length/json.loads logic inline instead of calling the shared method every other POST
                # handler in this class already uses — a future hardening of _body() (a size cap, chunked-
                # encoding support, a clearer malformed-header error) would silently never apply to episode
                # uploads. Delegate instead.
                data = self._body()
                num = int(data.get("number"))
                title = (data.get("title") or "").strip() or f"Episode {num}"
                script = data.get("script") or ""
                if data.get("docData"):   # an uploaded script document — extract its text
                    script = extract_doc_text(data["docData"], data.get("docName", "")) or script
                current = SCRIPT_STORE.store(
                    f"Ep{num}", script, title,
                    source_name=str(data.get("docName") or "pasted-script"),
                    activated_by=str(data.get("by") or "Julian"),
                )
                fname = current["displayFile"]
                eps = reindex_episodes()
                episode = f"Ep{num}"
                import cb_intake as _CBI
                direction_status = _CBI.intake_status(episode)
                direction_job = None
                if not direction_status.get("canonicalCurrent"):
                    direction_job = _start(
                        _jid(f"storyintake_{episode}"), "storyintake", "-",
                        ["cb_intake.py", "run", episode])
                self._json(200, {"ok": True, "script": fname,
                                  "scriptVersionId": current["scriptVersionId"],
                                  "directionPreparationJobId": direction_job,
                                  "directionPreparation": "automatic",
                                  "episodes": eps})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/episode-rename":
            # RENAME an episode's title AFTER saving — no re-upload. The number is the stable key; only the title
            # (and the title-slug in the script + package filenames, and the package "title" field) changes.
            try:
                d = self._body()
                num = int(d.get("number"))
                title = (d.get("title") or "").strip()
                if not title:
                    raise ValueError("a new name is required")
                newslug = slug(title)
                before = SCRIPT_STORE.current(f"Ep{num}", required=False)
                current = SCRIPT_STORE.rename_current(f"Ep{num}", title)
                # A Writers' Room score belongs to the same immutable script bytes. Preserve
                # its display alias when only the episode title changes.
                if before:
                    old_score = SCRIPTS / before["displayFile"].replace(".txt", ".score.json")
                    new_score = SCRIPTS / current["displayFile"].replace(".txt", ".score.json")
                    if old_score.exists() and not new_score.exists():
                        new_score.write_bytes(old_score.read_bytes())
                # update the "title" field of any package + rename its file to match
                for pk in list(OUT.glob(f"Ep{num}_*_beat_package.json")) + list(OUT.glob(f"Ep{num}_*_shot_package.json")):
                    try:
                        pd = json.loads(pk.read_text()); pd["title"] = title
                        pk.write_text(json.dumps(pd, indent=1, ensure_ascii=False))
                        kind = "_beat_package.json" if pk.name.endswith("_beat_package.json") else "_shot_package.json"
                        newpk = OUT / f"Ep{num}_{newslug}{kind}"
                        if pk.name != newpk.name and not newpk.exists():
                            pk.rename(newpk)
                    except Exception:
                        pass
                eps = reindex_episodes()
                self._json(200, {"ok": True, "title": title, "episodes": eps})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/scene-shot":
            try:
                import base64, shutil
                d = self._body()
                scene = str(d.get("scene", "")).strip()
                if not scene:
                    raise ValueError("scene required")
                episode = str(d.get("episode") or "Ep1").strip() or "Ep1"
                fname = f"{episode}_S{scene}_plate.png"
                MEDIA.mkdir(parents=True, exist_ok=True)
                src = d.get("fromFile")
                if src:   # PULL from the library — copy an existing image to this scene's plate
                    sp = (ROOT / str(src).lstrip("/")).resolve()
                    if not (sp.is_relative_to(ROOT) and sp.is_file()):
                        raise ValueError("fromFile not found")
                    shutil.copy(str(sp), str(MEDIA / fname))
                else:     # UPLOAD — decode the image data
                    raw = d.get("imageData") or ""
                    if not raw:
                        raise ValueError("imageData or fromFile required")
                    if raw.strip().startswith("data:") and "," in raw:
                        raw = raw.split(",", 1)[1]
                    (MEDIA / fname).write_bytes(base64.b64decode(raw))
                reindex_media()   # the file exists on disk now — without this, media-index.json (what the UI
                                  # re-fetches right after this call) stays stale and the plate never appears
                self._json(200, {"ok": True, "plate": fname})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/beat-update":
            try:
                d = self._body()
                pkg = str(d.get("package", "")).strip()
                code = str(d.get("beatCode", "")).strip()
                if not pkg or not code:
                    raise ValueError("package and beatCode required")
                if "/" in pkg or ".." in pkg:
                    raise ValueError("bad package name")
                pf = ROOT / "cb-output" / pkg
                if not pf.exists():
                    raise ValueError("package not found: " + pkg)
                data = json.loads(pf.read_text())
                beats = data.get("beats") or data.get("shots") or []
                target = next((b for b in beats if str(b.get("beatCode") or b.get("shotCode")) == code), None)
                if target is None:
                    raise ValueError("beat not found: " + code)
                for k, v in (d.get("updates") or {}).items():
                    if isinstance(v, dict):
                        cur = target.get(k) if isinstance(target.get(k), dict) else {}
                        # was `if vv not in (None, "")` — skipped every blank sub-field, so a user could never
                        # actively CLEAR a nested field (opensOn/fidelityAllocation/performance/continuity) via
                        # the Studio UI (found 2026-07-08). The only caller (app.html's ebSave) always sends the
                        # FULL current state of every sub-field on every save, never a partial patch, so
                        # excluding only None (not "") is safe — nothing relies on blank-means-leave-alone here.
                        cur.update({kk: vv for kk, vv in v.items() if vv is not None})
                        target[k] = cur
                    elif v is not None:
                        target[k] = v
                if isinstance(d.get("cuts"), list):
                    target["cuts"] = d["cuts"]
                try:
                    (ROOT / "cb-output" / (pkg + ".bak")).write_text(pf.read_text())  # one-step undo backup
                except Exception:
                    pass
                pf.write_text(json.dumps(data, indent=2, ensure_ascii=False))
                self._json(200, {"ok": True, "beatCode": code})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/scene-update":
            # THE SCENE-LOOK LAW + THE SCENE BUBBLE LAW's three locked constants (sceneLook, ambientBed,
            # parentLine) had no write path at all before this — found in the 2026-07-08 software-wide audit.
            # Mirrors /api/beat-update's own generic merge pattern, targeting data["scenes"] instead of
            # data["beats"]/data["shots"].
            try:
                d = self._body()
                pkg = str(d.get("package", "")).strip()
                sn = str(d.get("sceneNumber", "")).strip()
                if not pkg or not sn:
                    raise ValueError("package and sceneNumber required")
                if "/" in pkg or ".." in pkg:
                    raise ValueError("bad package name")
                pf = ROOT / "cb-output" / pkg
                if not pf.exists():
                    raise ValueError("package not found: " + pkg)
                data = json.loads(pf.read_text())
                scenes = data.get("scenes") or []
                target = next((s for s in scenes if str(s.get("sceneNumber")) == sn), None)
                if target is None:
                    raise ValueError("scene not found: " + sn)
                for k, v in (d.get("updates") or {}).items():
                    if isinstance(v, dict):
                        cur = target.get(k) if isinstance(target.get(k), dict) else {}
                        # same nested-clearing fix as /api/beat-update above (2026-07-08) — excludes only None.
                        cur.update({kk: vv for kk, vv in v.items() if vv is not None})
                        target[k] = cur
                    elif v is not None:
                        target[k] = v
                try:
                    (ROOT / "cb-output" / (pkg + ".bak")).write_text(pf.read_text())  # one-step undo backup
                except Exception:
                    pass
                pf.write_text(json.dumps(data, indent=2, ensure_ascii=False))
                self._json(200, {"ok": True, "sceneNumber": sn})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/project":
            try:
                import datetime
                d = self._body()
                name = str(d.get("name", "")).strip()
                if not name:
                    raise ValueError("project name required")
                pid = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "project"
                base_pid = pid; i = 2
                while (ROOT / "projects" / pid).exists():
                    pid = base_pid + "-" + str(i); i += 1
                pdir = ROOT / "projects" / pid
                (pdir / "assets").mkdir(parents=True, exist_ok=True)
                chars = {}
                for ch in (d.get("characters") or []):
                    cn = str(ch.get("name", "")).strip()
                    if not cn:
                        continue
                    entry = {"key_features": str(ch.get("keyFeatures", "")).strip()}
                    raw = ch.get("imageData") or ""
                    if raw:
                        blob, ext = decode_image_upload(raw)
                        safe = slug(cn).lower()
                        fn = safe + "_anchor" + ext
                        (pdir / "assets" / fn).write_bytes(blob)
                        rel = "projects/" + pid + "/assets/" + fn
                        entry["anchor"] = rel; entry["refs"] = [rel]
                    chars[cn] = entry
                cover_image = ""
                raw_cover = d.get("coverImageData") or ""
                if raw_cover:
                    blob, ext = decode_image_upload(raw_cover)
                    fn = "project_key_art" + ext
                    (pdir / "assets" / fn).write_bytes(blob)
                    cover_image = "/projects/" + pid + "/assets/" + fn
                (pdir / "characters.json").write_text(json.dumps(chars, indent=2, ensure_ascii=False))
                (pdir / "show_bible.md").write_text(str(d.get("showBible", "")))
                (pdir / "episodes.json").write_text("[]")
                accent = str(d.get("accentColor", "")).strip().lower()
                if not re.fullmatch(r"#[0-9a-f]{6}", accent):
                    accent = "#0b8f87"
                meta = {
                    "id": pid, "name": name, "primary": False,
                    "animationType": d.get("animationType", ""), "style": d.get("style", ""),
                    "premise": d.get("premise", ""), "audience": d.get("audience", ""),
                    "episodeLength": d.get("episodeLength", ""), "aspectRatio": d.get("aspectRatio", ""),
                    "voiceProvider": d.get("voiceProvider", ""), "musicStyle": d.get("musicStyle", ""),
                    "theme": {"accent": accent},
                    "configBase": "projects/" + pid, "showBibleFile": "projects/" + pid + "/show_bible.md",
                    "episodesFile": "projects/" + pid + "/episodes.json", "mediaBase": "projects/" + pid + "/media",
                    "createdAt": str(datetime.date.today()),
}
                if cover_image:
                    meta["coverImage"] = cover_image
                    meta["episodeCoverImage"] = cover_image
                (pdir / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
                pf = ROOT / "cb-studio" / "data" / "projects.json"
                pdata = json.loads(pf.read_text()) if pf.exists() else {"projects": []}
                if not isinstance(pdata, dict):
                    pdata = {"projects": []}
                pdata.setdefault("projects", []).append(meta)
                pf.write_text(json.dumps(pdata, indent=2, ensure_ascii=False))
                self._json(200, {"ok": True, "id": pid, "project": meta})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/scene-ref":
            try:
                import base64
                d = self._body()
                name = str(d.get("name", "")).strip()
                raw = d.get("imageData") or ""
                if not name:
                    raise ValueError("name required")
                if not raw:
                    raise ValueError("imageData required")
                if raw.strip().startswith("data:") and "," in raw:
                    raw = raw.split(",", 1)[1]
                safe = re.sub(r"[^A-Za-z0-9]+", "", name) or "Scene"
                outdir = ASSETS / "ep1"
                outdir.mkdir(parents=True, exist_ok=True)
                fn = f"CB_Scene_{safe}_anchor.png"
                (outdir / fn).write_bytes(base64.b64decode(raw))
                self._json(200, {"ok": True, "file": f"cb-seed/assets/ep1/{fn}", "name": name})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/character":
            try:
                import base64
                d = self._body()
                name = (d.get("name") or "").strip()
                if not name:
                    raise ValueError("name required")
                cpath = CANON_CONFIG / "characters.json"
                C = json.loads(cpath.read_text())
                entry = C.get(name) if isinstance(C.get(name), dict) else {}
                if d.get("anchorData"):
                    raw = d["anchorData"]
                    if raw.strip().startswith("data:") and "," in raw:
                        raw = raw.split(",", 1)[1]
                    ext = (d.get("anchorName", "") or "").rsplit(".", 1)[-1].lower()
                    if ext not in ("png", "jpg", "jpeg", "webp"):
                        ext = "png"
                    safe = "CB_" + re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_") + "_anchor." + ext
                    ASSETS.mkdir(parents=True, exist_ok=True)
                    (ASSETS / safe).write_bytes(base64.b64decode(raw))
                    entry["anchor"] = "../cb-seed/assets/" + safe
                if d.get("turnData"):
                    raw = d["turnData"]
                    if raw.strip().startswith("data:") and "," in raw:
                        raw = raw.split(",", 1)[1]
                    ext = (d.get("turnName", "") or "").rsplit(".", 1)[-1].lower()
                    if ext not in ("png", "jpg", "jpeg", "webp"):
                        ext = "png"
                    safe = "CB_" + re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_") + "_turn4." + ext
                    ASSETS.mkdir(parents=True, exist_ok=True)
                    (ASSETS / safe).write_bytes(base64.b64decode(raw))
                    turn_path = "../cb-seed/assets/" + safe
                    entry["turn4"] = turn_path
                    entry.setdefault("refs", [])
                    if turn_path not in entry["refs"]:
                        entry["refs"].insert(0, turn_path)
                reference_data = d.get("referenceData") or []
                if not isinstance(reference_data, list):
                    raise ValueError("referenceData must be a list")
                if len(reference_data) > 12:
                    raise ValueError("a character update accepts at most 12 reference images")
                if reference_data:
                    char_dir = ASSETS / "characters" / slug(name)
                    char_dir.mkdir(parents=True, exist_ok=True)
                    entry.setdefault("refs", [])
                    for index, reference in enumerate(reference_data, start=1):
                        if not isinstance(reference, dict) or not reference.get("data"):
                            raise ValueError("each reference image requires data and a filename")
                        raw = str(reference["data"])
                        if raw.strip().startswith("data:") and "," in raw:
                            raw = raw.split(",", 1)[1]
                        ext = str(reference.get("name") or "").rsplit(".", 1)[-1].lower()
                        if ext not in ("png", "jpg", "jpeg", "webp"):
                            ext = "png"
                        source_stem = re.sub(r"[^A-Za-z0-9]+", "_", pathlib.Path(str(reference.get("name") or f"reference_{index}")).stem).strip("_")
                        filename = f"CB_{slug(name)}_{source_stem or ('reference_' + str(index))}.{ext}"
                        out = char_dir / filename
                        out.write_bytes(base64.b64decode(raw))
                        rel = "../" + out.relative_to(ROOT).as_posix()
                        if rel not in entry["refs"]:
                            entry["refs"].append(rel)
                for k in ("key_features", "voiceId", "size", "sizeRef", "cadence",
                          "tier", "crystal", "feeling", "colour", "note", "home"):
                    if d.get(k) not in (None, ""):
                        entry[k] = d[k]
                if str(d.get("sizeRank", "")).strip().isdigit():
                    entry["sizeRank"] = int(d["sizeRank"])
                C[name] = entry
                cpath.write_text(json.dumps(C, indent=2, ensure_ascii=False))
                sync = subprocess.run(
                    [sys.executable, str(ROOT / "tools" / "sync_canon.py")],
                    cwd=str(ROOT), capture_output=True, text=True, timeout=30,
                )
                if sync.returncode:
                    raise RuntimeError(sync.stderr.strip() or sync.stdout.strip() or
                                       "canon compatibility sync failed")
                import cb_canon
                lock = cb_canon.status(root=ROOT)
                self._json(200, {"ok": True, "name": name, "character": entry,
                                 "canonLockCurrent": lock.get("current"),
                                 "canonAction": "Review this change, then explicitly re-lock canon."})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/post-workspace":
            try:
                import cb_post_workspace
                d = self._body()
                episode = str(d.get("episode") or "Ep1").strip()
                action = str(d.get("action") or "").strip()
                if not _SHOT_TOKEN.match(episode):
                    raise ValueError("episode must be a plain token")
                if action in ("approve", "reject"):
                    payload = cb_post_workspace.record_verdict(
                        episode,
                        "approved" if action == "approve" else "rejected",
                        str(d.get("note") or ""),
                        str(d.get("reviewer") or "Julian"),
                    )
                    self._json(200, payload)
                    return
                if action in ("rebuild", "build-assembly"):
                    args = [
                        "../tools/build_episode_post95_master.py",
                        "--episode", episode,
                    ]
                    job_id = _start(_jid(f"post_{episode}"), "post:episode-assembly", "post", args)
                    self._json(200, {"ok": True, "jobId": job_id})
                    return
                raise ValueError("action must be approve, reject or build-assembly")
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/department-run":
            # One explicit specialist thinking call. The subprocess can use the LLM but its
            # cb_render command has no path to cb_gen: it stores an awaiting-approval brief
            # and stops. Existing approved work remains untouched on failure.
            try:
                d = self._body()
                scene = str(d.get("scene", "")).strip()
                ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                stage = str(d.get("stage", "")).strip()
                sid = str(d.get("shotId", "")).strip() or "-"
                if (not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(ep) or
                        stage not in DEPARTMENT_STAGES or
                        (sid != "-" and not _SHOT_TOKEN.match(sid))):
                    self._json(400, {"error": "invalid scene, episode, stage or shotId"}); return
                if stage not in ("look", "review-final") and sid == "-":
                    self._json(400, {"error": f"{stage} needs a shotId"}); return
                department_runtime = _canonical_cb_render()
                status = department_runtime.department_status(
                    scene, None if sid == "-" else sid, ep, stage)
                # Reuse only direction signed against the current direct inputs. A stale
                # candidate must reach cb_safety.prepare_department(), which archives it
                # and prepares its replacement instead of trapping WATCH in a loop.
                if status.get("candidate") and status.get("candidateCurrent"):
                    self._json(200, {
                        "ok": True,
                        "existing": True,
                        "department": status,
                    })
                    return
                args = ["cb_render.py", "department-prepare", scene, stage, sid, ep]
                job = _start(_jid(f"department_{stage}_{sid}"),
                             f"department:{stage}:{sid}", scene, args)
                self._json(200, {"ok": True, "jobId": job})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/director-chat":
            # A small-context OpenAI text call. It can discuss and propose one bounded
            # correction, but cannot mutate production state or reach any media provider.
            try:
                d = self._body()
                scene = str(d.get("scene") or "").strip()
                ep = str(d.get("episode") or "Ep1").strip() or "Ep1"
                shot_id = str(d.get("shotId") or "").strip() or None
                stage = str(d.get("stage") or "").strip()
                if (not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(ep) or
                        (shot_id and not _SHOT_TOKEN.match(shot_id)) or
                        not _SHOT_TOKEN.match(stage)):
                    return self._json(400, {"error": "invalid Director chat scope"})
                import cb_director_chat
                result = cb_director_chat.chat(
                    ep, scene, shot_id, stage, d.get("message"), issue=d.get("issue"),
                    reviewer=str(d.get("by") or "Julian"))
                return self._json(200, {"ok": True, **result})
            except Exception as exc:
                return self._json(400, {"error": str(exc), "zeroMediaSpend": True})
        if self.path == "/api/director-action":
            # The Director UI submits product-level decisions only. This server translates
            # them onto the existing engine allowlist after recomputing the current session;
            # stale or invented actions are refused before any mutation or provider call.
            try:
                d = self._body()
                scene = str(d.get("scene") or "").strip()
                ep = str(d.get("episode") or "Ep1").strip() or "Ep1"
                shot_id = (str(d.get("shotId")).strip()
                           if d.get("shotId") not in (None, "") else None)
                action = str(d.get("action") or "").strip()
                note = str(d.get("note") or "").strip()
                if (not scene or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(ep) or
                        (shot_id and not _SHOT_TOKEN.match(shot_id))):
                    self._json(400, {"error": "invalid Director action target"}); return
                if action not in DIRECTOR_ACTION_IDS:
                    self._json(409, {
                        "error": "That action is no longer current or is not recognised. Refresh the Studio and try again.",
                    }); return
                if action == "save-retake-note":
                    stage = str(d.get("stage") or "").strip()
                    if not shot_id or stage not in ("1", "2", "3"):
                        self._json(400, {"error": "A shot and SEE, HEAR or WATCH stage are required."}); return
                    state = _save_project_workbench_state({
                        "project": ACTIVE_PROJECT_ID, "episode": ep, "scene": scene,
                        "retakeNotes": {f"{shot_id}:{stage}": note},
                    })
                    self._json(200, {"ok": True, "zeroSpend": True,
                                     "savedNote": note,
                                     "updatedAt": state.get("updatedAt")}); return
                # Mutating actions must be admitted by a fresh state projection. A cached
                # Director session is fine for navigation, but it can preserve a button from
                # before SEE/HEAR/WATCH state, references, or signed prompts changed.
                read_only_action = action in ("open-inspector", "open-provider-setup")
                session = (
                    _cached_director_session(scene, ep, shot_id)
                    if read_only_action else
                    _director_session(scene, ep, shot_id)
                )
                import cb_studio_director as _CBD
                if action not in _CBD.allowed_action_ids(session):
                    self._json(409, {
                        "error": "That action is no longer current. The Director view has been refreshed.",
                        "session": session,
                    }); return
                target = session.get("selectedShotId")

                if action in ("open-inspector", "open-provider-setup"):
                    stage = "animation" if action == "open-provider-setup" else session.get("phase")
                    if action == "open-inspector" and stage == "story":
                        route = ("/cb-studio/director.html#view=pipeline&scene=" +
                                 quote(scene) + "&step=analysis")
                    else:
                        route = (f"/cb-studio/app.html#p={ACTIVE_PROJECT_ID}&pg=pipeline&ep=" +
                                 quote(ep) + "&sc=" + quote(scene) + "&st=" +
                                 quote(str(stage or "storyboard")) +
                                 (("&shot=" + quote(target)) if target else ""))
                    self._json(200, {"ok": True, "navigate": route, "zeroSpend": True}); return
                if action == "direct-scene":
                    args = ["cb_creative.py", "scene", scene, ep]
                    job_id = _start(_jid(f"director_scene_{scene}"),
                                    "director:scene", scene, args)
                elif action in ("build-scene-plate", "select-scene-plate-library", "select-scene-plate-upload"):
                    source_path = d.get("sourcePath")
                    if action == "build-scene-plate":
                        job_id = shot_run_job("scenelook", scene, ep)
                    else:
                        if not source_path or not isinstance(source_path, str):
                            self._json(400, {"error": "Choose a scene plate source first."}); return
                        try:
                            sp = pathlib.Path(source_path).resolve()
                            roots = (MEDIA.resolve(), ASSETS.resolve())
                            if not sp.exists() or not any(sp.is_relative_to(root) for root in roots):
                                self._json(400, {"error": "sourcePath must be an existing file under engine/media or cb-seed/assets"}); return
                        except Exception:
                            self._json(400, {"error": "sourcePath is not a valid path"}); return
                        _CBR = _canonical_cb_render()
                        mode = "library" if action == "select-scene-plate-library" else "upload"
                        try:
                            st = _CBR.scenelook_status(scene, ep)
                            if st.get("candidate"):
                                _CBR.reject_scenelook(
                                    scene,
                                    "Superseded by direct Scene Plate library/upload selection in the Director workspace.",
                                    episode=ep,
                                    reviewed_by=str(d.get("by") or "Julian"),
                                )
                            _CBR.select_scenelook_source(
                                scene, mode, ep,
                                library_path=str(sp) if mode == "library" else None,
                                upload_path=str(sp) if mode == "upload" else None,
                            )
                            _CBR.approve_scenelook(scene, ep)
                        except _CBR.Refused as e:
                            self._json(409, {"error": str(e), "session": session}); return
                        job_id = None
                elif action in ("select-keyframe-library", "select-keyframe-upload"):
                    if not target:
                        self._json(409, {"error": "No current shot is available"}); return
                    source_path = d.get("sourcePath")
                    if not source_path or not isinstance(source_path, str):
                        self._json(400, {"error": "Choose a keyframe source first."}); return
                    try:
                        sp = pathlib.Path(source_path).resolve()
                        roots = (MEDIA.resolve(), ASSETS.resolve())
                        if not sp.exists() or not any(sp.is_relative_to(root) for root in roots):
                            self._json(400, {"error": "sourcePath must be an existing file under engine/media or cb-seed/assets"}); return
                    except Exception:
                        self._json(400, {"error": "sourcePath is not a valid path"}); return
                    command = "select-library" if action == "select-keyframe-library" else "select-upload"
                    job_id = shot_run_job(command, scene, ep, target, source_path=str(sp))
                elif action == "select-keyframe-candidate":
                    if not target:
                        self._json(409, {"error": "No current shot is available"}); return
                    candidate = str(d.get("candidate") or "").strip().upper()
                    _CBR = _canonical_cb_render()
                    try:
                        _CBR.select_keyframe_candidate(
                            scene, target, candidate, episode=ep,
                            log=lambda message: print(message, flush=True))
                    except _CBR.Refused as e:
                        self._json(409, {"error": str(e), "session": session}); return
                    _clear_director_session_cache(scene=scene, episode=ep)
                    self._json(200, {
                        "ok": True,
                        "zeroSpend": True,
                        "selectedCandidateId": candidate,
                        "session": _director_session(scene, ep, target),
                    }); return
                elif action in ("build-keyframe", "build-voice", "prepare-render"):
                    if not target:
                        self._json(409, {"error": "No current shot is available"}); return
                    command = {
                        "build-keyframe": "build-keyframe",
                        "build-voice": "build-voice",
                        "prepare-render": "prepare-render",
                    }[action]
                    job_id = _start(
                        _jid(f"director_{command}_{target}"),
                        f"director:{command}:{target}", scene,
                        ["cb_studio_director.py", command, scene, target, ep])
                elif action == "accept-keyframe":
                    import cb_render as _CBR
                    candidate = str(d.get("candidate") or "").strip().upper()
                    if candidate:
                        _CBR.select_keyframe_candidate(
                            scene, target, candidate, episode=ep,
                            log=lambda message: print(message, flush=True))
                    review_work = ((((session.get("humanReview") or {}).get(
                        "currentDecision") or {}).get("aiReview") or {}))
                    if review_work.get("available"):
                        _CBR.decide_department(
                            scene, "review-keyframe", "approved", shot_id=target,
                            note="Julian accepted the keyframe after considering the AI Director recommendation.",
                            episode=ep, reviewed_by=str(d.get("by") or "Julian"))
                    job_id = shot_run_job("approve-keyframe", scene, ep, target)
                elif action == "iterate-keyframe":
                    if not note:
                        self._json(400, {"error": "Tell the Director what must change."}); return
                    import cb_render as _CBR
                    review_work = ((((session.get("humanReview") or {}).get(
                        "currentDecision") or {}).get("aiReview") or {}))
                    if review_work.get("available"):
                        _CBR.decide_department(
                            scene, "review-keyframe", "rejected", shot_id=target,
                            note=note, episode=ep,
                            reviewed_by=str(d.get("by") or "Julian"))
                    job_id = _start(
                        _jid(f"director_refire-keyframe_{target}"),
                        f"director:refire-keyframe:{target}", scene,
                        ["cb_studio_director.py", "refire-keyframe", scene,
                         target, note, ep])
                elif action == "accept-voice":
                    job_id = shot_run_job("approve-voice", scene, ep, target)
                elif action == "iterate-voice":
                    if not note:
                        self._json(400, {"error": "Tell the Director what must change."}); return
                    job_id = shot_run_job("reject-voice", scene, ep, target, note)
                elif action == "approve-spend":
                    pkg, _ = _load_director_package(scene, ep)
                    ledger = next((item for item in (pkg.get("continuityLedger") or [])
                                   if item.get("shotId") == target), {})
                    token = ((ledger.get("pendingSpendAuth") or {}).get("token"))
                    if not token:
                        self._json(409, {"error": "The sealed spend approval is no longer current."}); return
                    candidate_count = int((((ledger.get("pendingSpendAuth") or {})
                                            .get("disclosure") or {})
                                           .get("candidateCount") or 1))
                    job_id = shot_run_job("fire", scene, ep, target, candidates=candidate_count,
                                          spend_token=token)
                elif action == "cancel-spend":
                    self._json(200, {"ok": True, "zeroSpend": True, "noChange": True}); return
                elif action == "accept-animation":
                    candidate = d.get("candidate")
                    choices = (((session.get("artifact") or {}).get("items")) or [])
                    available = {int(item["n"]) for item in choices if item.get("n") is not None}
                    if candidate is None and len(available) == 1:
                        candidate = next(iter(available))
                    try:
                        candidate = int(candidate)
                    except (TypeError, ValueError):
                        candidate = -1
                    if candidate not in available:
                        self._json(400, {"error": "Choose a current animation candidate."}); return
                    import cb_render as _CBR
                    review_work = ((((session.get("humanReview") or {}).get(
                        "currentDecision") or {}).get("aiReview") or {}))
                    if review_work.get("available"):
                        _CBR.decide_department(
                            scene, "review-animation", "approved", shot_id=target,
                            note="Julian accepted the selected take after considering the AI Director recommendation.",
                            episode=ep, reviewed_by=str(d.get("by") or "Julian"))
                    job_id = shot_run_job("approve", scene, ep, target, candidate=candidate)
                elif action == "iterate-animation":
                    if not note:
                        self._json(400, {"error": "Tell the Director what must change."}); return
                    import cb_render as _CBR
                    review_work = ((((session.get("humanReview") or {}).get(
                        "currentDecision") or {}).get("aiReview") or {}))
                    if review_work.get("available"):
                        _CBR.decide_department(
                            scene, "review-animation", "rejected", shot_id=target,
                            note=note, episode=ep,
                            reviewed_by=str(d.get("by") or "Julian"))
                    job_id = shot_run_job("reject", scene, ep, target, note,
                                          category="other")
                elif action == "run-ai-review":
                    review_stage = {
                        "keyframe": "review-keyframe",
                        "animation": "review-animation",
                    }.get(session.get("phase"))
                    if not review_stage:
                        self._json(409, {"error": "No visual artifact is awaiting AI review."}); return
                    job_id = _start(
                        _jid(f"director_ai_review_{target}"),
                        f"director:ai-review:{target}", scene,
                        ["cb_render.py", "department-prepare", scene,
                         review_stage, target, ep])
                elif action == "run-quality-review":
                    job_id = _start(
                        _jid(f"director_quality_{target}"),
                        f"director:quality:{target}", scene,
                        ["cb_render.py", "department-prepare", scene,
                         "review-animation", target, ep])
                elif action == "accept-quality":
                    import cb_render as _CBR
                    _CBR.decide_department(
                        scene, "review-animation", "approved", shot_id=target,
                        note="Accepted from the outcome-first Director review.",
                        episode=ep, reviewed_by=str(d.get("by") or "Julian"))
                    self._json(200, {"ok": True, "zeroSpend": True}); return
                elif action == "reopen-shot":
                    if not note:
                        self._json(400, {"error": "Tell the Director what must change."}); return
                    import cb_render as _CBR
                    _CBR.reopen_approved_shot(
                        scene, target, note, category="other", episode=ep,
                        reviewed_by=str(d.get("by") or "Julian"))
                    self._json(200, {"ok": True, "zeroSpend": True}); return
                elif action == "build-master":
                    job_id = shot_run_job("stitch", scene, ep)
                elif action == "run-final-review":
                    job_id = _start(
                        _jid(f"director_final_review_{scene}"),
                        "director:final-review", scene,
                        ["cb_render.py", "department-prepare", scene,
                         "review-final", "-", ep])
                elif action == "accept-master":
                    import cb_render as _CBR
                    _CBR.decide_department(
                        scene, "review-final", "approved", shot_id=None,
                        note="Final master accepted in the Director review.",
                        episode=ep, reviewed_by=str(d.get("by") or "Julian"))
                    self._json(200, {"ok": True, "zeroSpend": True}); return
                elif action == "iterate-master":
                    if not note:
                        self._json(400, {"error": "Tell the Director what must change."}); return
                    import cb_render as _CBR
                    _CBR.decide_department(
                        scene, "review-final", "rejected", shot_id=None, note=note,
                        episode=ep, reviewed_by=str(d.get("by") or "Julian"))
                    self._json(200, {"ok": True, "zeroSpend": True}); return
                else:
                    self._json(409, {"error": "This Director action is not implemented yet."}); return
                if job_id is None:
                    self._json(200, {
                        "ok": True,
                        "zeroSpend": True,
                        "session": _director_session(scene, ep, target),
                    }); return
                self._json(200, {"ok": True, "jobId": job_id})
            except Exception as exc:
                self._json(400, {"error": str(exc)})
            return
        if self.path == "/api/prompt-lab-rate":
            # Append-only human evidence. This never approves/rejects media and never calls
            # a provider; cb_render rebinds the submitted candidate ID to its live asset,
            # exact prompt snapshot and current content hash before saving.
            if str(CBGEN) not in sys.path:
                sys.path.insert(0, str(CBGEN))
            import cb_render as _CBR
            try:
                d = self._body()
                scene = str(d.get("scene", "")).strip()
                sid = str(d.get("shotId", "")).strip()
                ep = str(d.get("episode") or "Ep1").strip() or "Ep1"
                artifact_type = str(d.get("artifactType", "")).strip()
                candidate_id = str(d.get("candidateId", "")).strip()
                if (not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(sid) or
                        not _SHOT_TOKEN.match(ep) or not _SHOT_TOKEN.match(candidate_id) or
                        artifact_type not in ("keyframe", "animation")):
                    self._json(400, {"error": "invalid Prompt Lab rating target"}); return
                record = _CBR.rate_prompt_render(
                    scene, sid, artifact_type, candidate_id,
                    d.get("scores") or {}, str(d.get("overallRead") or ""),
                    note=str(d.get("note") or ""), episode=ep,
                    reviewed_by=str(d.get("by") or "Julian"))
                self._json(200, {
                    "ok": True,
                    "rating": record,
                    "zeroSpend": True,
                    "approvalChanged": False,
                })
            except _CBR.Refused as e:
                self._json(409, {"error": str(e), "zeroSpend": True})
            except (ValueError, TypeError) as e:
                self._json(400, {"error": str(e), "zeroSpend": True})
            except Exception as e:
                self._json(500, {"error": str(e), "zeroSpend": True})
            return
        if self.path == "/api/dailies-review":
            # One lightweight human call after a render. Diagnosis is advisory and a retake
            # is never fired here; the existing approval ledger remains authoritative.
            try:
                import cb_dailies
                import cb_render as _CBR
                d = self._body()
                scene = str(d.get("scene", "")).strip()
                sid = str(d.get("shotId", "")).strip()
                ep = str(d.get("episode") or "Ep1").strip() or "Ep1"
                candidate = str(d.get("candidateId") or "").strip()
                if (not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(sid) or
                        not _SHOT_TOKEN.match(ep) or not _SHOT_TOKEN.match(candidate)):
                    self._json(400, {"error": "invalid dailies review target"}); return
                rating = int(d.get("rating"))
                decision = str(d.get("decision") or "").strip().lower()
                if rating not in range(1, 6) or decision not in {"approve", "retake", "reject"}:
                    self._json(400, {"error": "rating must be 1-5 and decision must be approve, retake or reject"}); return
                snapshot = _CBR._prompt_lab_snapshot(scene, sid, "animation", ep, candidate)
                selected = snapshot.get("selected") or {}
                shot = snapshot.get("shot") or {}
                contract = selected.get("promptContract") or {}
                ledger = snapshot.get("ledger") or {}
                review = cb_dailies.record({
                    "episode": ep, "scene": scene, "beat": shot.get("beat") or shot.get("purpose"),
                    "shotId": sid, "candidateId": candidate, "take": candidate,
                    "assetPath": selected.get("path"), "assetHash": selected.get("expectedAssetHash"),
                    "promptHash": contract.get("promptHash"), "promptVersion": contract.get("promptHash"),
                    "keyframeVersion": ((ledger.get("keyframeApproval") or {}).get("contentHash")),
                    "audioVersion": ((ledger.get("audioApproval") or {}).get("contentHash") or
                                     (ledger.get("voiceApproval") or {}).get("contentHash")),
                    "provider": contract.get("provider"), "providerModelId": contract.get("providerModelId"),
                    "operationId": ((ledger.get("batch") or {}).get("batchId")),
                    "openingFrame": shot.get("openingPose"), "landingFrame": shot.get("continuityFinish"),
                    "audioAsset": ledger.get("approvedAudio") or ledger.get("voiceApproved"),
                    "storyBeat": shot.get("purpose"), "automatedScores": snapshot.get("aiReview") or {},
                    "timing": {"durationSec": shot.get("durationSec")},
                }, rating=rating, decision=decision, note=str(d.get("note") or ""),
                   reviewer=str(d.get("by") or "Julian"), cost=d.get("cost"),
                   retake_of=d.get("retakeOf"))
                self._json(200, {"ok": True, "review": review, "compare": cb_dailies.compare(review["recordId"]), "zeroSpend": True})
            except _CBR.Refused as e:
                self._json(409, {"error": str(e), "zeroSpend": True})
            except (ValueError, TypeError) as e:
                self._json(400, {"error": str(e), "zeroSpend": True})
            except Exception as e:
                self._json(500, {"error": str(e), "zeroSpend": True})
            return
        if self.path in ("/api/department-save", "/api/department-decide"):
            # Plain ledger edits/decisions: no LLM and no media provider call.
            try:
                d = self._body()
                scene = str(d.get("scene", "")).strip()
                ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                stage = str(d.get("stage", "")).strip()
                sid = str(d.get("shotId", "")).strip() or None
                if (not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(ep) or
                        stage not in DEPARTMENT_STAGES or
                        (sid and not _SHOT_TOKEN.match(sid))):
                    self._json(400, {"error": "invalid scene, episode, stage or shotId"}); return
                import cb_render as _CBR
                if self.path == "/api/department-save":
                    rec = _CBR.save_department_candidate(
                        scene, stage, text=d.get("text"), lines=d.get("lines"), shot_id=sid,
                        episode=ep, reviewed_by=str(d.get("by") or "Julian"))
                else:
                    rec = _CBR.decide_department(
                        scene, stage, str(d.get("verdict") or ""), shot_id=sid,
                        note=str(d.get("note") or ""), episode=ep,
                        reviewed_by=str(d.get("by") or "Julian"))
                self._json(200, {"ok": True, "record": rec})
            except _CBR.Refused as e:
                self._json(400, {"error": str(e)})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/story-intake-run":
            # THE DIRECTOR'S SCRIPT INTAKE — one real thinking call (2026-07-19). Episode-
            # scoped, runs BEFORE any scene package exists, so it cannot reuse
            # /api/department-run (which always requires one). Background job, matching
            # every other specialist-thinking call in this studio — no media provider is
            # reachable from cb_intake.py at all.
            try:
                d = self._body()
                ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                if not _SHOT_TOKEN.match(ep):
                    self._json(400, {"error": "valid episode required"}); return
                args = ["cb_intake.py", "run", ep]
                job = _start(_jid(f"storyintake_{ep}"), "storyintake", "-", args)
                self._json(200, {"ok": True, "jobId": job})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/story-intake-decide":
            # Approve/reject the visible candidate. No LLM, no media provider — approve()
            # is the ONLY place that writes the canonical beat package + episode vision
            # that unlock cb_creative.py's own scene/storyboard process; reject() archives
            # the candidate (never deletes) and leaves no canonical package.
            try:
                d = self._body()
                ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                verdict = str(d.get("verdict") or "").strip()
                if not _SHOT_TOKEN.match(ep) or verdict not in ("approve", "reject"):
                    self._json(400, {"error": "episode and verdict (approve|reject) required"})
                    return
                import cb_intake as _CBI
                try:
                    rec = _CBI.decide_intake(ep, verdict, note=str(d.get("note") or ""),
                                             reviewed_by=str(d.get("by") or "Julian"))
                except _CBI.Refused:
                    status = _CBI.intake_status(ep)
                    if (verdict == "approve" and status.get("canonicalCurrent") and
                            status.get("candidateCurrent") and
                            (status.get("candidate") or {}).get("approvalState") == "approved"):
                        rec = {
                            "state": "approved",
                            "alreadyCurrent": True,
                            "message": "Story & Direction is already approved for this script and canon lock.",
                        }
                    else:
                        raise
                reindex_episodes()
                queued = []
                if rec.get("outcome") == "approved":
                    try:
                        queued = _queue_episode_storyboards(ep)
                    except Exception as queue_error:
                        # Intake approval remains valid; expose the handoff failure so
                        # the UI can show a retryable state instead of implying completion.
                        rec["sceneStoryboardQueueError"] = str(queue_error)
                self._json(200, {"ok": True, "record": rec,
                                 "sceneStoryboardJobs": queued,
                                 "sceneStoryboardCount": len(queued)})
            except _CBI.Refused as e:
                self._json(400, {"error": str(e)})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/creative-run":
            # THE CREATIVE ROOM job runner (2026-07-16): vision / scene passes — OpenAI text
            # calls only; no media provider, no spend token (cb_creative imports no adapter).
            try:
                d = self._body()
                cmd = str(d.get("cmd", "")).strip()
                scene = str(d.get("scene", "")).strip()
                ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                if cmd not in ("vision", "scene", "envelope", "migrate"):
                    self._json(400, {"error": "cmd must be vision|scene|envelope|migrate"}); return
                if cmd == "scene" and not re.match(r"^\w+$", scene):
                    self._json(400, {"error": "scene must be a plain token"}); return
                args = ["cb_creative.py", cmd] + ([scene, ep] if cmd == "scene" else [ep])
                self._json(200, {"ok": True,
                                  "jobId": _start(_jid(f"creative_{cmd}_{scene or ep}"),
                                                   "creative:" + cmd, scene or "-", args)})
            except Exception as e:
                self._json(500, {"error": str(e)})
            return
        if self.path in ("/api/storyboard-bootstrap", "/api/episode-production-start"):
            # Explicit, repeatable Scene Production handoff. No approval is changed and
            # no image, voice or video provider is called by this endpoint.
            try:
                d = self._body()
                ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                if not _SHOT_TOKEN.match(ep):
                    self._json(400, {"error": "valid episode required"}); return
                import cb_intake as _CBI
                status = _CBI.intake_status(ep)
                if not status.get("canonicalCurrent"):
                    # The common post-update case is a runtime skill hash changing while
                    # the approved script/creative package is unchanged. Refresh only that
                    # software contract and carry the approved package forward; never bypass
                    # a real script, canon, cast or asset blocker.
                    codes = {str(item.get("code")) for item in (status.get("canonBlockers") or [])}
                    if (status.get("hasCanonicalPackage") and codes == {"CANON_SOURCE_DRIFT"}
                            and all("runtime" in str(item.get("source") or "").lower()
                                    for item in (status.get("canonBlockers") or []))):
                        import cb_canon as _CBC
                        _CBC.write_lock(ROOT, locked_by="Julian via Start Episode Production")
                        _CBI.rebase_canon_lock(ep, reviewed_by="Julian")
                        status = _CBI.intake_status(ep)
                    if not status.get("canonicalCurrent"):
                        self._json(409, {"error": "The episode has a real script or canon change that needs review before production can start", "blockers": status.get("canonBlockers") or []}); return
                jobs = _queue_episode_storyboards(ep)
                self._json(200, {"ok": True, "sceneStoryboardJobs": jobs,
                                 "sceneStoryboardCount": len(jobs),
                                 "workflow": ["storyboard", "world-build", "keyframe",
                                              "voice-timing", "seedance-watch", "review"],
                                 "next": "Open a scene card to activate its workflow. Fire remains the paid human decision."})
            except Exception as e:
                self._json(500, {"error": str(e)})
            return
        if self.path == "/api/storyboard-approve":
            # HUMAN GATE A: approve/annotate at episode/scene/beat/shot level — a plain
            # creative note in the user's own words; no compiler fields exposed.
            try:
                self._json(200, _storyboard_approval(self._body()))
            except FileNotFoundError as e:
                self._json(404, {"error": str(e)})
            except (StoryboardApprovalRefused, cb_db.SceneBusy, cb_db.StateConflict) as e:
                self._json(409, {"error": str(e)})
            except ValueError as e:
                self._json(400, {"error": str(e)})
            except Exception as e:
                self._json(500, {"error": str(e)})
            return
        if self.path == "/api/storyboard-handover":
            # Non-decision repair: compile the current human-approved scene into its shot
            # package without adding another approval or contacting a media provider.
            try:
                self._json(200, _ensure_storyboard_handover(self._body()))
            except FileNotFoundError as e:
                self._json(404, {"error": str(e)})
            except (StoryboardApprovalRefused, cb_db.SceneBusy, cb_db.StateConflict) as e:
                self._json(409, {"error": str(e)})
            except ValueError as e:
                self._json(400, {"error": str(e)})
            except Exception as e:
                self._json(500, {"error": str(e)})
            return
        if self.path == "/api/direction-prepare":
            # Legacy/self-healing path for scene candidates created before Direction became
            # automatic. This is local text/package preparation only: no media provider and
            # no SEE, HEAR or WATCH approval is performed.
            try:
                d = self._body()
                ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                sc = str(d.get("scene") or "").strip()
                if not _SHOT_TOKEN.match(ep) or not _SHOT_TOKEN.match(sc):
                    raise ValueError("valid episode and scene required")
                self._json(200, {"ok": True,
                                 "direction": _prepare_scene_direction_for_production(ep, sc),
                                 "zeroMediaSpend": True})
            except FileNotFoundError as e:
                self._json(404, {"error": str(e), "zeroMediaSpend": True})
            except (StoryboardApprovalRefused, cb_db.SceneBusy, cb_db.StateConflict) as e:
                self._json(409, {"error": str(e), "zeroMediaSpend": True})
            except ValueError as e:
                self._json(400, {"error": str(e), "zeroMediaSpend": True})
            except Exception as e:
                self._json(500, {"error": str(e), "zeroMediaSpend": True})
            return
        if self.path == "/api/learning-promote":
            # THE EXPLICIT 'Promote to Creative Memory' ACTION — never silent, never automatic
            try:
                import cb_learning
                d = self._body()
                rec = cb_learning.promote(str(d.get("patternId", "")),
                                            by=str(d.get("by") or "Julian"),
                                            applied_source_ref=str(d.get("ref") or ""),
                                            decision=str(d.get("decision") or ""),
                                            activation_note=str(d.get("note", "")))
                self._json(200, {"ok": True, "activated": rec})
            except Exception as e:
                self._json(409, {"error": str(e)})
            return
        if self.path == "/api/shot-keyframe-upload":
            # THE UPLOAD SOURCE, STEP 1 OF 2 (2026-07-18, Julian's source-choice directive):
            # decodes a base64 image (same data-URI-or-raw convention as extract_doc_text's own
            # script-upload path above) and writes it to a holding file under the approved
            # engine/media tree — NOT yet a keyframe candidate. Step 2 is the client's own
            # follow-up /api/shot-run {cmd:"select-upload", sourcePath: <this path>} call, which
            # does the actual preserve-original + immutable-candidate-copy work in cb_render.py.
            # This endpoint alone never touches any shot's ledger.
            try:
                d = self._body()
                scene = str(d.get("scene", "")).strip(); sid = str(d.get("shotId", "")).strip()
                ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                raw = d.get("dataB64"); filename = str(d.get("filename") or "upload.png")
                if not scene or not sid or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(sid) \
                   or not _SHOT_TOKEN.match(ep):
                    self._json(400, {"error": "scene, shotId (and optional episode) required as plain tokens"}); return
                if not raw:
                    self._json(400, {"error": "dataB64 (the image data) is required"}); return
                blob, ext = decode_image_upload(raw)
                incoming = MEDIA / "uploads_incoming"
                incoming.mkdir(parents=True, exist_ok=True)
                out = incoming / f"{ep}_{sid}_incoming_{uuid.uuid4().hex[:8]}{ext}"
                out.write_bytes(blob)
                self._json(200, {"ok": True, "sourcePath": str(out)})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/shot-render-upload":
            # Zero-spend WATCH source. This stores a validated holding file only; the
            # follow-up select-render-upload command creates the immutable, auditable
            # shot candidate and still stops for Julian's normal Approve/Reject decision.
            try:
                d = self._body()
                scene = str(d.get("scene", "")).strip(); sid = str(d.get("shotId", "")).strip()
                ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                raw = d.get("dataB64")
                if not scene or not sid or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(sid) \
                   or not _SHOT_TOKEN.match(ep):
                    self._json(400, {"error": "scene, shotId and episode must be plain tokens"}); return
                if not raw:
                    self._json(400, {"error": "dataB64 (the render data) is required"}); return
                blob, ext = decode_video_upload(raw)
                incoming = MEDIA / "uploads_incoming"
                incoming.mkdir(parents=True, exist_ok=True)
                out = incoming / f"{ep}_{sid}_render_incoming_{uuid.uuid4().hex[:8]}{ext}"
                out.write_bytes(blob)
                self._json(200, {"ok": True, "sourcePath": str(out)})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/scenelook-upload":
            # THE SCENE LOOK UPLOAD SOURCE (2026-07-19 UX fix): scene-scoped mirror of
            # /api/shot-keyframe-upload above — no shotId, since Scene Look has no shot.
            # Decodes a base64 image and writes it to the same holding tree; the client's
            # own follow-up /api/shot-run {cmd:"scenelook", sourcePath: <this path>} call is
            # what actually fires generate_scenelook_plate with it as reference_path. This
            # endpoint alone never touches any ledger and never calls cb_gen.
            try:
                d = self._body()
                scene = str(d.get("scene", "")).strip()
                ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                raw = d.get("dataB64"); filename = str(d.get("filename") or "upload.png")
                if not scene or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(ep):
                    self._json(400, {"error": "scene (and optional episode) required as plain tokens"}); return
                if not raw:
                    self._json(400, {"error": "dataB64 (the image data) is required"}); return
                blob, ext = decode_image_upload(raw)
                incoming = MEDIA / "uploads_incoming"
                incoming.mkdir(parents=True, exist_ok=True)
                out = incoming / f"{ep}_S{scene}_scenelook_incoming_{uuid.uuid4().hex[:8]}{ext}"
                out.write_bytes(blob)
                self._json(200, {"ok": True, "sourcePath": str(out)})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/scenelook-select-source":
            # Zero-spend scene plate source assignment. This is intentionally
            # independent from the current Director action list so a freshly
            # uploaded plate cannot fail with "action no longer current".
            try:
                d = self._body()
                scene = str(d.get("scene", "")).strip()
                ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                source_path = d.get("sourcePath")
                mode = str(d.get("mode") or "upload").strip()
                if mode not in ("upload", "library"):
                    self._json(400, {"error": "mode must be upload or library"}); return
                if not scene or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(ep):
                    self._json(400, {"error": "scene (and optional episode) required as plain tokens"}); return
                if not source_path or not isinstance(source_path, str):
                    self._json(400, {"error": "Choose a scene plate source first."}); return
                try:
                    sp = pathlib.Path(source_path).resolve()
                    roots = (MEDIA.resolve(), ASSETS.resolve())
                    if not sp.exists() or not any(sp.is_relative_to(root) for root in roots):
                        self._json(400, {"error": "sourcePath must be an existing file under engine/media or cb-seed/assets"}); return
                except Exception:
                    self._json(400, {"error": "sourcePath is not a valid path"}); return
                _CBR = _canonical_cb_render()
                try:
                    st = _CBR.scenelook_status(scene, ep)
                    if st.get("candidate"):
                        _CBR.reject_scenelook(
                            scene,
                            "Superseded by direct Scene Plate library/upload selection in the Director workspace.",
                            episode=ep,
                            reviewed_by=str(d.get("by") or "Julian"),
                        )
                    _CBR.select_scenelook_source(
                        scene, mode, ep,
                        library_path=str(sp) if mode == "library" else None,
                        upload_path=str(sp) if mode == "upload" else None,
                    )
                    _CBR.approve_scenelook(scene, ep)
                except _CBR.Refused as e:
                    self._json(409, {"error": str(e)}); return
                with _DIRECTOR_SESSION_CACHE_LOCK:
                    for key in list(_DIRECTOR_SESSION_CACHE):
                        if key[0] == str(scene) and key[1] == str(ep):
                            _DIRECTOR_SESSION_CACHE.pop(key, None)
                self._json(200, {"ok": True, "sourcePath": str(sp), "mode": mode})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/asset-library-upload":
            # Generic library image upload for Characters / Scene Plates / Props.
            # This preserves a validated local image and binds it into the
            # project asset registry with an explicit intended production use.
            try:
                d = self._body()
                kind = slug(str(d.get("kind") or "asset")).lower()
                asset_use = slug(str(d.get("assetUse") or "")).lower()
                raw = d.get("dataB64")
                if kind not in ("characters", "scenes", "props", "asset"):
                    self._json(400, {"error": "kind must be characters, scenes or props"}); return
                allowed_uses = {
                    "character_turnaround", "scene_plate", "opening_plate",
                    "prop_reference", "general_reference", "",
                }
                if asset_use not in allowed_uses:
                    self._json(400, {"error": "assetUse must be character_turnaround, scene_plate, opening_plate, prop_reference or general_reference"}); return
                if not raw:
                    self._json(400, {"error": "dataB64 (the image data) is required"}); return
                blob, ext = decode_image_upload(raw)
                incoming = MEDIA / "uploads_incoming" / "asset_library"
                incoming.mkdir(parents=True, exist_ok=True)
                out = incoming / f"{kind}_{uuid.uuid4().hex[:10]}{ext}"
                out.write_bytes(blob)
                if not asset_use:
                    asset_use = {
                        "characters": "character_turnaround",
                        "scenes": "scene_plate",
                        "props": "prop_reference",
                        "asset": "general_reference",
                    }[kind]
                group_kind = {
                    "character_turnaround": "reference_image",
                    "scene_plate": "scene_plate",
                    "opening_plate": "opening_plate",
                    "prop_reference": "reference_image",
                    "general_reference": "reference_image",
                }[asset_use]
                label = str(d.get("label") or d.get("filename") or kind).strip() or kind
                scenes = str(d.get("scenes") or "").strip()
                bound_scene = str(d.get("scene") or "*").strip() or "*"
                if scenes:
                    first_scene = next((part.strip() for part in scenes.replace(",", " ").split() if part.strip()), "")
                    if first_scene:
                        bound_scene = first_scene
                rec = cb_asset_registry.register_asset(
                    episode=str(d.get("episode") or "Ep1"),
                    scene=bound_scene,
                    kind=group_kind,
                    path=out,
                    role=f"{asset_use}_{slug(label)}",
                    status="draft",
                    label=label,
                    source="studio-upload",
                    metadata={
                        "libraryGroup": kind,
                        "assetUse": asset_use,
                        "filename": str(d.get("filename") or ""),
                        "description": str(d.get("description") or ""),
                        "scenes": scenes,
                    },
                )
                reindex_media()
                self._json(200, {
                    "ok": True,
                    "sourcePath": str(out),
                    "url": "/engine/media/" + out.relative_to(MEDIA).as_posix(),
                    "assetId": rec.get("assetId"),
                    "assetUse": asset_use,
                    "kind": group_kind,
                    "scene": bound_scene,
                })
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/asset-library-delete":
            # Unbind an asset from the Studio library. This does not delete the
            # source file from disk; it removes the registry record so the asset
            # no longer appears as a selectable project-library item.
            try:
                d = self._body()
                asset_id = str(d.get("assetId") or "").strip()
                if not asset_id:
                    self._json(400, {"error": "assetId is required"}); return
                result = cb_asset_registry.remove_asset(asset_id)
                self._json(200, {"ok": True, **result})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/asset-library-update":
            # Edit an existing registry asset. If a replacement image is supplied,
            # the same asset record is rebound to the new displayable file.
            try:
                d = self._body()
                asset_id = str(d.get("assetId") or "").strip()
                if not asset_id:
                    self._json(400, {"error": "assetId is required"}); return
                kind = slug(str(d.get("kind") or "asset")).lower()
                asset_use = slug(str(d.get("assetUse") or "")).lower()
                if kind not in ("characters", "scenes", "props", "asset"):
                    self._json(400, {"error": "kind must be characters, scenes or props"}); return
                allowed_uses = {
                    "character_turnaround", "scene_plate", "opening_plate",
                    "prop_reference", "general_reference", "",
                }
                if asset_use not in allowed_uses:
                    self._json(400, {"error": "assetUse must be character_turnaround, scene_plate, opening_plate, prop_reference or general_reference"}); return
                if not asset_use:
                    asset_use = {
                        "characters": "character_turnaround",
                        "scenes": "scene_plate",
                        "props": "prop_reference",
                        "asset": "general_reference",
                    }[kind]
                group_kind = {
                    "character_turnaround": "reference_image",
                    "scene_plate": "scene_plate",
                    "opening_plate": "opening_plate",
                    "prop_reference": "reference_image",
                    "general_reference": "reference_image",
                }[asset_use]
                label = str(d.get("label") or d.get("filename") or kind).strip() or kind
                scenes = str(d.get("scenes") or "").strip()
                bound_scene = str(d.get("scene") or "*").strip() or "*"
                if scenes:
                    first_scene = next((part.strip() for part in scenes.replace(",", " ").split() if part.strip()), "")
                    if first_scene:
                        bound_scene = first_scene
                raw = d.get("dataB64")
                replacement = None
                if raw:
                    blob, ext = decode_image_upload(raw)
                    incoming = MEDIA / "uploads_incoming" / "asset_library"
                    incoming.mkdir(parents=True, exist_ok=True)
                    replacement = incoming / f"{kind}_{uuid.uuid4().hex[:10]}{ext}"
                    replacement.write_bytes(blob)
                rec = cb_asset_registry.update_asset(
                    asset_id,
                    label=label,
                    scene=bound_scene,
                    kind=group_kind,
                    role=f"{asset_use}_{slug(label)}",
                    status=str(d.get("status") or "draft"),
                    path=replacement,
                    metadata={
                        "libraryGroup": kind,
                        "assetUse": asset_use,
                        "filename": str(d.get("filename") or ""),
                        "description": str(d.get("description") or ""),
                        "scenes": scenes,
                    },
                )
                reindex_media()
                self._json(200, {"ok": True, "asset": rec})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path in ("/api/shot-voice-save", "/api/shot-voice-restore",
                         "/api/shot-voice-restore-take",
                         "/api/shot-voice-select-audition",
                         "/api/script-dialogue-correction",
                         "/api/shot-seedance-save", "/api/shot-seedance-restore"):
            # CONTAINED CREATIVE CONTROLS, WRITE SIDE (2026-07-19): direct, synchronous,
            # in-process calls (the same precedent as serve.py's own pre-existing
            # approve_beat() — a quick, guaranteed-cheap mutation doesn't need the
            # job-runner's streaming-log machinery). NONE of these call cb_gen — saving,
            # restoring a working version, or swapping back to a superseded audio TAKE
            # (restore-voice-take, 2026-07-19 — "show the old one and the new one... get
            # rid of one or the other") never generates audio or animation; the latter only
            # moves already-generated files that voice_shot itself archived on regeneration.
            try:
                d = self._body()
                scene = str(d.get("scene", "")).strip(); sid = str(d.get("shotId", "")).strip()
                ep = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                if not scene or not sid or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(sid) \
                   or not _SHOT_TOKEN.match(ep):
                    self._json(400, {"error": "scene, shotId (and optional episode) required as plain tokens"}); return
                if str(CBGEN) not in sys.path:
                    sys.path.insert(0, str(CBGEN))
                import cb_render as _CBR
                if self.path == "/api/script-dialogue-correction":
                    old_text = str(d.get("oldExactText") or "")
                    new_text = str(d.get("newExactText") or "").strip()
                    speaker = str(d.get("speaker") or "").strip()
                    occurrence_id = str(d.get("dialogueOccurrenceId") or "").strip()
                    if not old_text.strip() or not new_text:
                        raise ValueError("oldExactText and newExactText are required")
                    if old_text.strip() == new_text:
                        raise ValueError("the corrected words are unchanged")
                    provider_spelling = _CBR.cb_gen._eleven_voice_text(old_text).strip()
                    compare_voice_text = lambda value: re.sub(
                        r"[.!?…]+$", "", str(value or "").strip()).casefold()
                    if (provider_spelling != old_text.strip() and
                            compare_voice_text(provider_spelling) ==
                            compare_voice_text(new_text)):
                        self._json(409, {
                            "error": (
                                "Keep Aida in Approved spoken words. ElevenLabs already "
                                "receives Ada from the performance-prompt layer."),
                            "pronunciationOnly": True,
                            "canonicalText": old_text.strip(),
                            "providerText": provider_spelling,
                        })
                        return
                    current = SCRIPT_STORE.current(ep, required=True)
                    script_path = SCRIPT_STORE.content_path(ep)
                    script_text = script_path.read_text(encoding="utf-8")
                    if script_text.count(old_text) != 1:
                        raise ValueError(
                            "the exact approved line was not found once in the active script; "
                            "the correction was not applied")
                    corrected_text = script_text.replace(old_text, new_text, 1)
                    change_scope = {
                        "kind": "dialogue-correction",
                        "scene": scene,
                        "shotId": sid,
                        "dialogueOccurrenceId": occurrence_id,
                        "speaker": speaker,
                        "previousExactText": old_text,
                        "correctedExactText": new_text,
                    }
                    version = SCRIPT_STORE.store(
                        ep, corrected_text, current.get("title") or ep,
                        source_name=current.get("displayFile") or script_path.name,
                        activated_by="Julian",
                        event_kind="script-dialogue-corrected",
                        change_scope=change_scope)
                    # SCRIPT_STORE.store activates the immutable pointer immediately. Intake
                    # deliberately refuses if episodes.json still names the previous version,
                    # so publish and verify the new pointer before the child process starts.
                    # The job-finalizer reindex remains useful for publishing its output.
                    synchronize_episode_script_registry(
                        ep, version["scriptVersionId"])
                    amendment = _CBR.apply_scoped_dialogue_correction(
                        scene, sid, occurrence_id, old_text, new_text,
                        version["scriptVersionId"], current.get("scriptVersionId"), ep,
                        reviewed_by="Julian")
                    voice_job = _start(
                        _jid(f"department_voice_{sid}"),
                        f"department:voice:{sid}", scene,
                        ["cb_render.py", "department-prepare", scene,
                         "voice", sid, ep])
                    self._json(200, {"ok": True, "scriptVersionId": version["scriptVersionId"],
                                     "dialogueOccurrenceId": occurrence_id,
                                     "speaker": speaker, "providerCalled": False,
                                     "changeScope": change_scope,
                                     "affectedScene": scene, "affectedShotId": sid,
                                     "amendment": amendment,
                                     "jobId": voice_job,
                                     "voiceDirectionPreparing": True,
                                     "preservedStages": ["direction", "scenelook", "keyframe"],
                                     "invalidatedStages": ["voice", "animation", "continuity", "final"],
                                     "next": "review-hear"})
                elif self.path == "/api/shot-voice-save":
                    lines = d.get("lines") or []
                    rec = _CBR.save_voice_working(scene, sid, lines, ep)
                    self._json(200, {"ok": True, "saved": rec})
                elif self.path == "/api/shot-voice-restore":
                    _CBR.restore_voice_working(scene, sid, ep)
                    self._json(200, {"ok": True})
                elif self.path == "/api/shot-voice-restore-take":
                    _CBR.restore_previous_voice_take(scene, sid, ep)
                    self._json(200, {"ok": True})
                elif self.path == "/api/shot-voice-select-audition":
                    candidate_id = str(d.get("candidateId") or "").strip()
                    if not candidate_id:
                        raise ValueError("candidateId is required")
                    selected = _CBR.select_voice_audition(
                        scene, sid, candidate_id, ep, reviewed_by="Julian")
                    self._json(200, {"ok": True, "selected": selected})
                elif self.path == "/api/shot-seedance-save":
                    rec = _CBR.save_seedance_working(scene, sid, str(d.get("prompt") or ""), ep)
                    self._json(200, {"ok": True, "saved": rec})
                else:
                    _CBR.restore_seedance_working(scene, sid, ep)
                    self._json(200, {"ok": True})
            except _CBR.Refused as e:
                self._json(400, {"error": str(e)})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        if self.path == "/api/shot-run":
            # THE SHOT PIPELINE, front door (additive, 2026-07-16; extended same day for the probabilistic-
            # candidate contract, then the single-use SPEND-TOKEN contract): validates cmd against the exact
            # allowlist, then clones the /api/fire pattern — same _jid/_start job runner, same
            # {"ok": True, "jobId": ...} response shape. cb_render.py's own refusals (the SPEND DISCLOSURE +
            # token issue on a no-token fire/next, a stale/consumed token, red validation, relay-before-
            # approval, model-limited, an UNCONFIRMED billing_profile.json — which hard-blocks ALL paid
            # generation by design until Julian confirms his plans — and Law 5/6) all surface through the
            # job log as a failed job; for the no-token disclosure step and the billing-profile block that
            # refusal is EXPECTED protective behaviour, not a malfunction.
            try:
                d = self._body()
                cmd = str(d.get("cmd", "")).strip()
                if cmd not in SHOT_CMDS:
                    self._json(400, {"error": "unknown cmd %r — allowed: %s" % (cmd, ", ".join(SHOT_CMDS))}); return
                scene = str(d.get("scene", "")).strip()
                episode = (str(d.get("episode") or "Ep1").strip() or "Ep1")
                shot_id = str(d.get("shotId")).strip() if d.get("shotId") not in (None, "") else None
                character = (str(d.get("character")).strip()
                             if d.get("character") not in (None, "") else None)
                correction = str(d.get("correction")).strip() if d.get("correction") not in (None, "") else None
                if not scene or not _SHOT_TOKEN.match(scene) or not _SHOT_TOKEN.match(episode):
                    self._json(400, {"error": "scene and episode must be plain tokens (e.g. 1, Ep1)"}); return
                if cmd in ("fire", "voice-shot", "build-keyframe", "keyframe", "approve", "reject", "override-model-limited", "approve-keyframe", "rescreen-keyframe", "reject-keyframe",
                           "pose", "approve-pose", "reject-pose", "select-pose-upload",
                           "select-upload", "select-library", "select-previous", "select-render-upload",
                           "approve-voice", "reject-voice", "regen-voice",
                           "edit", "approve-edit", "reject-edit") \
                   and (not shot_id or not _SHOT_TOKEN.match(shot_id)):
                    self._json(400, {"error": f"{cmd} needs a shotId (e.g. 1.B1.S1)"}); return
                if cmd in ("pose", "approve-pose", "reject-pose", "select-pose-upload") and (
                        not character or not _CHARACTER_NAME.match(character)):
                    self._json(400, {"error": f"{cmd} needs a valid character name"}); return
                if cmd == "reject" and not correction:
                    self._json(400, {"error": "reject needs a one-sentence correction"}); return
                if cmd in ("edit", "reject-edit") and not correction:
                    self._json(400, {"error": f"{cmd} needs a written correction"}); return
                start_sec = d.get("startSec")
                end_sec = d.get("endSec")
                if cmd == "edit":
                    try:
                        start_sec = float(start_sec)
                        end_sec = float(end_sec)
                    except (TypeError, ValueError):
                        self._json(400, {"error": "edit needs numeric startSec and endSec"}); return
                    if start_sec < 0 or end_sec <= start_sec:
                        self._json(400, {"error": "edit endSec must be after startSec"}); return
                if cmd == "override-model-limited" and not correction:
                    self._json(400, {"error": "override-model-limited needs a written reason"}); return
                if cmd == "reject-keyframe" and not correction:
                    self._json(400, {"error": "reject-keyframe needs a plain-language reason"}); return
                if cmd == "reject-pose" and not correction:
                    self._json(400, {"error": "reject-pose needs a plain-language reason"}); return
                if cmd == "reject-scenelook" and not correction:
                    self._json(400, {"error": "reject-scenelook needs a plain-language note"}); return
                if cmd == "reject-voice" and not correction:
                    self._json(400, {"error": "reject-voice needs a plain-language reason"}); return
                if cmd == "reject-timing-slate" and not correction:
                    self._json(400, {"error": "reject-timing-slate needs a plain-language reason"}); return
                if cmd == "approve-keyframe" and d.get("candidate") not in (None, ""):
                    # SEE displays one current candidate. Approving that visible image is
                    # also the explicit A/B selection; no hidden second decision is needed.
                    keyframe_candidate = str(d.get("candidate")).strip().upper()
                    if keyframe_candidate not in ("A", "B"):
                        self._json(400, {"error": "approve-keyframe candidate must be A or B"}); return
                    _CBR = _canonical_cb_render()
                    try:
                        _CBR.select_keyframe_candidate(
                            scene, shot_id, keyframe_candidate, episode=episode,
                            log=lambda message: print(message, flush=True))
                    except _CBR.Refused as exc:
                        self._json(409, {"error": str(exc)}); return
                # THE NON-GENERATION OPENING-FRAME SOURCES (2026-07-18): 'select-upload' needs a
                # server-side path from a prior /api/shot-keyframe-upload call; 'select-library'
                # needs an item's path from /api/shot-keyframe-library — both validated as real,
                # existing files ROOTED under the approved engine/media tree (never an arbitrary
                # client-supplied path — the same containment discipline _url_from_abs enforces
                # in the other direction).
                source_path = d.get("sourcePath")
                if cmd in ("select-upload", "select-library", "select-pose-upload", "select-render-upload"):
                    if not source_path or not isinstance(source_path, str):
                        self._json(400, {"error": f"{cmd} needs a sourcePath"}); return
                    try:
                        sp = pathlib.Path(source_path).resolve()
                        if not sp.exists() or not sp.is_relative_to(MEDIA.resolve()):
                            self._json(400, {"error": "sourcePath must be an existing file under engine/media"}); return
                    except Exception:
                        self._json(400, {"error": "sourcePath is not a valid path"}); return
                    source_path = str(sp)
                elif cmd in ("select-scenelook-upload", "select-scenelook-library"):
                    # THE NON-GENERATION SCENE LOOK SOURCES (2026-07-19 — "still not letting me
                    # upload a library image, i select it then it wants to generate"): the
                    # scene-scoped mirror of select-upload/select-library above — no shotId,
                    # and the reusable-library root (cb-seed/assets) is allowed alongside
                    # engine/media, same as the scenelook cmd's own optional reference below.
                    if not source_path or not isinstance(source_path, str):
                        self._json(400, {"error": f"{cmd} needs a sourcePath"}); return
                    try:
                        sp = pathlib.Path(source_path).resolve()
                        _roots = (MEDIA.resolve(), ASSETS.resolve())
                        if not sp.exists() or not any(sp.is_relative_to(r) for r in _roots):
                            self._json(400, {"error": "sourcePath must be an existing file under "
                                                       "engine/media or cb-seed/assets"}); return
                    except Exception:
                        self._json(400, {"error": "sourcePath is not a valid path"}); return
                    source_path = str(sp)
                elif cmd == "scenelook" and source_path is not None:
                    # THE SCENE LOOK PROVIDER-ROUTING FIX (2026-07-19): OPTIONAL for this cmd — an
                    # explicitly selected location/style reference, never auto-picked from the Asset
                    # Library by this endpoint itself; omitting sourcePath entirely is the normal
                    # no-reference case. WIDENED (2026-07-19, correction — "the library has to come
                    # from the scenes houses etc"): a Scene Look reference legitimately comes from
                    # the REAL reusable library (cb-seed/assets/locations/_manifest.json entries,
                    # character house imagery, uploaded scene refs — the same sources the Scenes/
                    # Houses nav pages and /api/loclib + /api/houses already serve), not only a
                    # scene's own generation history under engine/media. Both roots are already
                    # part of the trusted static-serve allowlist (see the static-file guard below);
                    # select-upload/select-library above stay scoped to MEDIA only, since those
                    # remain the shot-owned candidate-copy mechanism, unrelated to this reference.
                    if not isinstance(source_path, str):
                        self._json(400, {"error": "sourcePath must be a string"}); return
                    try:
                        sp = pathlib.Path(source_path).resolve()
                        _roots = (MEDIA.resolve(), ASSETS.resolve())
                        if not sp.exists() or not any(sp.is_relative_to(r) for r in _roots):
                            self._json(400, {"error": "sourcePath must be an existing file under "
                                                       "engine/media or cb-seed/assets"}); return
                    except Exception:
                        self._json(400, {"error": "sourcePath is not a valid path"}); return
                    source_path = str(sp)
                elif source_path is not None:
                    self._json(400, {"error": "sourcePath applies to select-upload/select-library/select-render-upload/"
                                               "select-pose-upload/"
                                               "select-scenelook-upload/select-scenelook-library/"
                                               "scenelook only"}); return
                # THE PROBABILISTIC-CANDIDATE + SPEND-TOKEN CONTRACT (2026-07-16): candidates and the
                # single-use spendToken for fire/next, category for reject, candidate index for approve —
                # each validated, each optional.
                candidates = d.get("candidates")
                if candidates is not None:
                    if cmd not in ("fire", "next"):
                        self._json(400, {"error": "candidates applies to fire/next only"}); return
                    try:
                        candidates = int(candidates)
                    except (TypeError, ValueError):
                        candidates = -1
                    if not (1 <= candidates <= 4):
                        self._json(400, {"error": "candidates must be an integer 1-4"}); return
                spend_token = str(d.get("spendToken")).strip() if d.get("spendToken") not in (None, "") else None
                if spend_token is not None:
                    if cmd not in ("fire", "next", "edit"):
                        self._json(400, {"error": "spendToken applies to fire/next/edit only"}); return
                    if not _SPEND_TOKEN_RE.match(spend_token):
                        self._json(400, {"error": "spendToken must be 16-64 lowercase hex characters"}); return
                comparison_model_id = (str(d.get("comparisonModelId")).strip()
                                       if d.get("comparisonModelId") not in (None, "") else None)
                comparison_run_id = (str(d.get("comparisonRunId")).strip()
                                     if d.get("comparisonRunId") not in (None, "") else None)
                if comparison_model_id is not None or comparison_run_id is not None:
                    if cmd not in ("fire", "next"):
                        self._json(400, {"error": "comparison settings apply to fire/next only"}); return
                    if comparison_model_id != "fal-seedance-2.0":
                        self._json(400, {"error": "only fal-seedance-2.0 is allowed for comparison"}); return
                    if not comparison_run_id or not _SHOT_TOKEN.match(comparison_run_id) or len(comparison_run_id) > 120:
                        self._json(400, {"error": "comparisonRunId must be a bounded plain token"}); return
                category = str(d.get("category")).strip() if d.get("category") not in (None, "") else None
                if category is not None:
                    if cmd != "reject":
                        self._json(400, {"error": "category applies to reject only"}); return
                    if category not in REJECT_CATEGORIES:
                        self._json(400, {"error": "category must be one of: " + ", ".join(REJECT_CATEGORIES)}); return
                candidate = d.get("candidate")
                if candidate is not None:
                    if cmd != "approve":
                        self._json(400, {"error": "candidate applies to approve only"}); return
                    try:
                        candidate = int(candidate)
                    except (TypeError, ValueError):
                        candidate = -1
                    if not (1 <= candidate <= 4):
                        self._json(400, {"error": "candidate must be an integer 1-4"}); return
                self._json(200, {"ok": True, "jobId": shot_run_job(cmd, scene, episode, shot_id, correction,
                                                                    candidates=candidates,
                                                                    spend_token=spend_token,
                                                                    category=category, candidate=candidate,
                                                                    dry_run=bool(d.get("dryRun")),
                                                                    source_path=source_path,
                                                                    character=character,
                                                                    comparison_model_id=comparison_model_id,
                                                                    comparison_run_id=comparison_run_id,
                                                                    start_sec=start_sec,
                                                                    end_sec=end_sec)})
            except Exception as e:
                self._json(400, {"error": str(e)})
            return
        self._json(404, {"error": "not found"})

    def log_message(self, *a):
        pass

def main():
    os.chdir(ROOT)
    # T43 (2026-09-01): refuse to serve from a checkout whose compatibility links are not
    # real links (a Windows clone without symlink support turns each into a text file).
    sys.path.insert(0, str(ROOT / "tools"))
    import check_links
    _broken = check_links.broken_links(ROOT)
    if _broken:
        print("COMPATIBILITY LINKS BROKEN — the studio cannot run safely from this checkout:")
        for _line in _broken:
            print("  " + _line)
        print(check_links.FIX)
        sys.exit(2)
    # Jobs used to live only in the Python dictionary above. Restore their durable
    # ledger first, and close any row left running by a previous process honestly.
    interrupted = cb_db.interrupt_running_jobs(ROOT, server_key=SERVER_KEY)
    restored_jobs = cb_db.load_jobs(ROOT, server_key=SERVER_KEY)
    with _JOB_LOCK:
        JOBS.clear()
        JOBS.update(restored_jobs)
    reindex_media()
    episodes = reindex_episodes()
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    threading.Thread(target=_freshness_watch, daemon=True).start()
    # Finish the authoritative projection before publishing the launch URL so
    # the first browser click does not race a cold state audit.
    if os.environ.get("CB_STUDIO_SKIP_PREWARM") != "1":
        _prewarm_director_session_cache()
    # Python 3.14's cyclic collector can otherwise rescan the complete imported
    # production stack during ordinary browser polling. In the Studio process that
    # graph is immutable after prewarm; freezing it prevents multi-gigabyte GC scans
    # that leave the port listening while every browser request times out.
    gc.collect()
    if hasattr(gc, "freeze"):
        gc.freeze()
    # Python 3.14's automatic cyclic collector can spend minutes traversing the
    # dynamically imported production graph while holding the GIL. Reference
    # counting still releases ordinary request/session objects; disabling the
    # automatic collector keeps this long-running local UI responsive.
    gc.disable()
    with http.server.ThreadingHTTPServer((BIND_HOST, PORT), H) as httpd:
        base_url = PUBLIC_ORIGIN or f"http://{BIND_HOST}:{PORT}"
        launch_url = f"{base_url}/cb-studio/director.html?launchToken={LAUNCH_TOKEN}"
        print(f"Animation Studio launch URL -> {launch_url}", flush=True)
        access_mode = "HTTPS tunnel" if PUBLIC_ORIGIN else "loopback-only"
        print(
            f"Serving {ROOT} ({len(episodes)} episodes) - {access_mode}, authenticated, "
            f"threaded + byte-range; {len(restored_jobs)} durable job(s) restored, "
            f"{interrupted} interrupted; freshness guard ON (fp={_STARTED_FP:.0f})",
            flush=True,
        )
        httpd.serve_forever()


if __name__ == "__main__":
    main()
