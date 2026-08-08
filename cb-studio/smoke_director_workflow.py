#!/usr/bin/env python3
"""Authenticated smoke audit for the local Director Studio workflow.

This is intentionally a live local-server check, not a unit test. It catches the
class of failures where the package is correct but the browser-facing API/UI still
shows stale state.
"""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import sys
import urllib.parse
import urllib.request


def _opener():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def _get(opener, base_url, path):
    with opener.open(base_url + path, timeout=30) as response:
        body = response.read()
    return json.loads(body.decode("utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8899")
    parser.add_argument("--launch-token", required=True)
    parser.add_argument("--episode", default="Ep1")
    parser.add_argument("--scene", default="1")
    parser.add_argument("--shot", default="S1.SH1A")
    args = parser.parse_args(argv)

    base = args.base_url.rstrip("/")
    opener = _opener()
    launch = (
        f"{base}/cb-studio/director.html?launchToken="
        f"{urllib.parse.quote(args.launch_token)}"
    )
    opener.open(launch, timeout=30).read()

    query = urllib.parse.urlencode({
        "episode": args.episode,
        "scene": args.scene,
        "shotId": args.shot,
    })
    session = _get(opener, base, f"/api/director-session?{query}")
    voice = _get(opener, base, f"/api/shot-voice-status?{query}")
    refs = _get(opener, base, f"/api/shot-references?{query}")

    checks = [
        ("selected shot", session.get("selectedShotId") == args.shot,
         session.get("selectedShotId")),
        ("phase available", bool(session.get("phase")), session.get("phase")),
        ("actions available", bool(session.get("primaryAction") or session.get("decisionActions")),
         [session.get("primaryAction"), *(session.get("decisionActions") or [])]),
        ("voice status readable", "error" not in voice, voice.get("error")),
        ("voice take URL present when take exists",
         (not voice.get("hasTake")) or bool(voice.get("takeUrl")), voice.get("takeUrl")),
        ("voice take current when present",
         (not voice.get("hasTake")) or voice.get("takeMatchesCurrent") is True,
         voice.get("takeMatchesCurrent")),
        ("keyframe references", bool((refs.get("keyframe") or {}).get("references")),
         len((refs.get("keyframe") or {}).get("references") or [])),
        ("animation references", bool((refs.get("animation") or {}).get("references")),
         len((refs.get("animation") or {}).get("references") or [])),
    ]

    failed = False
    for name, ok, detail in checks:
        print(f"{'OK' if ok else 'FAIL'} {name}: {detail}")
        failed = failed or not ok
    if failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
