from __future__ import annotations

import asyncio
import sys
import time
import unittest

from hermes_nim_channel.config import PlatformConfig
from hermes_nim_channel.inbound_media import parse_inbound_attachment
from hermes_nim_channel.platforms.nim import NimAdapter
from hermes_nim_channel.platforms.nim_bridge import BridgeError, NodeBridgeProcess


class FakeBridge:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.config = None
        self.sent: list[dict[str, str]] = []
        self.stream_sent: list[dict[str, object]] = []
        self.edits: list[dict[str, object]] = []
        self.qchat_sent: list[dict[str, str]] = []
        self.media_sent: list[dict[str, str]] = []
        self.event_handler = None

    async def start(self, config, *, event_handler=None) -> None:
        self.started = True
        self.config = config
        self.event_handler = event_handler

    async def stop(self) -> None:
        self.stopped = True

    async def health(self) -> dict[str, str]:
        return {"status": "ok"}

    async def send_text(
        self,
        *,
        chat_id: str,
        text: str,
        session_type: str,
        reply_to=None,
        topic_id=None,
    ) -> dict[str, str]:
        self.sent.append(
            {
                "chat_id": chat_id,
                "text": text,
                "session_type": session_type,
                "reply_to": reply_to,
                "topic_id": topic_id,
            }
        )
        return {"message_id": "msg-1"}

    async def send_qchat_message(
        self,
        *,
        chat_id: str,
        text: str,
        session_type: str,
        reply_to=None,
        topic_id=None,
    ) -> dict[str, str]:
        self.qchat_sent.append(
            {
                "chat_id": chat_id,
                "text": text,
                "session_type": session_type,
                "reply_to": reply_to,
            }
        )
        return {"message_id": "qchat-1"}

    async def send_media(
        self,
        *,
        chat_id: str,
        file_path: str,
        media_kind: str,
        session_type: str,
        reply_to=None,
        topic_id=None,
    ) -> dict[str, str]:
        self.media_sent.append(
            {
                "chat_id": chat_id,
                "file_path": file_path,
                "media_kind": media_kind,
                "session_type": session_type,
                "reply_to": reply_to,
                "topic_id": topic_id,
            }
        )
        return {"message_id": "media-1"}

    async def send_stream_text(
        self,
        *,
        chat_id: str,
        text: str,
        session_type: str,
        chunk_index: int = 0,
        is_complete: bool = True,
        reply_to=None,
        stream_id=None,
        topic_id=None,
    ) -> dict[str, str]:
        self.stream_sent.append(
            {
                "chat_id": chat_id,
                "text": text,
                "session_type": session_type,
                "chunk_index": chunk_index,
                "is_complete": is_complete,
                "reply_to": reply_to,
                "stream_id": stream_id,
                "topic_id": topic_id,
            }
        )
        return {"message_id": "stream-1"}

    async def edit_message(
        self,
        *,
        chat_id: str,
        text: str,
        session_type: str,
        message_id=None,
    ) -> dict[str, str]:
        self.edits.append(
            {
                "chat_id": chat_id,
                "text": text,
                "session_type": session_type,
                "message_id": message_id,
            }
        )
        return {"message_id": "edit-1"}


class NimAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_connect_requires_credentials(self) -> None:
        adapter = NimAdapter(PlatformConfig(), bridge=FakeBridge())
        self.assertFalse(await adapter.connect())

    async def test_direct_message_allowlist(self) -> None:
        bridge = FakeBridge()
        adapter = NimAdapter(
            PlatformConfig(
                extra={
                    "nim_token": "app|bot|secret",
                    "allowed_users": ["allowed-user"],
                }
            ),
            bridge=bridge,
        )
        accepted = []
        adapter.set_message_handler(lambda event: accepted.append(event))
        await adapter.connect()
        assert bridge.event_handler is not None

        await bridge.event_handler(
            {
                "type": "event",
                "event": "message",
                "payload": {
                    "session_type": "p2p",
                    "sender_id": "blocked-user",
                    "target_id": "bot",
                    "text": "hello",
                    "message_id": "m-1",
                    "message_type": "text",
                },
            }
        )
        await bridge.event_handler(
            {
                "type": "event",
                "event": "message",
                "payload": {
                    "session_type": "p2p",
                    "sender_id": "allowed-user",
                    "target_id": "bot",
                    "text": "hello",
                    "message_id": "m-2",
                    "message_type": "text",
                },
            }
        )

        self.assertEqual(1, len(accepted))
        self.assertEqual("allowed-user", accepted[0].source.user_id)

    async def test_multi_instance_routes_inbound_and_outbound_by_account_prefix(self) -> None:
        bridges = [FakeBridge(), FakeBridge()]

        def bridge_factory(config):
            return bridges[0] if config.credentials.account == "bot-a" else bridges[1]

        adapter = NimAdapter(
            PlatformConfig(
                extra={
                    "instances": [
                        {
                            "enabled": True,
                            "nimToken": "app|bot-a|secret-a",
                            "p2p": {"policy": "allowlist", "allowFrom": ["alice"]},
                        },
                        {
                            "enabled": True,
                            "nimToken": "app|bot-b|secret-b",
                            "p2p": {"policy": "open"},
                        },
                    ]
                }
            ),
            bridge_factory=bridge_factory,
        )
        accepted = []
        adapter.set_message_handler(lambda event: accepted.append(event))
        self.assertTrue(await adapter.connect())
        self.assertTrue(all(bridge.started for bridge in bridges))
        assert bridges[0].event_handler is not None
        assert bridges[1].event_handler is not None

        await bridges[0].event_handler(
            {
                "type": "event",
                "event": "message",
                "payload": {
                    "session_type": "p2p",
                    "sender_id": "alice",
                    "target_id": "bot-a",
                    "text": "hello a",
                    "message_id": "m-a",
                    "message_type": "text",
                },
            }
        )
        await bridges[1].event_handler(
            {
                "type": "event",
                "event": "message",
                "payload": {
                    "session_type": "p2p",
                    "sender_id": "bob",
                    "target_id": "bot-b",
                    "text": "hello b",
                    "message_id": "m-b",
                    "message_type": "text",
                },
            }
        )

        self.assertEqual(["acct:app%3Abot-a:user:alice", "acct:app%3Abot-b:user:bob"], [e.source.chat_id for e in accepted])
        self.assertEqual("app:bot-a", accepted[0].raw["metadata"]["nim_account_id"])
        self.assertEqual("app:bot-b", accepted[1].raw["metadata"]["nim_account_id"])

        result = await adapter.send("acct:app%3Abot-b:user:bob", "reply b")
        self.assertTrue(result.success)
        self.assertEqual([], bridges[0].sent)
        self.assertEqual("user:bob", bridges[1].sent[0]["chat_id"])

    async def test_multi_instance_blocks_ambiguous_unprefixed_outbound(self) -> None:
        adapter = NimAdapter(
            PlatformConfig(
                extra={
                    "instances": [
                        {"enabled": True, "nimToken": "app|bot-a|secret-a"},
                        {"enabled": True, "nimToken": "app|bot-b|secret-b"},
                    ]
                }
            ),
            bridge_factory=lambda _config: FakeBridge(),
        )
        self.assertTrue(await adapter.connect())

        result = await adapter.send("user:alice", "ambiguous")

        self.assertFalse(result.success)
        self.assertEqual("no NIM instance is connected for target", result.error)

    async def test_direct_message_explicit_p2p_policy(self) -> None:
        bridge = FakeBridge()
        adapter = NimAdapter(
            PlatformConfig(
                extra={
                    "nim_token": "app|bot|secret",
                    "p2p_policy": "allowlist",
                    "p2p_allow_from": ["alice"],
                }
            ),
            bridge=bridge,
        )
        accepted = []
        adapter.set_message_handler(lambda event: accepted.append(event))
        await adapter.connect()
        assert bridge.event_handler is not None

        for sender in ("bob", "alice"):
            await bridge.event_handler(
                {
                    "type": "event",
                    "event": "message",
                    "payload": {
                        "session_type": "p2p",
                        "sender_id": sender,
                        "target_id": "bot",
                        "text": "hello",
                        "message_id": f"m-{sender}",
                        "message_type": "text",
                    },
                }
            )

        self.assertEqual(1, len(accepted))
        self.assertEqual("alice", accepted[0].source.user_id)

    async def test_direct_message_disabled_p2p_policy(self) -> None:
        bridge = FakeBridge()
        adapter = NimAdapter(
            PlatformConfig(
                extra={
                    "nim_token": "app|bot|secret",
                    "p2p_policy": "disabled",
                }
            ),
            bridge=bridge,
        )
        accepted = []
        adapter.set_message_handler(lambda event: accepted.append(event))
        await adapter.connect()
        assert bridge.event_handler is not None

        await bridge.event_handler(
            {
                "type": "event",
                "event": "message",
                "payload": {
                    "session_type": "p2p",
                    "sender_id": "alice",
                    "target_id": "bot",
                    "text": "hello",
                    "message_id": "m-disabled",
                    "message_type": "text",
                },
            }
        )

        self.assertEqual([], accepted)

    async def test_group_message_requires_mention_and_allowlist(self) -> None:
        bridge = FakeBridge()
        adapter = NimAdapter(
            PlatformConfig(
                extra={
                    "nim_token": "app|bot|secret",
                    "group_policy": "allowlist",
                    "group_allowlist": ["team-1"],
                }
            ),
            bridge=bridge,
        )
        accepted = []
        adapter.set_message_handler(lambda event: accepted.append(event))
        await adapter.connect()
        assert bridge.event_handler is not None

        await bridge.event_handler(
            {
                "type": "event",
                "event": "message",
                "payload": {
                    "session_type": "team",
                    "sender_id": "alice",
                    "target_id": "team-1",
                    "text": "bot please answer",
                    "message_id": "m-3",
                    "message_type": "text",
                    "force_push_account_ids": [],
                },
            }
        )
        await bridge.event_handler(
            {
                "type": "event",
                "event": "message",
                "payload": {
                    "session_type": "team",
                    "sender_id": "alice",
                    "target_id": "team-1",
                    "text": "bot please answer",
                    "message_id": "m-4",
                    "message_type": "text",
                    "force_push_account_ids": ["bot"],
                },
            }
        )
        await bridge.event_handler(
            {
                "type": "event",
                "event": "message",
                "payload": {
                    "session_type": "team",
                    "sender_id": "alice",
                    "target_id": "team-2",
                    "text": "bot please answer",
                    "message_id": "m-5",
                    "message_type": "text",
                    "force_push_account_ids": ["bot"],
                },
            }
        )

        self.assertEqual(1, len(accepted))
        self.assertEqual("team:team-1", accepted[0].source.chat_id)

    async def test_inbound_reply_context_is_forwarded(self) -> None:
        bridge = FakeBridge()
        adapter = NimAdapter(
            PlatformConfig(
                extra={
                    "nim_token": "app|bot|secret",
                    "p2p_policy": "open",
                }
            ),
            bridge=bridge,
        )
        accepted = []
        adapter.set_message_handler(lambda event: accepted.append(event))
        await adapter.connect()
        assert bridge.event_handler is not None

        await bridge.event_handler(
            {
                "type": "event",
                "event": "message",
                "payload": {
                    "session_type": "p2p",
                    "sender_id": "alice",
                    "target_id": "bot",
                    "text": "reply text",
                    "message_id": "reply-server",
                    "message_type": "text",
                    "reply_to_message_id": "source-server",
                    "reply_to_text": "source text",
                    "reply_to_author_id": "bot",
                    "reply_to_author_name": "Nim Bot",
                    "reply_to_is_own_message": True,
                },
            }
        )

        self.assertEqual(1, len(accepted))
        event = accepted[0]
        self.assertEqual("source-server", event.reply_to_message_id)
        self.assertEqual("source text", event.reply_to_text)
        self.assertEqual("bot", event.reply_to_author_id)
        self.assertEqual("Nim Bot", event.reply_to_author_name)
        self.assertTrue(event.reply_to_is_own_message)
        self.assertEqual("source-server", event.raw["metadata"]["reply_to_message_id"])

    async def test_non_online_message_is_ignored(self) -> None:
        bridge = FakeBridge()
        adapter = NimAdapter(
            PlatformConfig(
                extra={
                    "nim_token": "app|bot|secret",
                    "p2p_policy": "open",
                }
            ),
            bridge=bridge,
        )
        accepted = []
        adapter.set_message_handler(lambda event: accepted.append(event))
        await adapter.connect()
        assert bridge.event_handler is not None

        await bridge.event_handler(
            {
                "type": "event",
                "event": "message",
                "payload": {
                    "session_type": "p2p",
                    "sender_id": "alice",
                    "target_id": "bot",
                    "text": "old message",
                    "message_id": "old-1",
                    "message_type": "text",
                    "message_source": 3,
                },
            }
        )

        self.assertEqual([], accepted)

    async def test_send_uses_session_prefix(self) -> None:
        bridge = FakeBridge()
        adapter = NimAdapter(
            PlatformConfig(extra={"nim_token": "app|bot|secret"}),
            bridge=bridge,
        )
        await adapter.connect()
        result = await adapter.send("team:123", "hello")
        self.assertTrue(result.success)
        self.assertEqual("team", bridge.sent[0]["session_type"])

    async def test_connection_events_update_connected_state(self) -> None:
        bridge = FakeBridge()
        adapter = NimAdapter(
            PlatformConfig(extra={"nim_token": "app|bot|secret"}),
            bridge=bridge,
        )
        await adapter.connect()
        self.assertTrue(adapter.connected)
        assert bridge.event_handler is not None

        await bridge.event_handler(
            {
                "type": "event",
                "event": "connection",
                "payload": {"status": "disconnected", "reason": "network"},
            }
        )
        self.assertFalse(adapter.connected)

        await bridge.event_handler(
            {
                "type": "event",
                "event": "connection",
                "payload": {"status": "connected", "reason": "login"},
            }
        )
        self.assertTrue(adapter.connected)

    async def test_send_routes_qchat_targets_to_qchat_bridge(self) -> None:
        bridge = FakeBridge()
        adapter = NimAdapter(
            PlatformConfig(extra={"nim_token": "app|bot|secret"}),
            bridge=bridge,
        )
        await adapter.connect()
        result = await adapter.send("qchat:server-a:channel-b", "hello")
        self.assertTrue(result.success)
        self.assertEqual("qchat", bridge.qchat_sent[0]["session_type"])
        self.assertEqual("qchat:server-a:channel-b", bridge.qchat_sent[0]["chat_id"])

    async def test_send_blocks_qchat_when_policy_disables_target(self) -> None:
        bridge = FakeBridge()
        adapter = NimAdapter(
            PlatformConfig(
                extra={
                    "nim_token": "app|bot|secret",
                    "qchat_policy": "disabled",
                }
            ),
            bridge=bridge,
        )
        await adapter.connect()
        result = await adapter.send("qchat:server-a:channel-b", "hello")
        self.assertFalse(result.success)
        self.assertEqual("qchat send blocked by policy", result.error)
        self.assertEqual([], bridge.qchat_sent)

    async def test_send_blocks_qchat_allowlist_without_target_match(self) -> None:
        bridge = FakeBridge()
        adapter = NimAdapter(
            PlatformConfig(
                extra={
                    "nim_token": "app|bot|secret",
                    "qchat_policy": "allowlist",
                    "qchat_allow_from": ["server-a|channel-a"],
                }
            ),
            bridge=bridge,
        )
        await adapter.connect()
        result = await adapter.send("qchat:server-a:channel-b", "hello")
        self.assertFalse(result.success)
        self.assertEqual("qchat send blocked by policy", result.error)
        self.assertEqual([], bridge.qchat_sent)

    async def test_send_image_file_uses_bridge_media_path(self) -> None:
        bridge = FakeBridge()
        adapter = NimAdapter(
            PlatformConfig(extra={"nim_token": "app|bot|secret"}),
            bridge=bridge,
        )
        await adapter.connect()
        result = await adapter.send_image_file("team:123", "/tmp/test.png")
        self.assertTrue(result.success)
        self.assertEqual("image", bridge.media_sent[0]["media_kind"])
        self.assertEqual("team", bridge.media_sent[0]["session_type"])
        self.assertEqual("/tmp/test.png", bridge.media_sent[0]["file_path"])

    async def test_send_uses_stream_metadata_path(self) -> None:
        bridge = FakeBridge()
        adapter = NimAdapter(
            PlatformConfig(extra={"nim_token": "app|bot|secret"}),
            bridge=bridge,
        )
        await adapter.connect()
        result = await adapter.send(
            "user:alice",
            "chunk",
            metadata={
                "stream": {
                    "chunk_index": 2,
                    "is_complete": "false",
                },
                "reply_to": "server-1",
            },
        )
        self.assertTrue(result.success)
        self.assertEqual("stream-1", result.message_id)
        self.assertEqual(2, bridge.stream_sent[0]["chunk_index"])
        self.assertEqual(False, bridge.stream_sent[0]["is_complete"])
        self.assertEqual("server-1", bridge.stream_sent[0]["reply_to"])

    async def test_send_stream_invalid_chunk_index_falls_back_to_zero(self) -> None:
        bridge = FakeBridge()
        adapter = NimAdapter(
            PlatformConfig(extra={"nim_token": "app|bot|secret"}),
            bridge=bridge,
        )
        await adapter.connect()
        result = await adapter.send(
            "user:alice",
            "chunk",
            metadata={
                "stream": {
                    "chunk_index": "bad",
                },
            },
        )
        self.assertTrue(result.success)
        self.assertEqual(0, bridge.stream_sent[0]["chunk_index"])

    async def test_inbound_metadata_is_forwarded_in_raw_metadata(self) -> None:
        bridge = FakeBridge()
        adapter = NimAdapter(
            PlatformConfig(extra={"nim_token": "app|bot|secret"}),
            bridge=bridge,
        )
        accepted = []
        adapter.set_message_handler(lambda event: accepted.append(event))
        await adapter.connect()
        assert bridge.event_handler is not None
        await bridge.event_handler(
            {
                "type": "event",
                "event": "message",
                "payload": {
                    "session_type": "p2p",
                    "sender_id": "alice",
                    "target_id": "bot",
                    "text": "hello",
                    "message_id": "m-1",
                    "message_type": "text",
                    "topic_info": {"topicId": 1},
                    "topic_name": "Topic",
                    "batch_id": "batch-1",
                    "batch_key": "p2p:alice",
                    "batch_index": 0,
                    "batch_size": 1,
                    "quick_comment": {"index": 72},
                },
            }
        )
        metadata = accepted[0].raw["metadata"]
        self.assertEqual({"topicId": 1}, metadata["topic_info"])
        self.assertEqual("Topic", metadata["topic_name"])
        self.assertEqual("batch-1", metadata["batch_id"])
        self.assertEqual("p2p:alice", metadata["batch_key"])
        self.assertEqual({"index": 72}, metadata["quick_comment"])

    async def test_send_uses_edit_metadata_path(self) -> None:
        bridge = FakeBridge()
        adapter = NimAdapter(
            PlatformConfig(extra={"nim_token": "app|bot|secret"}),
            bridge=bridge,
        )
        await adapter.connect()
        result = await adapter.send(
            "team:team-1",
            "replacement",
            metadata={"edit_message_id": "old-1"},
        )
        self.assertTrue(result.success)
        self.assertEqual("edit-1", result.message_id)
        self.assertEqual("team", bridge.edits[0]["session_type"])
        self.assertEqual("old-1", bridge.edits[0]["message_id"])

    async def test_send_media_forwards_reply_to(self) -> None:
        bridge = FakeBridge()
        adapter = NimAdapter(
            PlatformConfig(extra={"nim_token": "app|bot|secret"}),
            bridge=bridge,
        )
        await adapter.connect()
        result = await adapter.send_image_file("user:alice", "/tmp/test.png", reply_to="server-1")
        self.assertTrue(result.success)
        self.assertEqual("server-1", bridge.media_sent[0]["reply_to"])

    async def test_send_media_forwards_metadata_reply_to(self) -> None:
        bridge = FakeBridge()
        adapter = NimAdapter(
            PlatformConfig(extra={"nim_token": "app|bot|secret"}),
            bridge=bridge,
        )
        await adapter.connect()
        result = await adapter.send_document(
            "user:alice",
            "/tmp/report.pdf",
            metadata={"reply_to": "client-1"},
        )
        self.assertTrue(result.success)
        self.assertEqual("client-1", bridge.media_sent[0]["reply_to"])

    async def test_qchat_media_falls_back_to_one_text_message(self) -> None:
        bridge = FakeBridge()
        adapter = NimAdapter(
            PlatformConfig(extra={"nim_token": "app|bot|secret"}),
            bridge=bridge,
        )
        await adapter.connect()
        result = await adapter.send_image_file("qchat:server-a:channel-b", "/tmp/test.png")
        self.assertTrue(result.success)
        self.assertEqual([], bridge.media_sent)
        self.assertEqual("/tmp/test.png", bridge.qchat_sent[0]["text"])

    async def test_media_caption_sends_followup_text(self) -> None:
        bridge = FakeBridge()
        adapter = NimAdapter(
            PlatformConfig(extra={"nim_token": "app|bot|secret"}),
            bridge=bridge,
        )
        await adapter.connect()
        result = await adapter.send_document(
            "user:alice",
            "/tmp/report.pdf",
            caption="see attachment",
        )
        self.assertTrue(result.success)
        self.assertEqual("file", bridge.media_sent[0]["media_kind"])
        self.assertEqual("see attachment", bridge.sent[0]["text"])
        self.assertEqual("p2p", bridge.sent[0]["session_type"])

    async def test_inbound_media_event_caches_attachment_paths(self) -> None:
        bridge = FakeBridge()

        async def attachment_loader(payload, kind):
            self.assertEqual("image", kind)
            self.assertEqual("https://example.com/a.png", payload["attachment"]["url"])
            return ["/tmp/cached-a.png"], ["image/png"]

        adapter = NimAdapter(
            PlatformConfig(extra={"nim_token": "app|bot|secret"}),
            bridge=bridge,
            attachment_loader=attachment_loader,
        )
        accepted = []
        adapter.set_message_handler(lambda event: accepted.append(event))
        await adapter.connect()
        assert bridge.event_handler is not None

        await bridge.event_handler(
            {
                "type": "event",
                "event": "message",
                "payload": {
                    "session_type": "p2p",
                    "sender_id": "alice",
                    "target_id": "bot",
                    "text": "[Image] https://example.com/a.png",
                    "message_id": "m-6",
                    "message_type": "image",
                    "attachment": {
                        "url": "https://example.com/a.png",
                        "name": "a.png",
                    },
                },
            }
        )

        self.assertEqual(1, len(accepted))
        self.assertEqual(["/tmp/cached-a.png"], accepted[0].media_urls)
        self.assertEqual(["image/png"], accepted[0].media_types)

    async def test_inbound_qchat_requires_mention_and_allowlist_match(self) -> None:
        bridge = FakeBridge()
        adapter = NimAdapter(
            PlatformConfig(
                extra={
                    "nim_token": "app|bot|secret",
                    "qchat_policy": "allowlist",
                    "qchat_allow_from": ["server-a|channel-a"],
                }
            ),
            bridge=bridge,
        )
        accepted = []
        adapter.set_message_handler(lambda event: accepted.append(event))
        await adapter.connect()
        assert bridge.event_handler is not None

        await bridge.event_handler(
            {
                "type": "event",
                "event": "message",
                "payload": {
                    "session_type": "qchat",
                    "sender_id": "alice",
                    "server_id": "server-a",
                    "channel_id": "channel-b",
                    "target_id": "server-a:channel-b",
                    "text": "hello",
                    "message_id": "m-7",
                    "message_type": "text",
                    "mentioned": True,
                },
            }
        )
        await bridge.event_handler(
            {
                "type": "event",
                "event": "message",
                "payload": {
                    "session_type": "qchat",
                    "sender_id": "alice",
                    "server_id": "server-a",
                    "channel_id": "channel-a",
                    "target_id": "server-a:channel-a",
                    "text": "hello",
                    "message_id": "m-8",
                    "message_type": "text",
                    "mentioned": False,
                },
            }
        )
        await bridge.event_handler(
            {
                "type": "event",
                "event": "message",
                "payload": {
                    "session_type": "qchat",
                    "sender_id": "alice",
                    "server_id": "server-a",
                    "channel_id": "channel-a",
                    "target_id": "server-a:channel-a",
                    "text": "hello",
                    "message_id": "m-9",
                    "message_type": "text",
                    "mentioned": True,
                },
            }
        )

        self.assertEqual(1, len(accepted))
        self.assertEqual("qchat:server-a:channel-a", accepted[0].source.chat_id)

    async def test_inbound_qchat_injects_channel_context_once(self) -> None:
        bridge = FakeBridge()
        adapter = NimAdapter(
            PlatformConfig(extra={"nim_token": "app|bot|secret", "qchat_policy": "open"}),
            bridge=bridge,
        )
        accepted = []
        adapter.set_message_handler(lambda event: accepted.append(event))
        await adapter.connect()
        assert bridge.event_handler is not None
        await bridge.event_handler(
            {
                "type": "event",
                "event": "message",
                "payload": {
                    "session_type": "qchat",
                    "sender_id": "alice",
                    "server_id": "server-a",
                    "channel_id": "channel-a",
                    "target_id": "server-a:channel-a",
                    "conversation_name": "General",
                    "channel_topic": "Daily work",
                    "text": "hello",
                    "message_id": "qchat-context",
                    "message_type": "text",
                    "mentioned": True,
                },
            }
        )
        self.assertEqual("[QChat channel=General; topic=Daily work]\nhello", accepted[0].text)
        self.assertEqual("云信·圈组·General", accepted[0].source.chat_name)

    async def test_inbound_qchat_title_falls_back_to_server_and_channel(self) -> None:
        bridge = FakeBridge()
        adapter = NimAdapter(
            PlatformConfig(extra={"nim_token": "app|bot|secret", "qchat_policy": "open"}),
            bridge=bridge,
        )
        accepted = []
        adapter.set_message_handler(lambda event: accepted.append(event))
        await adapter.connect()
        assert bridge.event_handler is not None
        await bridge.event_handler(
            {
                "type": "event",
                "event": "message",
                "payload": {
                    "session_type": "qchat",
                    "sender_id": "alice",
                    "server_id": "server-a",
                    "channel_id": "channel-a",
                    "target_id": "server-a:channel-a",
                    "text": "hello",
                    "message_id": "qchat-title-fallback",
                    "message_type": "text",
                    "mentioned": True,
                },
            }
        )
        self.assertEqual("云信·圈组·server-a:channel-a", accepted[0].source.chat_name)
        self.assertEqual("[QChat channel=server-a:channel-a]\nhello", accepted[0].text)

    async def test_same_sender_topics_use_distinct_chat_ids_and_titles(self) -> None:
        bridge = FakeBridge()
        adapter = NimAdapter(
            PlatformConfig(extra={"nim_token": "app|bot|secret", "p2p_policy": "open"}),
            bridge=bridge,
        )
        accepted = []
        adapter.set_message_handler(lambda event: accepted.append(event))
        await adapter.connect()
        assert bridge.event_handler is not None
        for topic_id, topic_name in ((1, "Release"), (2, "Support")):
            await bridge.event_handler(
                {
                    "type": "event",
                    "event": "message",
                    "payload": {
                        "session_type": "p2p",
                        "sender_id": "alice",
                        "target_id": "bot",
                        "conversation_name": "云信·单聊·Alice",
                        "topic_refer": {
                            "topicId": topic_id,
                            "conversationId": "0|1|alice",
                            "createTime": 100,
                        },
                        "topic_name": topic_name,
                        "text": "hello",
                        "message_id": f"topic-{topic_id}",
                        "message_type": "text",
                    },
                }
            )
        self.assertEqual(["user:alice:topic:1", "user:alice:topic:2"], [event.source.chat_id for event in accepted])
        self.assertEqual("云信·单聊·Alice · Release", accepted[0].source.chat_name)
        self.assertEqual("云信·单聊·Alice · Support", accepted[1].source.chat_name)

    async def test_topic_target_forwards_topic_to_text_media_and_stream(self) -> None:
        bridge = FakeBridge()
        adapter = NimAdapter(PlatformConfig(extra={"nim_token": "app|bot|secret"}), bridge=bridge)
        await adapter.connect()

        await adapter.send("user:alice:topic:42", "text")
        await adapter.send_image_file("user:alice:topic:42", "/tmp/test.png")
        await adapter.send(
            "user:alice:topic:42",
            "chunk",
            metadata={"stream": {"stream_id": "answer-42", "is_complete": False}},
        )

        self.assertEqual(42, bridge.sent[0]["topic_id"])
        self.assertEqual(42, bridge.media_sent[0]["topic_id"])
        self.assertEqual(42, bridge.stream_sent[0]["topic_id"])
        self.assertEqual("answer-42", bridge.stream_sent[0]["stream_id"])

    async def test_qchat_media_fallback_keeps_caption_and_reply(self) -> None:
        bridge = FakeBridge()
        adapter = NimAdapter(
            PlatformConfig(extra={"nim_token": "app|bot|secret", "qchat_policy": "open"}),
            bridge=bridge,
        )
        await adapter.connect()
        result = await adapter.send_document(
            "qchat:server-a:channel-a",
            "/tmp/report.pdf",
            caption="report",
            reply_to="source-1",
        )
        self.assertTrue(result.success)
        self.assertEqual("report\n/tmp/report.pdf", bridge.qchat_sent[0]["text"])
        self.assertEqual("source-1", bridge.qchat_sent[0]["reply_to"])

    def test_inbound_attachment_preserves_scene_name(self) -> None:
        attachment = parse_inbound_attachment(
            {
                "attachment": {
                    "url": "https://example.com/v.aac",
                    "name": "voice.aac",
                    "sceneName": "voice.scene",
                }
            }
        )
        self.assertIsNotNone(attachment)
        self.assertEqual("voice.scene", attachment.scene_name)


class NodeBridgeProcessTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_failure_cleans_up_process(self) -> None:
        script = """
import json
import sys
import time
line = sys.stdin.readline()
request = json.loads(line)
print(json.dumps({"id": request["id"], "type": "response", "status": "error", "error": "boom"}), flush=True)
time.sleep(10)
"""
        bridge = NodeBridgeProcess(
            [sys.executable, "-c", script],
            request_timeout=0.2,
            stop_timeout=0.2,
        )
        config = NimAdapter(PlatformConfig(extra={"nim_token": "app|bot|secret"})).resolved
        with self.assertRaises(BridgeError):
            await bridge.start(config)
        self.assertIsNone(bridge._process)

    async def test_stop_kills_unresponsive_process(self) -> None:
        script = """
import json
import sys
import time
line = sys.stdin.readline()
request = json.loads(line)
print(json.dumps({"id": request["id"], "type": "response", "status": "ok", "result": {"connected": True}}), flush=True)
time.sleep(10)
"""
        bridge = NodeBridgeProcess(
            [sys.executable, "-c", script],
            request_timeout=0.5,
            stop_timeout=0.05,
        )
        config = NimAdapter(PlatformConfig(extra={"nim_token": "app|bot|secret"})).resolved
        await bridge.start(config)
        bridge._request_timeout = 0.05
        started_at = time.monotonic()
        await bridge.stop()
        self.assertLess(time.monotonic() - started_at, 1.0)
        self.assertIsNone(bridge._process)


if __name__ == "__main__":
    unittest.main()
