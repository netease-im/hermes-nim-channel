from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import mimetypes
import tempfile
from typing import Any
from urllib.request import Request, urlopen


@dataclass(slots=True)
class NimInboundAttachment:
    url: str
    name: str = ""
    size: int | None = None
    mime_type: str = ""
    width: int | None = None
    height: int | None = None
    duration: int | None = None
    scene_name: str | None = None


@dataclass(slots=True)
class CachedInboundMedia:
    path: str
    media_type: str
    kind: str


def infer_media_kind(message_type: str) -> str | None:
    mapping = {
        "image": "image",
        "audio": "audio",
        "video": "video",
        "file": "document",
    }
    return mapping.get(str(message_type or "").strip().lower())


def infer_placeholder(message_type: str, attachment_url: str | None = None) -> str:
    message_type = str(message_type or "").strip().lower()
    labels = {
        "image": "[Image]",
        "audio": "[Audio]",
        "video": "[Video]",
        "file": "[File]",
    }
    prefix = labels.get(message_type, "[Attachment]")
    return f"{prefix} {attachment_url}".strip() if attachment_url else prefix


def parse_inbound_attachment(payload: dict[str, Any]) -> NimInboundAttachment | None:
    attachment = payload.get("attachment") or {}
    url = str(attachment.get("url") or "").strip()
    if not url:
        return None

    mime_type = str(attachment.get("mime_type") or "").strip()
    if not mime_type and attachment.get("name"):
        mime_type = mimetypes.guess_type(str(attachment["name"]))[0] or ""

    return NimInboundAttachment(
        url=url,
        name=str(attachment.get("name") or "").strip(),
        size=int(attachment["size"]) if attachment.get("size") not in (None, "") else None,
        mime_type=mime_type,
        width=int(attachment["width"]) if attachment.get("width") not in (None, "") else None,
        height=int(attachment["height"]) if attachment.get("height") not in (None, "") else None,
        duration=int(attachment["duration"]) if attachment.get("duration") not in (None, "") else None,
        scene_name=str(attachment.get("scene_name") or attachment.get("sceneName") or "").strip() or None,
    )


def fetch_attachment_bytes(attachment: NimInboundAttachment) -> tuple[bytes, str]:
    request = Request(
        attachment.url,
        headers={"User-Agent": "hermes-nim-channel/0.2"},
    )
    with urlopen(request, timeout=20) as response:
        data = response.read()
        mime_type = str(response.headers.get_content_type() or "").strip()
    return data, attachment.mime_type or mime_type


def cache_attachment_bytes_local(
    data: bytes,
    *,
    attachment: NimInboundAttachment,
    kind: str,
) -> CachedInboundMedia:
    suffix = Path(attachment.name).suffix
    if not suffix:
        suffix = mimetypes.guess_extension(attachment.mime_type or "") or ""
    if not suffix:
        suffix = {
            "image": ".jpg",
            "audio": ".ogg",
            "video": ".mp4",
            "document": ".bin",
        }.get(kind, ".bin")

    fd, path = tempfile.mkstemp(prefix=f"nim_{kind}_", suffix=suffix)
    with open(fd, "wb", closefd=True) as handle:
        handle.write(data)

    media_type = attachment.mime_type or mimetypes.guess_type(attachment.name or path)[0] or {
        "image": "image/jpeg",
        "audio": "audio/ogg",
        "video": "video/mp4",
        "document": "application/octet-stream",
    }.get(kind, "application/octet-stream")

    return CachedInboundMedia(path=path, media_type=media_type, kind=kind)
