from __future__ import annotations

import asyncio
import unittest

from hermes_nim_channel.config import PlatformConfig
from hermes_nim_channel.inbound_media import parse_inbound_attachment
from hermes_nim_channel.platforms.nim import NimAdapter


class FakeBridge:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.sent: list[dict[str, str]] = []
        self.qchat_sent: list[dict[str, str]] = []
        self.media_sent: list[dict[str, str]] = []
        self.event_handler = None

    async def start(self, config, *, event_handler=None) -> None:
        self.started = True
        self.event_handler = event_handler

    async def stop(self) -> None:
        self.stopped = True

    async def health(self) -> dict[str, str]:
        return {"status": "ok"}

    async def send_text(self, *, chat_id: str, text: str, session_type: str, reply_to=None) -> dict[str, str]:
        self.sent.append(
            {
                "chat_id": chat_id,
                "text": text,
                "session_type": session_type,
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
    ) -> dict[str, str]:
        self.qchat_sent.append(
            {
                "chat_id": chat_id,
                "text": text,
                "session_type": session_type,
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
    ) -> dict[str, str]:
        self.media_sent.append(
            {
                "chat_id": chat_id,
                "file_path": file_path,
                "media_kind": media_kind,
                "session_type": session_type,
            }
        )
        return {"message_id": "media-1"}


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

    async def test_qchat_media_is_rejected_without_bridge_send(self) -> None:
        bridge = FakeBridge()
        adapter = NimAdapter(
            PlatformConfig(extra={"nim_token": "app|bot|secret"}),
            bridge=bridge,
        )
        await adapter.connect()
        result = await adapter.send_image_file("qchat:server-a:channel-b", "/tmp/test.png")
        self.assertFalse(result.success)
        self.assertEqual("qchat media is not supported", result.error)
        self.assertEqual([], bridge.media_sent)

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


if __name__ == "__main__":
    unittest.main()
