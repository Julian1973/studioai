"""Make every provider call trust the certificates this machine already trusts.

2026-09-02, the PC: every OpenAI call failed with `APIConnectionError: Connection error.`, and
under it `[SSL: CERTIFICATE_VERIFY_FAILED] unable to get local issuer certificate`. Nothing was
wrong with the key, the model or the network — Norton's Web/Mail Shield is intercepting HTTPS on
this machine and re-issuing every certificate under its own root:

    api.openai.com                    issuer: Norton Web/Mail Shield
    api.elevenlabs.io                 issuer: Norton Web/Mail Shield
    fal.run                           issuer: Norton Web/Mail Shield
    ark.ap-southeast.bytepluses.com   issuer: Norton Web/Mail Shield

Windows trusts that root, so curl and Python's own `ssl.create_default_context()` are fine. httpx
and requests are not: they verify against certifi's bundle, which of course has never heard of it,
so every SDK built on them refuses the connection and reports it as a transport failure.

This module merges the machine's own root store into certifi's bundle, writes the result beside
the virtualenv, and points every library at it — the env vars requests and urllib3 read, and
`certifi.where()` itself, which is what httpx (and so the OpenAI SDK) asks at client construction.
It adds no trust the operating system has not already granted; it only stops Python disagreeing
with the rest of the machine. On anything but Windows, and on a Windows box with no interception,
it is a no-op beyond writing the same bundle certifi already had.

The alternative is to turn off Norton's HTTPS scanning, which is Julian's call, not the studio's.
"""
from __future__ import annotations

import os
import pathlib
import ssl

BUNDLE_NAME = "cacert-with-machine-roots.pem"
_APPLIED = False


def _machine_root_pems() -> list[str]:
    """Every trusted root this machine holds, PEM-encoded. Empty off Windows."""
    if not hasattr(ssl, "enum_certificates"):
        return []
    pems: list[str] = []
    for store in ("ROOT", "CA"):
        try:
            entries = ssl.enum_certificates(store)
        except Exception:
            continue
        for der, encoding, trust in entries:
            # trust is True for "all purposes", else a FROZENset of enhanced-key-usage OIDs;
            # 1.3.6.1.5.5.7.3.1 is server authentication. Testing `isinstance(trust, set)` here
            # silently excluded every restricted root — frozenset is not a subclass of set — and
            # the one root that mattered, Norton's, carries exactly {serverAuth}.
            if trust is not True:
                try:
                    if "1.3.6.1.5.5.7.3.1" not in trust:
                        continue
                except TypeError:
                    continue
            if encoding != "x509_asn":
                continue
            try:
                pems.append(ssl.DER_cert_to_PEM_cert(der))
            except Exception:
                continue
    return pems


def bundle_path() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent / ".venv" / BUNDLE_NAME


def build_bundle(force: bool = False) -> pathlib.Path | None:
    """Write certifi's bundle plus this machine's own roots, and return the path."""
    try:
        import certifi
    except Exception:
        return None
    base = pathlib.Path(getattr(certifi, "_ORIGINAL_WHERE", certifi.where)())
    try:
        base_text = base.read_text(encoding="utf-8")
    except OSError:
        return None
    extra = [pem for pem in _machine_root_pems() if pem not in base_text]
    target = bundle_path()
    if not extra and not force:
        return base                       # nothing to add: certifi's own bundle is enough
    body = base_text.rstrip("\n") + "\n" + "".join(extra)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if force or not target.exists() or target.read_text(encoding="utf-8") != body:
            target.write_text(body, encoding="utf-8")
    except OSError:
        return None
    return target


def apply(force: bool = False) -> pathlib.Path | None:
    """Point requests, urllib3, httpx and anything reading certifi at the merged bundle."""
    global _APPLIED
    if _APPLIED and not force:
        return bundle_path() if bundle_path().exists() else None
    path = build_bundle(force=force)
    if path is None:
        return None
    _APPLIED = True
    value = str(path)
    os.environ.setdefault("SSL_CERT_FILE", value)
    os.environ.setdefault("REQUESTS_CA_BUNDLE", value)
    try:
        import certifi
        if not hasattr(certifi, "_ORIGINAL_WHERE"):
            certifi._ORIGINAL_WHERE = certifi.where          # so a rebuild reads the real one
        certifi.where = lambda: value                        # httpx asks this at client build
        import certifi.core
        certifi.core.where = certifi.where
    except Exception:
        pass
    return path


if __name__ == "__main__":
    import socket
    result = apply(force=True)
    print("bundle:", result)
    intercepted = []
    for host in ("api.openai.com", "api.elevenlabs.io", "fal.run",
                 "ark.ap-southeast.bytepluses.com"):
        try:
            with socket.create_connection((host, 443), timeout=12) as raw:
                context = ssl.create_default_context()
                with context.wrap_socket(raw, server_hostname=host) as tls:
                    issuer = dict(item[0] for item in tls.getpeercert().get("issuer", ()))
                    name = issuer.get("organizationName") or issuer.get("commonName") or "?"
            print(f"{host:34} issuer: {name}")
            if "Norton" in name or "Shield" in name:
                intercepted.append(host)
        except Exception as exc:
            print(f"{host:34} {type(exc).__name__}: {exc}")
    print("intercepted:", intercepted or "none")
