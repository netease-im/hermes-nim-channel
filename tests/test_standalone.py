from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import stat
import tempfile
import unittest

from hermes_nim_channel.standalone import (
    NimStandaloneRelay,
    standalone_send_via_gateway,
    standalone_socket_path,
)


@dataclass
class FakeSendResult:
    success: bool
    message_id: str | None = None
    error: str | None = None


class FakeAdapter:
    def __init__(self, result: FakeSendResult | None = None) -> None:
        self.result = result or FakeSendResult(True, message_id="message-1")
        self.sent: list[dict[str, object]] = []

    async def send(self, **kwargs):
        self.sent.append(kwargs)
        return self.result


class StandaloneRelayTests(unittest.IsolatedAsyncioTestCase):
    async def test_relay_forwards_to_connected_adapter_and_cleans_up(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "nim.sock"
            adapter = FakeAdapter()
            relay = NimStandaloneRelay(adapter, socket_path=path)
            await relay.start()
            self.assertEqual(0o600, stat.S_IMODE(path.stat().st_mode))

            result = await standalone_send_via_gateway(
                None,
                "team:123",
                "hello",
                thread_id="topic-1",
                socket_path=path,
            )

            self.assertTrue(result["success"])
            self.assertEqual("message-1", result["message_id"])
            self.assertEqual(
                {
                    "chat_id": "team:123",
                    "content": "hello",
                    "metadata": {"thread_id": "topic-1"},
                },
                adapter.sent[0],
            )
            await relay.stop()
            self.assertFalse(path.exists())

    async def test_relay_returns_adapter_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "nim.sock"
            relay = NimStandaloneRelay(
                FakeAdapter(FakeSendResult(False, error="blocked")),
                socket_path=path,
            )
            await relay.start()
            try:
                result = await standalone_send_via_gateway(
                    None,
                    "qchat:1:2",
                    "hello",
                    socket_path=path,
                )
            finally:
                await relay.stop()
            self.assertEqual({"error": "blocked"}, result)

    async def test_unavailable_relay_does_not_start_an_ephemeral_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "missing.sock"
            result = await standalone_send_via_gateway(
                None,
                "user:alice",
                "hello",
                socket_path=path,
            )
            self.assertIn("requires the Hermes gateway", result["error"])
            self.assertFalse(path.exists())

    async def test_stale_socket_path_is_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "nim.sock"
            path.write_text("stale", encoding="utf-8")
            relay = NimStandaloneRelay(FakeAdapter(), socket_path=path)
            await relay.start()
            try:
                self.assertTrue(path.exists())
                self.assertTrue(stat.S_ISSOCK(os.stat(path).st_mode))
            finally:
                await relay.stop()

    def test_socket_path_uses_hermes_home(self) -> None:
        self.assertEqual(
            Path("/tmp/hermes-test/nim-channel.sock"),
            standalone_socket_path({"HERMES_HOME": "/tmp/hermes-test"}),
        )
