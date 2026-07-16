from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote
from urllib.request import Request, urlopen

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import BasePlatformAdapter, MessageEvent, MessageType, SendResult, cache_media_bytes
from gateway.session import SessionSource

from hermes_nim_channel.config import NimResolvedConfig, load_nim_instances
from hermes_nim_channel.inbound_media import infer_media_kind, parse_inbound_attachment
from hermes_nim_channel.qchat import (
    build_qchat_chat_id,
    is_qchat_allowed,
    is_qchat_target_allowed,
    parse_qchat_chat_id,
)
from hermes_nim_channel.platforms.nim_bridge import NodeBridgeProcess
from hermes_nim_channel.session_titles import schedule_nim_session_title_pin
from hermes_nim_channel.standalone import NimStandaloneRelay, standalone_send_via_gateway
from hermes_nim_channel.targets import (
    append_topic_to_conversation_name,
    build_topic_chat_id,
    derive_stream_id,
    qchat_context_text,
    qchat_media_fallback_text,
    resolve_topic_id,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class NimInstanceRuntime:
    account_id: str
    config: NimResolvedConfig
    bridge: NodeBridgeProcess
    connected: bool = False


class HermesNimAdapter(BasePlatformAdapter):
    def __init__(self, config: PlatformConfig) -> None:
        super().__init__(config=config, platform=Platform("nim"))
        self.instances = load_nim_instances(config, _hermes_env())
        self.resolved = self.instances[0] if self.instances else NimResolvedConfig(False, None)
        self._runtimes: dict[str, NimInstanceRuntime] = {}
        self._chat_names: dict[str, str | None] = {}
        self._standalone_relay: NimStandaloneRelay | None = None

    async def connect(self, *args: Any, **kwargs: Any) -> bool:
        configured = [instance for instance in self.instances if instance.configured()]
        if not configured:
            self._set_fatal_error(
                "config_missing",
                "NIM credentials are not configured",
                retryable=False,
            )
            return False
        for instance in configured:
            account_id = instance.resolved_account_id()
            runtime = NimInstanceRuntime(
                account_id=account_id,
                config=instance,
                bridge=NodeBridgeProcess(instance.bridge_command),
            )
            self._runtimes[account_id] = runtime
            try:
                await runtime.bridge.start(
                    instance,
                    event_handler=lambda envelope, runtime_account_id=account_id: self._on_bridge_event(
                        envelope,
                        runtime_account_id,
                    ),
                )
                runtime.connected = True
            except Exception:
                logger.exception("Failed to connect NIM instance: account_id=%s", account_id)
        if not any(runtime.connected for runtime in self._runtimes.values()):
            self._set_fatal_error(
                "connect_failed",
                "No NIM instances connected",
                retryable=True,
            )
            return False
        self._mark_connected()
        relay = NimStandaloneRelay(self)
        try:
            await relay.start()
            self._standalone_relay = relay
        except Exception:
            logger.exception("Failed to start NIM standalone-send relay")
        return True

    async def disconnect(self) -> None:
        relay = self._standalone_relay
        self._standalone_relay = None
        if relay is not None:
            try:
                await relay.stop()
            except Exception:
                logger.exception("Failed to stop NIM standalone-send relay")
        for runtime in list(self._runtimes.values()):
            try:
                await runtime.bridge.stop()
            finally:
                runtime.connected = False
        self._mark_disconnected()

    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SendResult:
        runtime, resolved, routed_chat_id = self._resolve_runtime_for_send(chat_id, metadata)
        if runtime is None or resolved is None:
            return SendResult(success=False, error="no NIM instance is connected for target")
        session_type = self._infer_session_type(routed_chat_id, metadata)
        topic_id = resolve_topic_id(routed_chat_id, metadata)
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
                text=str(content or ""),
                session_type=session_type,
                reply_to=reply_to or (metadata or {}).get("reply_to"),
            )
        else:
            meta = metadata or {}
            if meta.get("edit_message_id") or meta.get("edit"):
                result = await runtime.bridge.edit_message(
                    chat_id=routed_chat_id,
                    text=str(content or ""),
                    session_type=session_type,
                    message_id=meta.get("edit_message_id") or meta.get("message_id"),
                )
            elif meta.get("stream"):
                stream = meta.get("stream") if isinstance(meta.get("stream"), dict) else {}
                resolved_reply_to = reply_to or meta.get("reply_to")
                result = await runtime.bridge.send_stream_text(
                    chat_id=routed_chat_id,
                    text=str(content or ""),
                    session_type=session_type,
                    chunk_index=self._metadata_int(stream.get("chunk_index", stream.get("index", 0)), 0),
                    is_complete=self._metadata_bool(stream.get("is_complete", stream.get("finish", True)), True),
                    reply_to=resolved_reply_to,
                    stream_id=derive_stream_id(
                        routed_chat_id,
                        resolved_reply_to,
                        stream.get("stream_id") or stream.get("id") or meta.get("stream_id"),
                    ),
                    topic_id=topic_id,
                )
            else:
                result = await runtime.bridge.send_text(
                    chat_id=routed_chat_id,
                    text=str(content or ""),
                    session_type=session_type,
                    reply_to=reply_to or meta.get("reply_to"),
                    topic_id=topic_id,
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
        parsed = self._parse_account_prefixed_chat_id(chat_id)
        if parsed is not None:
            _account_id, chat_id = parsed
        if parse_qchat_chat_id(chat_id) is not None:
            return {
                "name": self._chat_names.get(chat_id) or chat_id,
                "type": "group",
            }
        return {
            "name": self._chat_names.get(chat_id) or chat_id,
            "type": "group" if chat_id.startswith("team:") else "dm",
        }

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
        self._chat_names[event.source.chat_id] = event.source.chat_name
        await self.handle_message(event)
        schedule_nim_session_title_pin(event.source)

    def _handle_connection_event(self, payload: dict[str, Any], runtime: NimInstanceRuntime) -> None:
        status = str(payload.get("status") or "")
        if status == "connected":
            runtime.connected = True
            self._mark_connected()
        elif status in {"logout", "kickout", "disconnected"}:
            runtime.connected = False
            if not any(item.connected for item in self._runtimes.values()):
                self._mark_disconnected()

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
            topic_id = resolve_topic_id("", payload)
            chat_id = (
                build_topic_chat_id(sender_id, topic_id)
                if session_type == "p2p" and topic_id is not None
                else f"user:{sender_id}" if session_type == "p2p" else f"team:{target_id}"
            )
        if self._multi_instance_enabled() and account_id:
            chat_id = self._with_account_prefix(account_id, chat_id)
        message_id = str(payload.get("message_id") or payload.get("client_message_id") or "")
        message_type = self._to_message_type(str(payload.get("message_type") or "text"))
        media_urls, media_types = await self._load_media_attachments(payload, message_type)
        conversation_name = append_topic_to_conversation_name(
            payload.get("conversation_name"),
            payload.get("topic_name"),
        )
        source = SessionSource(
            platform=Platform("nim"),
            chat_id=chat_id,
            chat_type=chat_type,
            user_id=sender_id,
            user_name=payload.get("sender_name"),
            chat_name=conversation_name,
            message_id=message_id,
        )
        return MessageEvent(
            text=qchat_context_text(
                payload.get("text"),
                conversation_name,
                payload.get("channel_topic"),
            ) if session_type == "qchat" else str(payload.get("text") or ""),
            message_type=message_type,
            source=source,
            raw_message=payload,
            message_id=message_id,
            media_urls=media_urls,
            media_types=media_types,
            reply_to_message_id=self._optional_str(payload.get("reply_to_message_id")),
            reply_to_text=self._optional_str(payload.get("reply_to_text")),
            reply_to_author_id=self._optional_str(payload.get("reply_to_author_id")),
            reply_to_author_name=self._optional_str(payload.get("reply_to_author_name")),
            reply_to_is_own_message=bool(payload.get("reply_to_is_own_message")),
            metadata={
                "session_type": session_type,
                "target_id": target_id,
                "server_id": payload.get("server_id"),
                "channel_id": payload.get("channel_id"),
                "mentioned": bool(payload.get("mentioned")),
                "mention_all": bool(payload.get("mention_all")),
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
        mapping = {
            "text": MessageType.TEXT,
            "image": MessageType.PHOTO,
            "audio": MessageType.AUDIO,
            "video": MessageType.VIDEO,
            "file": MessageType.DOCUMENT,
        }
        return mapping.get(value, MessageType.TEXT)

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
        runtime, _resolved, routed_chat_id = self._resolve_runtime_for_send(chat_id, metadata)
        if runtime is None:
            return SendResult(success=False, error="no NIM instance is connected for target")
        session_type = self._infer_session_type(routed_chat_id, metadata)
        if session_type == "qchat":
            fallback_text = qchat_media_fallback_text(caption, file_path)
            return await self.send(
                chat_id=chat_id,
                content=fallback_text,
                reply_to=reply_to,
                metadata=metadata,
            )
        result = await runtime.bridge.send_media(
            chat_id=routed_chat_id,
            file_path=str(Path(file_path)),
            media_kind=media_kind,
            session_type=session_type,
            reply_to=reply_to or (metadata or {}).get("reply_to"),
            topic_id=resolve_topic_id(routed_chat_id, metadata),
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
    return any(instance.configured() for instance in load_nim_instances(config, _hermes_env()))


def _is_connected(config: PlatformConfig) -> bool:
    return any(instance.configured() for instance in load_nim_instances(config, _hermes_env()))


def _hermes_env() -> dict[str, str]:
    env = dict(os.environ)
    try:
        from hermes_cli.gateway import get_env_value
    except Exception:
        return env
    for key in (
        "NIM_CREDENTIALS",
        "NIM_INSTANCES",
        "NIM_APP_KEY",
        "NIM_ACCOUNT",
        "NIM_TOKEN",
        "NIM_ALLOWED_USERS",
        "NIM_ALLOW_ALL_USERS",
        "NIM_GROUP_POLICY",
        "NIM_GROUP_ALLOWLIST",
        "NIM_P2P_POLICY",
        "NIM_P2P_ALLOW_FROM",
        "NIM_QCHAT_POLICY",
        "NIM_QCHAT_ALLOW_FROM",
        "NIM_QCHAT_ALLOWLIST",
        "NIM_WEBLBS_URL",
        "NIM_LINK_WEB",
        "NIM_NOS_UPLOADER",
        "NIM_NOS_DOWNLOADER_V2",
        "NIM_NOS_SSL",
        "NIM_NOS_ACCELERATE",
        "NIM_NOS_ACCELERATE_HOST",
        "NIM_MEDIA_MAX_MB",
        "NIM_TEXT_CHUNK_LIMIT",
        "NIM_INBOUND_DEBOUNCE_MS",
        "NIM_QUICK_COMMENT_ENABLED",
        "NIM_QUICK_COMMENT_INDEX",
        "NIM_QUICK_COMMENT_TTL_MS",
        "NIM_LEGACY_LOGIN",
        "NIM_ANTISPAM_ENABLED",
        "NIM_DEBUG",
        "NIM_HOME_CHANNEL",
        "NIM_BRIDGE_COMMAND",
    ):
        value = get_env_value(key)
        if value not in (None, ""):
            env[key] = str(value)
    return env


def _env_enablement() -> dict[str, Any] | None:
    env = _hermes_env()
    nim_credentials = env.get("NIM_CREDENTIALS", "").strip()
    app_key = env.get("NIM_APP_KEY", "").strip()
    account = env.get("NIM_ACCOUNT", "").strip()
    token = env.get("NIM_TOKEN", "").strip()
    if not nim_credentials and not (app_key and account and token):
        instances = env.get("NIM_INSTANCES", "").strip()
        if not instances:
            return None
        return {"instances": json.loads(instances)}

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
        raw = env.get(env_name, "").strip()
        if raw:
            extra[key] = parser(raw)

    home_channel = env.get("NIM_HOME_CHANNEL", "").strip()
    if home_channel:
        extra["home_channel"] = {
            "chat_id": home_channel,
            "name": env.get("NIM_HOME_CHANNEL_NAME", "").strip() or "NIM Home",
        }

    return extra


def register(ctx) -> None:
    ctx.register_platform(
        name="nim",
        label="NIM",
        adapter_factory=lambda cfg: HermesNimAdapter(cfg),
        check_fn=check_requirements,
        is_connected=_is_connected,
        validate_config=validate_config,
        required_env=["NIM_CREDENTIALS"],
        install_hint="npm install --prefix bridge",
        env_enablement_fn=_env_enablement,
        cron_deliver_env_var="NIM_HOME_CHANNEL",
        allowed_users_env="NIM_ALLOWED_USERS",
        allow_all_env="NIM_ALLOW_ALL_USERS",
        standalone_sender_fn=standalone_send_via_gateway,
        max_message_length=4000,
        platform_hint=(
            "You are chatting via NetEase IM (NIM). "
            "Reply to the current conversation unless the user explicitly asks to switch targets."
        ),
    )
