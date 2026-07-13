from __future__ import annotations

import asyncio
import unittest

from hermes_nim_channel.config import PlatformConfig
from hermes_nim_channel.platforms.nim import NimAdapter


class FakeBridge:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.sent: list[dict[str, str]] = []
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


if __name__ == "__main__":
    unittest.main()
