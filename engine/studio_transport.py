"""Explicit-credential provider adapters used by the project production service.

Never retry a generation POST automatically. A lost response may already have
incurred spend; only a known asynchronous task can be resumed without resubmitting.
"""
from __future__ import annotations

import base64
import ipaddress
import json
import mimetypes
from pathlib import Path
import socket
import subprocess
from urllib.parse import urlsplit
from typing import Literal

import requests
import urllib3
from pydantic import BaseModel, ConfigDict, Field

from studio_workspace import PROVIDERS, StudioError


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Dialogue(StrictModel):
    speaker: str
    text: str
    delivery: Literal["neutral", "whispering", "laughs", "sighs", "crying", "excited", "sad", "curious"]


class StateBinding(StrictModel):
    character: str
    stateId: str


class IdentityClaim(StrictModel):
    character: str
    trait: str
    value: str


class PerformanceBeat(StrictModel):
    at: float
    action: str
    audienceFeeling: str


class Shot(StrictModel):
    id: str
    scene: int
    startLine: int
    endLine: int
    title: str
    emotion: str
    performance: str
    camera: str
    geography: str
    transition: str
    duration: int
    characters: list[str]
    location: str
    props: list[str]
    dialogue: list[Dialogue]
    seePrompt: str
    watchPrompt: str
    intent: str = ""
    openingState: str = ""
    endingState: str = ""
    beatPlan: list[PerformanceBeat] = Field(default_factory=list)
    characterStates: list[StateBinding] = Field(default_factory=list)
    identityClaims: list[IdentityClaim] = Field(default_factory=list)


class EpisodePlan(StrictModel):
    message: str
    shots: list[Shot] = Field(min_length=1, max_length=120)


class AgentReply(StrictModel):
    message: str
    revisedShot: Shot | None


ERRORS = {
    401: ("authentication_failed", "The provider rejected this API key. Reconnect it in Workspace connections."),
    402: ("balance_required", "The provider account needs credit. Add credit, then return to this job."),
    403: ("permission_required", "This key lacks access to the requested service or model. Check its provider permissions."),
    404: ("model_unavailable", "The selected provider model or task is unavailable. Check the project service and account region."),
    429: ("provider_limit", "The provider reports a rate or account limit. Check the account before retrying."),
}


def provider_error(status, provider_code=""):
    normalized = str(provider_code).lower().replace("-", "_").replace(".", "_")
    if any(part in normalized for part in ("insufficient_balance", "insufficient_quota", "insufficient_credit", "quota_exceeded", "accountarrearage")):
        return StudioError("The provider account has no available generation allowance or credit. Check its balance and quota, then return to this job.", "balance_required")
    code, message = ERRORS.get(status, ("provider_rejected", "The provider rejected the request. Check the selected model and its supported inputs."))
    if status >= 500:
        code, message = "submission_unknown", "The provider did not confirm the request. Check the provider account before submitting again."
    return StudioError(message, code)


class ProviderTransport:
    def request(self, connection, key, path, *, body=None):
        provider = PROVIDERS[connection["provider"]]
        headers = {"xi-api-key": key} if connection["provider"] == "elevenlabs" else {"Authorization": "Bearer " + key}
        try:
            response = requests.request("GET" if body is None else "POST", provider["base"] + path,
                                        headers=headers, json=body, timeout=(15, 180), allow_redirects=False)
        except requests.RequestException:
            raise StudioError("The provider response was interrupted. Check the account before resubmitting a generation.",
                              "submission_unknown" if body is not None else "provider_offline") from None
        if not 200 <= response.status_code < 300:
            code = ""
            try:
                body = response.json()
                detail = body.get("error") or body.get("detail") or {}
                if isinstance(detail, dict):
                    code = detail.get("code") or detail.get("status") or ""
            except (ValueError, AttributeError, TypeError):
                pass
            raise provider_error(response.status_code, code)
        return response

    def check(self, connection, key):
        self.request(connection, key, PROVIDERS[connection["provider"]]["check"])

    def direct(self, connection, key, model, system, context, *, planning=False, images=None):
        from openai import OpenAI
        try:
            # Do not inherit SDK retries, project headers, custom base URLs or env keys.
            client = OpenAI(api_key=key, base_url=PROVIDERS["openai"]["base"], max_retries=0,
                            timeout=180, organization="", project="")
            content = [{"type": "input_text", "text": json.dumps(context, ensure_ascii=False)}]
            content += [{"type": "input_image", "image_url": self.inline(path), "detail": "auto"} for path in (images or [])]
            response = client.responses.parse(
                model=model, store=False, max_output_tokens=16000 if planning else 5000,
                input=[{"role": "system", "content": [{"type": "input_text", "text": system}]},
                       {"role": "user", "content": content}],
                text_format=EpisodePlan if planning else AgentReply)
            if response.output_parsed is None:
                raise StudioError("The director did not return a complete proposal. Your existing shots are unchanged.", "invalid_output")
            return response.output_parsed.model_dump()
        except StudioError:
            raise
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            if status:
                raise provider_error(status, getattr(exc, "code", "")) from None
            raise StudioError("The director response was interrupted or incomplete. Your approved work is preserved.", "submission_unknown") from None

    @staticmethod
    def inline(path):
        path = Path(path)
        if path.stat().st_size > 15 * 1024 * 1024:
            raise StudioError("This reference is too large. Supply a reference smaller than 15 MB.")
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = path.read_bytes()
        if mime.startswith("audio/") and path.suffix != ".wav":
            try:
                data = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "44100", "-f", "wav", "pipe:1"],
                                      capture_output=True, timeout=60, check=True).stdout
                mime = "audio/wav"
            except (OSError, subprocess.SubprocessError):
                raise StudioError("The voice reference could not be decoded.", "invalid_media") from None
        return "data:" + mime + ";base64," + base64.b64encode(data).decode()

    def image(self, connection, key, model, prompt, references, output, *, received=None):
        body = {"model": model, "prompt": prompt, "size": "2K", "watermark": False,
                "response_format": "url", "output_format": "png"}
        if references:
            body["image"] = [self.inline(p) for p in references]
        response = self.request(connection, key, "/images/generations", body=body)
        try:
            url = response.json()["data"][0]["url"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise StudioError("The image provider returned no usable image. Check the request in the provider account.", "invalid_output") from None
        if received:
            received(url)
        self.download(url, output)
        self.verify_media(output, "image")

    def voice(self, connection, key, model, dialogue, output):
        response = self.request(connection, key, "/v1/text-to-dialogue", body={"model_id": model, "inputs": dialogue})
        Path(output).write_bytes(response.content)
        self.verify_media(output, "audio")

    def video_submit(self, connection, key, model, prompt, images, audio, duration, *, ratio="16:9"):
        content = [{"type": "text", "text": prompt}]
        content += [{"type": "image_url", "image_url": {"url": self.inline(p)}, "role": "reference_image"} for p in images]
        content += [{"type": "audio_url", "audio_url": {"url": self.inline(p)}, "role": "reference_audio"} for p in audio]
        response = self.request(connection, key, "/contents/generations/tasks", body={
            "model": model, "content": content, "duration": duration, "resolution": "480p", "ratio": ratio,
            "generate_audio": True, "watermark": False, "return_last_frame": True})
        try:
            task_id = response.json()["id"]
            from studio_workspace import token
            return token(task_id)
        except (ValueError, KeyError, TypeError):
            raise StudioError("The provider did not return a task ID. Check the provider account before another submission.", "submission_unknown") from None

    def video_poll(self, connection, key, task_id, output):
        from studio_workspace import token
        response = self.request(connection, key, "/contents/generations/tasks/" + token(task_id))
        try:
            result = response.json()
            state = result["status"]
            if state in {"failed", "expired", "cancelled"}:
                raise StudioError("The provider could not finish this render. Its task ID is saved for account review.", "generation_failed")
            if state != "succeeded":
                return False
            self.download(result["content"]["video_url"], output)
            self.verify_media(output, "video")
            return True
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, StudioError):
                raise
            raise StudioError("The provider returned an incomplete task status. Resume this same job to check again.", "invalid_output") from None

    @staticmethod
    def download(url, output):
        # Provider-returned URLs are untrusted. Never send keys to a media host or
        # follow a redirect into the local server/cloud metadata network.
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.username or parsed.password or not parsed.hostname:
            raise StudioError("The provider returned an unsafe media address.", "invalid_output")
        try:
            addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
            if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
                raise StudioError("The provider returned a private media address.", "invalid_output")
            # Pin the validated address for the TLS connection to prevent a second
            # DNS lookup from redirecting the fetch into a private network.
            address = addresses[0][4][0]
            pool = urllib3.HTTPSConnectionPool(address, parsed.port or 443, server_hostname=parsed.hostname,
                                               assert_hostname=parsed.hostname, cert_reqs="CERT_REQUIRED",
                                               ca_certs=requests.certs.where())
            target = parsed.path or "/"
            if parsed.query:
                target += "?" + parsed.query
            response = pool.request("GET", target, headers={"Host": parsed.netloc},
                                    timeout=urllib3.Timeout(connect=15, read=120), preload_content=False,
                                    retries=False, redirect=False)
            if response.status != 200:
                response.close()
                pool.close()
                raise StudioError("The generated media download is unavailable. Resume the saved task to recover it.", "download_failed")
            total = 0
            try:
                with Path(output).open("wb") as stream:
                    for chunk in response.stream(1024 * 1024):
                        total += len(chunk)
                        if total > 250 * 1024 * 1024:
                            raise StudioError("The generated media exceeds the download limit.", "invalid_output")
                        stream.write(chunk)
            finally:
                response.close()
                pool.close()
        except (requests.RequestException, urllib3.exceptions.HTTPError, OSError):
            raise StudioError("The media download was interrupted. Resume the saved task to recover it.", "download_failed") from None

    @staticmethod
    def verify_media(path, kind):
        try:
            if kind == "image":
                from PIL import Image
                with Image.open(path) as image:
                    image.verify()
                return 0
            probe = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                                   capture_output=True, timeout=30, check=True)
            data = json.loads(probe.stdout)
            if not any(s["codec_type"] == kind for s in data["streams"]):
                raise ValueError()
            duration = float(data["format"]["duration"])
            if duration <= 0:
                raise ValueError()
            return duration
        except Exception:
            raise StudioError("The returned media is incomplete or cannot be decoded. It has not been marked ready.", "invalid_media") from None
