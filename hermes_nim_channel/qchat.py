from __future__ import annotations

from typing import Iterable


def build_qchat_chat_id(server_id: str, channel_id: str) -> str:
    server = str(server_id or "").strip()
    channel = str(channel_id or "").strip()
    if not server or not channel:
        raise ValueError("server_id and channel_id are required")
    return f"qchat:{server}:{channel}"


def parse_qchat_chat_id(chat_id: str) -> tuple[str, str] | None:
    raw = str(chat_id or "").strip()
    if not raw:
        return None

    lowered = raw.lower()
    matched_prefix = None
    for prefix in ("nim:qchat:", "qchat:"):
        if lowered.startswith(prefix):
            raw = raw[len(prefix) :]
            matched_prefix = prefix
            break

    if matched_prefix is None:
        return None

    parts = raw.split(":", 1)
    if len(parts) != 2:
        return None

    server_id = parts[0].strip()
    channel_id = parts[1].strip()
    if not server_id or not channel_id:
        return None
    return server_id, channel_id


def is_qchat_allowed(
    *,
    policy: str,
    allow_from: Iterable[str | int],
    server_id: str,
    channel_id: str,
    sender_accid: str,
) -> bool:
    normalized_policy = str(policy or "").strip().lower()
    if normalized_policy == "disabled":
        return False
    if normalized_policy == "open":
        return True

    allow_entries = [str(entry).strip().lower() for entry in allow_from if str(entry).strip()]
    if not allow_entries:
        return False

    server = str(server_id or "").strip().lower()
    channel = str(channel_id or "").strip().lower()
    sender = str(sender_accid or "").strip().lower()

    for entry in allow_entries:
        parts = entry.split("|")
        entry_server = parts[0].strip().lower() if len(parts) > 0 else ""
        entry_channel = parts[1].strip().lower() if len(parts) > 1 else ""
        entry_sender = parts[2].strip().lower() if len(parts) > 2 else ""

        if not entry_server or entry_server != server:
            continue
        if entry_channel and entry_channel != channel:
            continue
        if entry_sender and entry_sender != sender:
            continue
        return True

    return False
