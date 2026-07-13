from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import BasePlatformAdapter, MessageEvent, MessageType, SendResult, cache_media_bytes
from gateway.session import SessionSource

from hermes_nim_channel.config import load_nim_config
from hermes_nim_channel.inbound_media import infer_media_kind, parse_inbound_attachment
from hermes_nim_channel.qchat import (
    build_qchat_chat_id,
    is_qchat_allowed,
    is_qchat_target_allowed,
    parse_qchat_chat_id,
)
from hermes_nim_channel.platforms.nim_bridge import NodeBridgeProcess


class HermesNimAdapter(BasePlatformAdapter):
    def __init__(self, config: PlatformConfig) -> None:
        super().__init__(config=config, platform=Platform("nim"))
        self.resolved = load_nim_config(config)
        self._bridge = NodeBridgeProcess(self.resolved.bridge_command)
        self._chat_names: dict[str, str | None] = {}

    async def connect(self) -> bool:
        if not self.resolved.configured():
            self._set_fatal_error(
                "config_missing",
                "NIM credentials are not configured",
                retryable=False,
            )
            return False
        await self._bridge.start(self.resolved, event_handler=self._on_bridge_event)
        self._mark_connected()
        return True

    async def disconnect(self) -> None:
        await self._bridge.stop()
        self._mark_disconnected()

    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SendResult:
        session_type = self._infer_session_type(chat_id, metadata)
        if session_type == "qchat":
            target = parse_qchat_chat_id(chat_id)
            if target is None:
                return SendResult(success=False, error=f"invalid QChat target: {chat_id}")
            server_id, channel_id = target
            if not is_qchat_target_allowed(
                policy=self.resolved.qchat_policy,
                allow_from=self.resolved.qchat_allow_from,
                server_id=server_id,
                channel_id=channel_id,
            ):
                return SendResult(success=False, error="qchat send blocked by policy")
            result = await self._bridge.send_qchat_message(
                chat_id=chat_id,
                text=str(content or ""),
                session_type=session_type,
                reply_to=reply_to or (metadata or {}).get("reply_to"),
            )
        else:
            result = await self._bridge.send_text(
                chat_id=chat_id,
                text=str(content or ""),
                session_type=session_type,
                reply_to=reply_to or (metadata or {}).get("reply_to"),
            )
        return SendResult(
            success=True,
            message_id=str(result.get("message_id") or result.get("client_message_id") or ""),
            raw_response=result,
        )

    async def send_image_file(
        self,
        chat_id: str,
        image_path: str,
        caption: str | None = None,
        reply_to: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs,
    ) -> SendResult:
        return await self._send_media_with_optional_caption(
            chat_id=chat_id,
            file_path=image_path,
            media_kind="image",
            caption=caption,
            reply_to=reply_to,
            metadata=metadata,
        )

    async def send_document(
        self,
        chat_id: str,
        file_path: str,
        caption: str | None = None,
        file_name: str | None = None,
        reply_to: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs,
    ) -> SendResult:
        return await self._send_media_with_optional_caption(
            chat_id=chat_id,
            file_path=file_path,
            media_kind="file",
            caption=caption,
            reply_to=reply_to,
            metadata=metadata,
        )

    async def send_voice(
        self,
        chat_id: str,
        audio_path: str,
        caption: str | None = None,
        reply_to: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs,
    ) -> SendResult:
        return await self._send_media_with_optional_caption(
            chat_id=chat_id,
            file_path=audio_path,
            media_kind="audio",
            caption=caption,
            reply_to=reply_to,
            metadata=metadata,
        )

    async def send_video(
        self,
        chat_id: str,
        video_path: str,
        caption: str | None = None,
        reply_to: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs,
    ) -> SendResult:
        return await self._send_media_with_optional_caption(
            chat_id=chat_id,
            file_path=video_path,
            media_kind="video",
            caption=caption,
            reply_to=reply_to,
            metadata=metadata,
        )

    async def get_chat_info(self, chat_id: str) -> dict[str, Any]:
        if parse_qchat_chat_id(chat_id) is not None:
            return {
                "name": self._chat_names.get(chat_id) or chat_id,
                "type": "group",
            }
        return {
            "name": self._chat_names.get(chat_id) or chat_id,
            "type": "group" if chat_id.startswith("team:") else "dm",
        }

    async def _on_bridge_event(self, envelope: dict[str, Any]) -> None:
        if envelope.get("event") != "message":
            return
        payload = dict(envelope.get("payload") or {})
        if self._should_ignore(payload):
            return
        event = await self._to_message_event(payload)
        self._chat_names[event.source.chat_id] = event.source.chat_name
        await self.handle_message(event)

    def _should_ignore(self, payload: dict[str, Any]) -> bool:
        if payload.get("from_self"):
            return True
        session_type = str(payload.get("session_type") or "p2p")
        sender_id = str(payload.get("sender_id") or "")
        if session_type == "p2p":
            return not self._is_allowed_direct_sender(sender_id)
        if session_type in {"team", "superTeam"}:
            if not self._is_allowed_group(str(payload.get("target_id") or "")):
                return True
            return not self._is_mentioned(payload)
        if session_type == "qchat":
            if not self._is_mentioned(payload):
                return True
            server_id, channel_id = self._resolve_qchat_target(payload)
            if not server_id or not channel_id:
                return True
            return not is_qchat_allowed(
                policy=self.resolved.qchat_policy,
                allow_from=self.resolved.qchat_allow_from,
                server_id=server_id,
                channel_id=channel_id,
                sender_accid=sender_id,
            )
        return True

    def _is_allowed_direct_sender(self, sender_id: str) -> bool:
        if self.resolved.p2p_policy == "disabled":
            return False
        if self.resolved.p2p_policy == "open":
            return True
        if self.resolved.p2p_policy == "allowlist":
            return sender_id in self.resolved.p2p_allow_from
        if self.resolved.allow_all_users:
            return True
        if not self.resolved.allowed_users:
            return True
        return sender_id in self.resolved.allowed_users

    def _is_allowed_group(self, target_id: str) -> bool:
        policy = self.resolved.group_policy
        if policy == "disabled":
            return False
        if policy == "open":
            return True
        return target_id in self.resolved.group_allowlist

    def _is_mentioned(self, payload: dict[str, Any]) -> bool:
        if payload.get("mentioned") or payload.get("mention_all"):
            return True
        force_push_ids = {str(item) for item in payload.get("force_push_account_ids") or []}
        account = self.resolved.credentials.account if self.resolved.credentials else ""
        return bool(account and account in force_push_ids)

    def _resolve_qchat_target(self, payload: dict[str, Any]) -> tuple[str, str]:
        parsed = parse_qchat_chat_id(str(payload.get("target_id") or payload.get("chat_id") or ""))
        if parsed is not None:
            return parsed
        server_id = str(payload.get("server_id") or "").strip()
        channel_id = str(payload.get("channel_id") or "").strip()
        if server_id and channel_id:
            return server_id, channel_id
        return "", ""

    async def _to_message_event(self, payload: dict[str, Any]) -> MessageEvent:
        session_type = str(payload.get("session_type") or "p2p")
        sender_id = str(payload.get("sender_id") or "")
        target_id = str(payload.get("target_id") or "")
        chat_type = "dm" if session_type == "p2p" else "group"
        if session_type == "qchat":
            server_id = str(payload.get("server_id") or "")
            channel_id = str(payload.get("channel_id") or "")
            parsed_target = parse_qchat_chat_id(target_id)
            if parsed_target is not None:
                server_id, channel_id = parsed_target
            elif not (server_id and channel_id):
                server_id = ""
                channel_id = ""
            chat_id = build_qchat_chat_id(server_id, channel_id) if server_id and channel_id else target_id or "qchat:unknown"
        else:
            chat_id = f"user:{sender_id}" if session_type == "p2p" else f"team:{target_id}"
        message_id = str(payload.get("message_id") or payload.get("client_message_id") or "")
        message_type = self._to_message_type(str(payload.get("message_type") or "text"))
        media_urls, media_types = await self._load_media_attachments(payload, message_type)
        source = SessionSource(
            platform=Platform("nim"),
            chat_id=chat_id,
            chat_type=chat_type,
            user_id=sender_id,
            user_name=payload.get("sender_name"),
            chat_name=payload.get("conversation_name"),
            message_id=message_id,
        )
        return MessageEvent(
            text=str(payload.get("text") or ""),
            message_type=message_type,
            source=source,
            raw_message=payload,
            message_id=message_id,
            media_urls=media_urls,
            media_types=media_types,
            metadata={
                "session_type": session_type,
                "target_id": target_id,
                "server_id": payload.get("server_id"),
                "channel_id": payload.get("channel_id"),
                "mentioned": bool(payload.get("mentioned")),
                "mention_all": bool(payload.get("mention_all")),
                "topic_refer": payload.get("topic_refer"),
                "thread_reply": payload.get("thread_reply"),
            },
        )

    def _infer_session_type(self, chat_id: str, metadata: dict[str, Any] | None) -> str:
        if metadata and metadata.get("session_type"):
            return str(metadata["session_type"])
        if parse_qchat_chat_id(chat_id) is not None:
            return "qchat"
        if chat_id.startswith("team:"):
            return "team"
        return "p2p"

    def _to_message_type(self, value: str) -> MessageType:
        mapping = {
            "text": MessageType.TEXT,
            "image": MessageType.PHOTO,
            "audio": MessageType.AUDIO,
            "video": MessageType.VIDEO,
            "file": MessageType.DOCUMENT,
        }
        return mapping.get(value, MessageType.TEXT)

    async def _load_media_attachments(
        self,
        payload: dict[str, Any],
        message_type: MessageType,
    ) -> tuple[list[str], list[str]]:
        kind = infer_media_kind(getattr(message_type, "value", str(message_type)))
        if not kind:
            return [], []

        attachment = parse_inbound_attachment(payload)
        if attachment is None:
            return [], []

        try:
            request = Request(
                attachment.url,
                headers={"User-Agent": "hermes-nim-channel/0.2"},
            )
            with urlopen(request, timeout=20) as response:
                data = response.read()
                mime_type = attachment.mime_type or str(response.headers.get_content_type() or "").strip()

            cached = cache_media_bytes(
                data,
                filename=attachment.name,
                mime_type=mime_type,
                default_kind=kind,
            )
        except Exception:
            return [], []
        if cached is None:
            return [], []
        return [cached.path], [cached.media_type]

    async def _send_media_with_optional_caption(
        self,
        *,
        chat_id: str,
        file_path: str,
        media_kind: str,
        caption: str | None,
        reply_to: str | None,
        metadata: dict[str, Any] | None,
    ) -> SendResult:
        session_type = self._infer_session_type(chat_id, metadata)
        if session_type == "qchat":
            return SendResult(success=False, error="qchat media is not supported")
        result = await self._bridge.send_media(
            chat_id=chat_id,
            file_path=str(Path(file_path)),
            media_kind=media_kind,
            session_type=session_type,
        )
        media_result = SendResult(
            success=True,
            message_id=str(result.get("message_id") or result.get("client_message_id") or ""),
            raw_response=result,
        )
        if not caption:
            return media_result

        caption_result = await self.send(
            chat_id=chat_id,
            content=caption,
            reply_to=reply_to,
            metadata=metadata,
        )
        if caption_result.success and not caption_result.message_id:
            caption_result.message_id = media_result.message_id
        return caption_result if caption_result.success else caption_result


def check_requirements() -> bool:
    return shutil.which("node") is not None


def validate_config(config: PlatformConfig) -> bool:
    return load_nim_config(config).configured()


def _env_enablement() -> dict[str, Any] | None:
    nim_credentials = os.getenv("NIM_CREDENTIALS", "").strip()
    app_key = os.getenv("NIM_APP_KEY", "").strip()
    account = os.getenv("NIM_ACCOUNT", "").strip()
    token = os.getenv("NIM_TOKEN", "").strip()
    if not nim_credentials and not (app_key and account and token):
        return None

    extra: dict[str, Any] = {}
    if nim_credentials:
        extra["nim_token"] = nim_credentials
    else:
        extra["app_key"] = app_key
        extra["account"] = account
        extra["token"] = token

    optional_map = {
        "NIM_ALLOWED_USERS": (
            "allowed_users",
            lambda value: [item.strip() for item in value.split(",") if item.strip()],
        ),
        "NIM_ALLOW_ALL_USERS": (
            "allow_all_users",
            lambda value: value.strip().lower() in {"1", "true", "yes", "on"},
        ),
        "NIM_GROUP_POLICY": ("group_policy", lambda value: value.strip()),
        "NIM_GROUP_ALLOWLIST": (
            "group_allowlist",
            lambda value: [item.strip() for item in value.split(",") if item.strip()],
        ),
        "NIM_P2P_POLICY": ("p2p_policy", lambda value: value.strip()),
        "NIM_P2P_ALLOW_FROM": (
            "p2p_allow_from",
            lambda value: [item.strip() for item in value.split(",") if item.strip()],
        ),
        "NIM_QCHAT_POLICY": ("qchat_policy", lambda value: value.strip()),
        "NIM_QCHAT_ALLOW_FROM": (
            "qchat_allow_from",
            lambda value: [item.strip() for item in value.split(",") if item.strip()],
        ),
        "NIM_WEBLBS_URL": ("weblbs_url", lambda value: value.strip()),
        "NIM_LINK_WEB": ("link_web", lambda value: value.strip()),
        "NIM_NOS_UPLOADER": ("nos_uploader", lambda value: value.strip()),
        "NIM_NOS_DOWNLOADER_V2": ("nos_downloader_v2", lambda value: value.strip()),
        "NIM_NOS_SSL": ("nos_ssl", lambda value: value.strip().lower() in {"1", "true", "yes", "on"}),
        "NIM_NOS_ACCELERATE": ("nos_accelerate", lambda value: value.strip()),
        "NIM_NOS_ACCELERATE_HOST": ("nos_accelerate_host", lambda value: value.strip()),
        "NIM_TEXT_CHUNK_LIMIT": ("text_chunk_limit", lambda value: int(value.strip())),
        "NIM_LEGACY_LOGIN": ("legacy_login", lambda value: value.strip().lower() in {"1", "true", "yes", "on"}),
        "NIM_ANTISPAM_ENABLED": (
            "antispam_enabled",
            lambda value: value.strip().lower() in {"1", "true", "yes", "on"},
        ),
        "NIM_BRIDGE_COMMAND": ("bridge_command", lambda value: value.strip()),
    }
    for env_name, (key, parser) in optional_map.items():
        raw = os.getenv(env_name, "").strip()
        if raw:
            extra[key] = parser(raw)

    home_channel = os.getenv("NIM_HOME_CHANNEL", "").strip()
    if home_channel:
        extra["home_channel"] = home_channel

    return extra


def register(ctx) -> None:
    ctx.register_platform(
        name="nim",
        label="NIM",
        adapter_factory=lambda cfg: HermesNimAdapter(cfg),
        check_fn=check_requirements,
        validate_config=validate_config,
        required_env=["NIM_CREDENTIALS"],
        install_hint="npm install --prefix bridge",
        env_enablement_fn=_env_enablement,
        cron_deliver_env_var="NIM_HOME_CHANNEL",
        allowed_users_env="NIM_ALLOWED_USERS",
        allow_all_env="NIM_ALLOW_ALL_USERS",
        max_message_length=4000,
        platform_hint=(
            "You are chatting via NetEase IM (NIM). "
            "Reply to the current conversation unless the user explicitly asks to switch targets."
        ),
    )
