from __future__ import annotations

import unittest

from hermes_nim_channel.targets import (
    append_topic_to_conversation_name,
    build_qchat_conversation_name,
    build_topic_chat_id,
    derive_stream_id,
    parse_topic_chat_id,
    qchat_context_text,
    qchat_channel_display_name,
    qchat_media_fallback_text,
    resolve_topic_id,
)


class TargetHelpersTests(unittest.TestCase):
    def test_topic_chat_id_round_trip_and_metadata_resolution(self) -> None:
        self.assertEqual("user:alice:topic:42", build_topic_chat_id("alice", 42))
        self.assertEqual(("alice", 42), parse_topic_chat_id("user:alice:topic:42"))
        self.assertEqual(42, resolve_topic_id("user:alice:topic:42"))
        self.assertEqual(9, resolve_topic_id("user:alice", {"topic_refer": {"topicId": "9"}}))
        self.assertIsNone(parse_topic_chat_id("user:alice"))

    def test_topic_title_and_qchat_context_are_idempotent(self) -> None:
        title = append_topic_to_conversation_name("云信·单聊·Alice", "Release")
        self.assertEqual("云信·单聊·Alice · Release", title)
        self.assertEqual(title, append_topic_to_conversation_name(title, "Release"))
        self.assertEqual(
            "云信·单聊·Alice · Alice",
            append_topic_to_conversation_name("云信·单聊·Alice", "Alice"),
        )

        text = qchat_context_text("hello", "General", "Daily work")
        self.assertEqual("[QChat channel=General; topic=Daily work]\nhello", text)
        self.assertEqual(text, qchat_context_text(text, "General", "Daily work"))

    def test_stream_and_qchat_media_fallback_helpers_are_stable(self) -> None:
        self.assertEqual(
            "hermes:user:alice:topic:42:message-1",
            derive_stream_id("user:alice:topic:42", "message-1"),
        )
        self.assertEqual("explicit", derive_stream_id("user:alice", None, "explicit"))
        self.assertEqual("caption\n/tmp/image.png", qchat_media_fallback_text("caption", "/tmp/image.png"))

    def test_qchat_conversation_title_matches_openclaw_format(self) -> None:
        self.assertEqual(
            "云信·圈组·General",
            build_qchat_conversation_name("General", "server-a", "channel-a"),
        )
        self.assertEqual(
            "云信·圈组·server-a:channel-a",
            build_qchat_conversation_name(None, "server-a", "channel-a"),
        )
        self.assertEqual(
            "云信·圈组·General",
            build_qchat_conversation_name("云信·圈组·General", "server-a", "channel-a"),
        )
        self.assertEqual(
            "General",
            qchat_channel_display_name("云信·圈组·General", "server-a", "channel-a"),
        )


if __name__ == "__main__":
    unittest.main()
