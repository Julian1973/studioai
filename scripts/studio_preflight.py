#!/usr/bin/env python3
"""Zero-spend installation diagnostics. Never prints credentials or contacts providers."""
import importlib.util
import json
import pathlib
import platform
import shutil
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))


def report():
    checks = {
        "python": {"ready": sys.version_info >= (3, 10), "version": platform.python_version()},
        "dependencies": {name: importlib.util.find_spec(name) is not None
                         for name in ("pydantic", "requests", "openai", "fal_client", "PIL", "numpy", "scipy")},
        "mediaTools": {name: shutil.which(name) is not None for name in ("ffmpeg", "ffprobe")},
    }
    provider = {}
    errors = []
    try:
        import cb_gen
        import cb_providers
        import studio_profile
        selected = cb_providers.video_model(require_enabled=False)
        provider = {
            "byteplusCredentialPresent": bool(cb_gen.BYTEPLUS_ARK_KEY),
            "elevenlabsCredentialPresent": bool(cb_gen.ELEVEN_KEY),
            "selectedVideoModel": selected.modelId,
            "qualifiedResolutions": selected.resolutions,
            "videoRouteEnabled": selected.enabled,
        }
        checks["show"] = studio_profile.capability_report(studio_profile.load_show_profile(ROOT))
    except Exception as exc:
        # Exception messages from imports/configuration can contain local paths but
        # should never be used as a place to print provider credentials.
        errors.append(type(exc).__name__)
    local_ready = (checks["python"]["ready"] and all(checks["dependencies"].values())
                   and all(checks["mediaTools"].values()) and not errors)
    return {
        "zeroSpend": True, "platform": platform.system(), "checks": checks,
        "providers": provider, "configurationErrors": errors,
        "localPrerequisitesReady": local_ready,
        "livePrerequisitesReady": bool(local_ready and provider.get("videoRouteEnabled")
            and provider.get("byteplusCredentialPresent") and provider.get("elevenlabsCredentialPresent")
            and checks.get("show", {}).get("productionReady")),
        "productionCertified": False,
        "remainingVerification": ["Live generation and delivery", "Provider recovery reconciliation",
                                  "Studio Mac installation and restore"],
    }


if __name__ == "__main__":
    print(json.dumps(report(), indent=2))
