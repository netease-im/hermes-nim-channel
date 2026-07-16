from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import quote, unquote

from hermes_nim_channel.config import NimResolvedConfig, Platform, PlatformConfig, load_nim_instances
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
from hermes_nim_channel.session_titles import schedule_nim_session_title_pin

logger = logging.getLogger(__name__)

AttachmentLoader = Callable[[dict[str, Any], str], tuple[list[str], list[str]] | Awaitable[tuple[list[str], list[str]]]]
BridgeFactory = Callable[[NimResolvedConfig], NodeBridgeProcess | Any]


@dataclass(slots=True)
class ChatInfo:
    chat_id: str
    chat_type: str
    chat_name: str | None = None


@dataclass(slots=True)
class NimInstanceRuntime:
    account_id: str
    config: NimResolvedConfig
    bridge: NodeBridgeProcess | Any
    connected: bool = False


class NimAdapter(BasePlatformAdapter):
    def __init__(
        self,
        config: PlatformConfig,
        *,
        bridge: NodeBridgeProcess | Any | None = None,
        bridge_factory: BridgeFactory | None = None,
        attachment_loader: AttachmentLoader | None = None,
    ) -> None:
        super().__init__(config=config, platform=Platform.NIM)
        self.instances: list[NimResolvedConfig] = load_nim_instances(config)
        self.resolved: NimResolvedConfig = self.instances[0] if self.instances else NimResolvedConfig(False, None)
        self._bridge_factory = bridge_factory
        self._single_bridge_override = bridge
        self._runtimes: dict[str, NimInstanceRuntime] = {}
        self._chat_cache: dict[str, ChatInfo] = {}
        self._attachment_loader = attachment_loader

    async def connect(self, *args: Any, **kwargs: Any) -> bool:
        configured = [instance for instance in self.instances if instance.configured()]
        if not configured:
            self.connected = False
            return False
        for index, instance in enumerate(configured):
            account_id = instance.resolved_account_id()
            bridge = self._make_bridge(instance, use_single_override=index == 0)
            runtime = NimInstanceRuntime(account_id=account_id, config=instance, bridge=bridge)
            self._runtimes[account_id] = runtime
            try:
                await bridge.start(
                    instance,
                    event_handler=lambda envelope, runtime_account_id=account_id: self._on_bridge_event(
                        envelope,
                        runtime_account_id,
                    ),
                )
                runtime.connected = True
            except Exception:
                logger.exception("Failed to connect NIM instance: account_id=%s", account_id)
                runtime.connected = False
        self.connected = any(runtime.connected for runtime in self._runtimes.values())
        return self.connected

    async def disconnect(self) -> None:
        for runtime in list(self._runtimes.values()):
            try:
                await runtime.bridge.stop()
            finally:
                runtime.connected = False
        self.connected = False

    async def health(self) -> dict[str, Any]:
        if len(self._runtimes) == 1:
            runtime = next(iter(self._runtimes.values()))
            return await runtime.bridge.health()
        results: dict[str, Any] = {}
        for account_id, runtime in self._runtimes.items():
            try:
                results[account_id] = await runtime.bridge.health()
            except Exception as exc:
                results[account_id] = {"status": "error", "error": str(exc)}
        return {"instances": results}

    async def send(
        self,
        chat_id: str,
        text: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> SendResult:
        runtime, resolved, routed_chat_id = self._resolve_runtime_for_send(chat_id, metadata)
        if runtime is None or resolved is None:
            return SendResult(success=False, error="no NIM instance is connected for target")
        session_type = self._infer_session_type(routed_chat_id, metadata)
        if session_type == "qchat":
            target = parse_qchat_chat_id(routed_chat_id)
            if target is None:
                return SendResult(success=False, error=f"invalid QChat target: {chat_id}")
            server_id, channel_id = target
            if not is_qchat_target_allowed(
                policy=resolved.qchat_policy,
                allow_from=resolved.qchat_allow_from,
                server_id=server_id,
                channel_id=channel_id,
            ):
                return SendResult(success=False, error="qchat send blocked by policy")
            result = await runtime.bridge.send_qchat_message(
                chat_id=routed_chat_id,
                text=text,
                session_type=session_type,
                reply_to=(metadata or {}).get("reply_to"),
            )
        else:
            meta = metadata or {}
            if meta.get("edit_message_id") or meta.get("edit"):
                result = await runtime.bridge.edit_message(
                    chat_id=routed_chat_id,
                    text=text,
                    session_type=session_type,
                    message_id=meta.get("edit_message_id") or meta.get("message_id"),
                )
            elif meta.get("stream"):
                stream = meta.get("stream") if isinstance(meta.get("stream"), dict) else {}
                result = await runtime.bridge.send_stream_text(
                    chat_id=routed_chat_id,
                    text=text,
                    session_type=session_type,
                    chunk_index=self._metadata_int(stream.get("chunk_index", stream.get("index", 0)), 0),
                    is_complete=self._metadata_bool(stream.get("is_complete", stream.get("finish", True)), True),
                    reply_to=meta.get("reply_to"),
                )
            else:
                result = await runtime.bridge.send_text(
                    chat_id=routed_chat_id,
                    text=text,
                    session_type=session_type,
                    reply_to=meta.get("reply_to"),
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

    def _make_bridge(self, instance: NimResolvedConfig, *, use_single_override: bool) -> NodeBridgeProcess | Any:
        if use_single_override and self._single_bridge_override is not None:
            return self._single_bridge_override
        if self._bridge_factory is not None:
            return self._bridge_factory(instance)
        return NodeBridgeProcess(instance.bridge_command)

    async def _on_bridge_event(self, envelope: dict[str, Any], account_id: str | None = None) -> None:
        runtime = self._runtime_for_account(account_id, require_connected=False)
        if runtime is None:
            return
        if envelope.get("event") == "connection":
            self._handle_connection_event(dict(envelope.get("payload") or {}), runtime)
            return
        if envelope.get("event") != "message":
            return
        payload = dict(envelope.get("payload") or {})
        payload["nim_account_id"] = runtime.account_id
        ignore_reason = self._ignore_reason(payload, runtime.config)
        if ignore_reason:
            logger.info(
                "Ignoring NIM inbound message: reason=%s session_type=%s sender=%s target=%s message_id=%s",
                ignore_reason,
                payload.get("session_type"),
                payload.get("sender_id"),
                payload.get("target_id"),
                payload.get("message_id") or payload.get("client_message_id"),
            )
            return
        event = await self._to_message_event(payload, runtime.account_id)
        self._chat_cache[event.source.chat_id] = ChatInfo(
            chat_id=event.source.chat_id,
            chat_type=event.source.chat_type,
            chat_name=event.source.chat_name,
        )
        await self.handle_message(event)
        schedule_nim_session_title_pin(event.source)

    def _handle_connection_event(self, payload: dict[str, Any], runtime: NimInstanceRuntime) -> None:
        status = str(payload.get("status") or "")
        if status == "connected":
            runtime.connected = True
        elif status in {"logout", "kickout", "disconnected"}:
            runtime.connected = False
        self.connected = any(item.connected for item in self._runtimes.values())

    def _should_ignore(self, payload: dict[str, Any]) -> bool:
        return self._ignore_reason(payload, self.resolved) is not None

    def _ignore_reason(self, payload: dict[str, Any], resolved: NimResolvedConfig) -> str | None:
        if "message_source" in payload and payload.get("message_source") != 1:
            return "non_online_message"
        if payload.get("from_self"):
            return "from_self"
        session_type = str(payload.get("session_type") or "p2p")
        sender_id = str(payload.get("sender_id") or "")
        if session_type == "p2p":
            return None if self._is_allowed_direct_sender(sender_id, resolved) else "p2p_not_allowed"
        if session_type in {"team", "superTeam"}:
            if not self._is_allowed_group(str(payload.get("target_id") or ""), resolved):
                return "group_not_allowed"
            return None if self._is_mentioned(payload, resolved) else "group_not_mentioned"
        if session_type == "qchat":
            if not self._is_mentioned(payload, resolved):
                return "qchat_not_mentioned"
            server_id, channel_id = self._resolve_qchat_target(payload)
            if not server_id or not channel_id:
                return "qchat_target_missing"
            allowed = is_qchat_allowed(
                policy=resolved.qchat_policy,
                allow_from=resolved.qchat_allow_from,
                server_id=server_id,
                channel_id=channel_id,
                sender_accid=sender_id,
            )
            return None if allowed else "qchat_not_allowed"
        return "unsupported_session_type"

    def _is_allowed_direct_sender(self, sender_id: str, resolved: NimResolvedConfig) -> bool:
        if resolved.p2p_policy == "disabled":
            return False
        if resolved.p2p_policy == "open":
            return True
        if resolved.p2p_policy == "allowlist":
            return sender_id in resolved.p2p_allow_from
        if resolved.allow_all_users:
            return True
        if not resolved.allowed_users:
            return True
        return sender_id in resolved.allowed_users

    def _is_allowed_group(self, target_id: str, resolved: NimResolvedConfig) -> bool:
        policy = resolved.group_policy
        if policy == "disabled":
            return False
        if policy == "open":
            return True
        return target_id in resolved.group_allowlist

    def _is_mentioned(self, payload: dict[str, Any], resolved: NimResolvedConfig) -> bool:
        if payload.get("mentioned") or payload.get("mention_all"):
            return True
        force_push_ids = {str(item) for item in payload.get("force_push_account_ids") or []}
        account = resolved.credentials.account if resolved.credentials else ""
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

    async def _to_message_event(self, payload: dict[str, Any], account_id: str | None = None) -> MessageEvent:
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
        if self._multi_instance_enabled() and account_id:
            chat_id = self._with_account_prefix(account_id, chat_id)
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
            raw={
                **payload,
                "metadata": {
                    "topic_refer": payload.get("topic_refer"),
                    "topic_info": payload.get("topic_info"),
                    "topic_name": payload.get("topic_name"),
                    "thread_reply": payload.get("thread_reply"),
                    "reply_to_message_id": payload.get("reply_to_message_id"),
                    "reply_to_text": payload.get("reply_to_text"),
                    "reply_to_author_id": payload.get("reply_to_author_id"),
                    "reply_to_author_name": payload.get("reply_to_author_name"),
                    "reply_to_is_own_message": payload.get("reply_to_is_own_message"),
                    "batch_id": payload.get("batch_id"),
                    "batch_key": payload.get("batch_key"),
                    "batch_index": payload.get("batch_index"),
                    "batch_size": payload.get("batch_size"),
                    "quick_comment": payload.get("quick_comment"),
                    "channel_topic": payload.get("channel_topic"),
                    "channel_info": payload.get("channel_info"),
                    "nim_account_id": payload.get("nim_account_id") or account_id,
                },
            },
            media_urls=media_urls,
            media_types=media_types,
            reply_to_message_id=self._optional_str(payload.get("reply_to_message_id")),
            reply_to_text=self._optional_str(payload.get("reply_to_text")),
            reply_to_author_id=self._optional_str(payload.get("reply_to_author_id")),
            reply_to_author_name=self._optional_str(payload.get("reply_to_author_name")),
            reply_to_is_own_message=bool(payload.get("reply_to_is_own_message")),
        )

    @staticmethod
    def _optional_str(value: Any) -> str | None:
        if value in (None, ""):
            return None
        return str(value)

    def _infer_session_type(self, chat_id: str, metadata: dict[str, Any] | None) -> str:
        if metadata and metadata.get("session_type"):
            return str(metadata["session_type"])
        if parse_qchat_chat_id(chat_id) is not None:
            return "qchat"
        if chat_id.startswith("team:"):
            return "team"
        return "p2p"

    def _runtime_for_account(self, account_id: str | None, *, require_connected: bool = True) -> NimInstanceRuntime | None:
        if account_id and account_id in self._runtimes:
            runtime = self._runtimes[account_id]
            return runtime if runtime.connected or not require_connected else None
        candidates = [runtime for runtime in self._runtimes.values() if runtime.connected or not require_connected]
        if len(candidates) == 1:
            return candidates[0]
        return None

    def _multi_instance_enabled(self) -> bool:
        return len([instance for instance in self.instances if instance.configured()]) > 1

    def _resolve_runtime_for_send(
        self,
        chat_id: str,
        metadata: dict[str, Any] | None,
    ) -> tuple[NimInstanceRuntime | None, NimResolvedConfig | None, str]:
        account_id = None
        routed_chat_id = chat_id
        if metadata:
            account_id = self._optional_str(
                metadata.get("nim_account_id")
                or metadata.get("account_id")
                or metadata.get("accountId")
            )
        parsed = self._parse_account_prefixed_chat_id(chat_id)
        if parsed is not None:
            account_id, routed_chat_id = parsed
        runtime = self._runtime_for_account(account_id)
        if runtime is None:
            return None, None, routed_chat_id
        return runtime, runtime.config, routed_chat_id

    @staticmethod
    def _with_account_prefix(account_id: str, chat_id: str) -> str:
        return f"acct:{quote(account_id, safe='')}:{chat_id}"

    @staticmethod
    def _parse_account_prefixed_chat_id(chat_id: str) -> tuple[str, str] | None:
        if not chat_id.startswith("acct:"):
            return None
        parts = chat_id.split(":", 2)
        if len(parts) != 3 or not parts[1] or not parts[2]:
            return None
        return unquote(parts[1]), parts[2]

    def _to_message_type(self, value: str) -> MessageType:
        try:
            return MessageType(value)
        except ValueError:
            return MessageType.UNKNOWN

    @staticmethod
    def _metadata_bool(value: Any, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _metadata_int(value: Any, default: int) -> int:
        if value in (None, ""):
            return default
        try:
            return int(float(str(value).strip()))
        except (TypeError, ValueError):
            return default

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
        runtime, _resolved, routed_chat_id = self._resolve_runtime_for_send(chat_id, metadata)
        if runtime is None:
            return SendResult(success=False, error="no NIM instance is connected for target")
        session_type = self._infer_session_type(routed_chat_id, metadata)
        if session_type == "qchat":
            return SendResult(success=False, error="qchat media is not supported")
        result = await runtime.bridge.send_media(
            chat_id=routed_chat_id,
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
