from __future__ import annotations

from typing import Any, Mapping


def normalize_topic_id(value: Any) -> int | None:
    try:
        topic_id = int(value)
    except (TypeError, ValueError):
        return None
    return topic_id if topic_id > 0 else None


def build_topic_chat_id(account_id: str, topic_id: Any) -> str:
    account = str(account_id or "").strip()
    normalized_topic_id = normalize_topic_id(topic_id)
    if not account or normalized_topic_id is None:
        raise ValueError("account_id and a positive topic_id are required")
    return f"user:{account}:topic:{normalized_topic_id}"


def parse_topic_chat_id(chat_id: str) -> tuple[str, int] | None:
    raw = str(chat_id or "").strip()
    if not raw.startswith("user:"):
        return None
    target = raw[len("user:") :]
    marker = ":topic:"
    if marker not in target:
        return None
    account, raw_topic_id = target.rsplit(marker, 1)
    topic_id = normalize_topic_id(raw_topic_id)
    if not account or topic_id is None:
        return None
    return account, topic_id


def topic_id_from_metadata(metadata: Mapping[str, Any] | None) -> int | None:
    if not metadata:
        return None
    for value in (
        metadata.get("topic_id"),
        metadata.get("topicId"),
        (metadata.get("topic_refer") or {}).get("topicId")
        if isinstance(metadata.get("topic_refer"), Mapping)
        else None,
        (metadata.get("topic_info") or {}).get("topicId")
        if isinstance(metadata.get("topic_info"), Mapping)
        else None,
    ):
        topic_id = normalize_topic_id(value)
        if topic_id is not None:
            return topic_id
    return None


def resolve_topic_id(chat_id: str, metadata: Mapping[str, Any] | None = None) -> int | None:
    parsed = parse_topic_chat_id(chat_id)
    return parsed[1] if parsed is not None else topic_id_from_metadata(metadata)


def derive_stream_id(chat_id: str, reply_to: str | None, explicit: Any = None) -> str:
    normalized = str(explicit or "").strip()
    if normalized:
        return normalized
    return f"hermes:{str(chat_id or '').strip()}:{str(reply_to or '').strip()}"


def append_topic_to_conversation_name(name: Any, topic_name: Any) -> str | None:
    conversation = str(name or "").strip()
    topic = str(topic_name or "").strip()
    if not conversation:
        return topic or None
    if not topic or conversation.endswith(f" · {topic}"):
        return conversation
    return f"{conversation} · {topic}"


QCHAT_CONVERSATION_PREFIX = "云信·圈组·"


def qchat_channel_display_name(channel_name: Any, server_id: Any, channel_id: Any) -> str:
    name = str(channel_name or "").strip()
    if name.startswith(QCHAT_CONVERSATION_PREFIX):
        name = name[len(QCHAT_CONVERSATION_PREFIX):].strip()
    if name:
        return name
    server = str(server_id or "").strip()
    channel = str(channel_id or "").strip()
    if server and channel:
        return f"{server}:{channel}"
    return server or channel or "unknown"


def build_qchat_conversation_name(channel_name: Any, server_id: Any, channel_id: Any) -> str:
    display_name = qchat_channel_display_name(channel_name, server_id, channel_id)
    return f"{QCHAT_CONVERSATION_PREFIX}{display_name}"


def qchat_context_text(text: Any, channel_name: Any, channel_topic: Any) -> str:
    original = str(text or "")
    name = str(channel_name or "").strip()
    topic = str(channel_topic or "").strip()
    parts = []
    if name:
        parts.append(f"channel={name}")
    if topic:
        parts.append(f"topic={topic}")
    if not parts:
        return original
    prefix = f"[QChat {'; '.join(parts)}]"
    if original == prefix or original.startswith(f"{prefix}\n"):
        return original
    return f"{prefix}\n{original}" if original else prefix


def qchat_media_fallback_text(caption: Any, media_path: Any) -> str:
    normalized_caption = str(caption or "").strip()
    normalized_path = str(media_path or "").strip()
    return "\n".join(part for part in (normalized_caption, normalized_path) if part)
