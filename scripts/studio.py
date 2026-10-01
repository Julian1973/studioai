#!/usr/bin/env python3
"""Install, inspect and launch a Studio workstation without exposing credentials."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import pathlib
import shutil
import subprocess
import sys
import venv

ROOT = pathlib.Path(__file__).resolve().parents[1]
ENV_DIR = ROOT / ".venv-studio"
LOCK = ROOT / "requirements-studio.lock"


def environment_python():
    return ENV_DIR / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def load_configuration(root=ROOT):
    """The workstation's environment wins; files never execute shell commands."""
    path = pathlib.Path(root) / "engine/.env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                name, value = line.split("=", 1)
                if name.strip().replace("_", "").isalnum():
                    os.environ.setdefault(name.strip(), value.strip())


def locked_versions():
    return dict(line.split("==", 1) for line in LOCK.read_text().splitlines()
                if line.strip() and not line.startswith("#"))


def doctor(show=None):
    load_configuration()
    checks = []
    def check(name, ready, detail):
        checks.append({"name": name, "ready": bool(ready), "detail": detail})
    check("python", sys.version_info[:2] == (3, 12),
          "Python 3.12 is the qualified candidate runtime")
    mismatches = []
    for package, expected in locked_versions().items():
        try:
            actual = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            actual = "missing"
        if actual != expected:
            mismatches.append(f"{package}: expected {expected}, found {actual}")
    check("dependencies", not mismatches, mismatches or "Pinned dependencies match")
    for executable in ("ffmpeg", "ffprobe", "node"):
        check(executable, shutil.which(executable) is not None,
              "Available" if shutil.which(executable) else "Install and add to PATH")
    sys.path.insert(0, str(ROOT / "engine"))
    profile = None
    try:
        import studio_profile
        profile = studio_profile.capability_report(studio_profile.load_show_profile(ROOT, show))
        check("show-profile", True, profile["showId"])
    except (ImportError, RuntimeError, ValueError) as exc:
        check("show-profile", False, str(exc))
    # Presence only: never echo, validate remotely, or call a paid model.
    providers = {name: bool(os.environ.get(name, "").strip()) for name in (
        "OPENAI_API_KEY", "ELEVENLABS_API_KEY", "BYTEPLUS_ARK_API_KEY")}
    return {"schemaVersion": 1, "zeroSpend": True,
            "workstationReady": all(row["ready"] for row in checks),
            "checks": checks, "show": profile,
            "providerKeysPresent": providers,
            "productionQualified": False,
            "qualificationNote": "A clean doctor report does not approve canon, billing or live provider delivery."}


def install(verify=False):
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("Install with Python 3.12; other Python versions are not qualified")
    if not environment_python().exists():
        if ENV_DIR.exists():
            raise RuntimeError("Incomplete .venv-studio directory; preserve it and investigate before reinstalling")
        venv.EnvBuilder(with_pip=True).create(ENV_DIR)
    python = str(environment_python())
    subprocess.run([python, "-m", "pip", "install", "-r", str(LOCK)], cwd=ROOT, check=True)
    subprocess.run([python, "-m", "pip", "check"], cwd=ROOT, check=True)
    if verify:
        subprocess.run([python, "-m", "pytest", "-q"], cwd=ROOT, check=True)
    print("Studio environment installed. Run: python3 scripts/studio.py doctor")


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("install", "doctor", "run"))
    parser.add_argument("--show")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(arguments)
    try:
        if args.command == "install":
            install(args.verify)
            return 0
        python = environment_python()
        if python.exists() and pathlib.Path(sys.prefix).resolve() != ENV_DIR.resolve():
            return subprocess.call([str(python), str(pathlib.Path(__file__).resolve()), *arguments], cwd=ROOT)
        report = doctor(args.show)
        if args.command == "doctor":
            print(json.dumps(report, indent=2))
            return 0 if report["workstationReady"] else 1
        if not report["workstationReady"]:
            print(json.dumps(report, indent=2))
            return 1
        environment = os.environ.copy()
        if args.show:
            environment["STUDIO_SHOW"] = args.show
        return subprocess.call([sys.executable, str(ROOT / "cb-studio/serve.py")], cwd=ROOT, env=environment)
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Studio setup stopped: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
