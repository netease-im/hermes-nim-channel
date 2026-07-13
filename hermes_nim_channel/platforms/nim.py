from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from hermes_nim_channel.config import NimResolvedConfig, Platform, PlatformConfig, load_nim_config
from hermes_nim_channel.inbound_media import (
    NimInboundAttachment,
    cache_attachment_bytes_local,
    fetch_attachment_bytes,
    infer_media_kind,
    parse_inbound_attachment,
)
from hermes_nim_channel.qchat import (
    build_qchat_chat_id,
    is_qchat_allowed,
    is_qchat_target_allowed,
    parse_qchat_chat_id,
)
from hermes_nim_channel.platforms.base import (
    BasePlatformAdapter,
    ChatType,
    MessageEvent,
    MessageSource,
    MessageType,
    SendResult,
)
from hermes_nim_channel.platforms.nim_bridge import NodeBridgeProcess

AttachmentLoader = Callable[[dict[str, Any], str], tuple[list[str], list[str]] | Awaitable[tuple[list[str], list[str]]]]


@dataclass(slots=True)
class ChatInfo:
    chat_id: str
    chat_type: str
    chat_name: str | None = None


class NimAdapter(BasePlatformAdapter):
    def __init__(
        self,
        config: PlatformConfig,
        *,
        bridge: NodeBridgeProcess | Any | None = None,
        attachment_loader: AttachmentLoader | None = None,
    ) -> None:
        super().__init__(config=config, platform=Platform.NIM)
        self.resolved: NimResolvedConfig = load_nim_config(config)
        self._bridge = bridge or NodeBridgeProcess(self.resolved.bridge_command)
        self._chat_cache: dict[str, ChatInfo] = {}
        self._attachment_loader = attachment_loader

    async def connect(self) -> bool:
        if not self.resolved.configured():
            self.connected = False
            return False
        await self._bridge.start(self.resolved, event_handler=self._on_bridge_event)
        self.connected = True
        return True

    async def disconnect(self) -> None:
        await self._bridge.stop()
        self.connected = False

    async def health(self) -> dict[str, Any]:
        return await self._bridge.health()

    async def send(
        self,
        chat_id: str,
        text: str,
        *,
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
                text=text,
                session_type=session_type,
                reply_to=(metadata or {}).get("reply_to"),
            )
        else:
            result = await self._bridge.send_text(
                chat_id=chat_id,
                text=text,
                session_type=session_type,
                reply_to=(metadata or {}).get("reply_to"),
            )
        return SendResult(
            success=True,
            message_id=str(result.get("message_id") or result.get("client_message_id") or ""),
        )

    async def send_image_file(
        self,
        chat_id: str,
        image_path: str,
        caption: str | None = None,
        reply_to: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
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
        **kwargs: Any,
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
        **kwargs: Any,
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
        **kwargs: Any,
    ) -> SendResult:
        return await self._send_media_with_optional_caption(
            chat_id=chat_id,
            file_path=video_path,
            media_kind="video",
            caption=caption,
            reply_to=reply_to,
            metadata=metadata,
        )

    def get_chat_info(self, chat_id: str) -> ChatInfo:
        cached = self._chat_cache.get(chat_id)
        if cached is not None:
            return cached
        if parse_qchat_chat_id(chat_id) is not None:
            return ChatInfo(chat_id=chat_id, chat_type=ChatType.GROUP.value)
        if chat_id.startswith("team:"):
            return ChatInfo(chat_id=chat_id, chat_type=ChatType.GROUP.value)
        return ChatInfo(chat_id=chat_id, chat_type=ChatType.DIRECT.value)

    async def _on_bridge_event(self, envelope: dict[str, Any]) -> None:
        if envelope.get("event") == "connection":
            self._handle_connection_event(dict(envelope.get("payload") or {}))
            return
        if envelope.get("event") != "message":
            return
        payload = dict(envelope.get("payload") or {})
        if self._should_ignore(payload):
            return
        event = await self._to_message_event(payload)
        self._chat_cache[event.source.chat_id] = ChatInfo(
            chat_id=event.source.chat_id,
            chat_type=event.source.chat_type,
            chat_name=event.source.chat_name,
        )
        await self.handle_message(event)

    def _handle_connection_event(self, payload: dict[str, Any]) -> None:
        status = str(payload.get("status") or "")
        if status == "connected":
            self.connected = True
        elif status in {"logout", "kickout", "disconnected"}:
            self.connected = False

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
        chat_type = ChatType.DIRECT.value if session_type == "p2p" else ChatType.GROUP.value
        if session_type == "qchat":
            server_id = str(payload.get("server_id") or "").strip()
            channel_id = str(payload.get("channel_id") or "").strip()
            parsed_target = parse_qchat_chat_id(target_id)
            if parsed_target is not None:
                server_id, channel_id = parsed_target
            elif not (server_id and channel_id):
                server_id = ""
                channel_id = ""
            chat_id = build_qchat_chat_id(server_id, channel_id) if server_id and channel_id else target_id or "qchat:unknown"
        else:
            chat_id = f"user:{sender_id}" if session_type == "p2p" else f"team:{target_id}"
        source = MessageSource(
            platform=self.platform.value,
            chat_id=chat_id,
            chat_type=chat_type,
            user_id=sender_id,
            user_name=payload.get("sender_name"),
            chat_name=payload.get("conversation_name"),
        )
        message_type = self._to_message_type(str(payload.get("message_type") or "text"))
        media_urls, media_types = await self._load_media_attachments(payload, message_type)
        return MessageEvent(
            message_id=str(payload.get("message_id") or payload.get("client_message_id") or ""),
            message_type=message_type.value,
            text=str(payload.get("text") or ""),
            source=source,
            raw=payload,
            media_urls=media_urls,
            media_types=media_types,
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
        try:
            return MessageType(value)
        except ValueError:
            return MessageType.UNKNOWN

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
            reply_to=reply_to or (metadata or {}).get("reply_to"),
        )
        media_result = SendResult(
            success=True,
            message_id=str(result.get("message_id") or result.get("client_message_id") or ""),
        )
        if not caption:
            return media_result

        caption_result = await self.send(
            chat_id=chat_id,
            text=caption,
            metadata=metadata,
        )
        if caption_result.success and not caption_result.message_id:
            caption_result.message_id = media_result.message_id
        return caption_result

    async def _load_media_attachments(
        self,
        payload: dict[str, Any],
        message_type: MessageType,
    ) -> tuple[list[str], list[str]]:
        kind = infer_media_kind(message_type.value)
        if not kind:
            return [], []

        if self._attachment_loader is not None:
            try:
                result = self._attachment_loader(payload, kind)
                if isinstance(result, tuple):
                    return result
                return await result
            except Exception:
                return [], []

        attachment = parse_inbound_attachment(payload)
        if attachment is None:
            return [], []

        try:
            data, mime_type = fetch_attachment_bytes(attachment)
            attachment = NimInboundAttachment(
                url=attachment.url,
                name=attachment.name,
                size=attachment.size,
                mime_type=mime_type,
                width=attachment.width,
                height=attachment.height,
                duration=attachment.duration,
            )
            cached = cache_attachment_bytes_local(
                data,
                attachment=attachment,
                kind=kind,
            )
            return [cached.path], [cached.media_type]
        except Exception:
            return [], []


PlatformAdapter = NimAdapter
