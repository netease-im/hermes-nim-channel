from __future__ import annotations

import asyncio
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from hermes_nim_channel.platforms.nim_bridge import (
    _bridge_dir_for_command,
    ensure_bridge_dependencies,
)


class FakeNpmProcess:
    def __init__(self, install_marker: Path, returncode: int = 0) -> None:
        self.install_marker = install_marker
        self.returncode = returncode
        self.killed = False

    async def communicate(self) -> tuple[bytes, bytes]:
        if self.returncode == 0:
            self.install_marker.parent.mkdir(parents=True, exist_ok=True)
            self.install_marker.write_text("{}", encoding="utf-8")
        return b"", b""

    def kill(self) -> None:
        self.killed = True

    async def wait(self) -> int:
        return self.returncode


class NimBridgeBootstrapTests(unittest.IsolatedAsyncioTestCase):
    def test_bridge_dir_for_default_node_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bridge = root / "bridge"
            bridge.mkdir()
            (bridge / "package.json").write_text("{}", encoding="utf-8")

            self.assertEqual(
                bridge.resolve(),
                _bridge_dir_for_command(["node", "bridge/index.mjs"], str(root)),
            )

    def test_bridge_dir_ignores_custom_binary(self) -> None:
        self.assertIsNone(_bridge_dir_for_command(["hermes-nim-bridge"]))

    async def test_ensure_bridge_dependencies_skips_when_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bridge = Path(tmp) / "bridge"
            bridge.mkdir()
            (bridge / "package.json").write_text("{}", encoding="utf-8")
            with mock.patch("hermes_nim_channel.platforms.nim_bridge.asyncio.create_subprocess_exec") as create:
                await ensure_bridge_dependencies(
                    ["node", str(bridge / "index.mjs")],
                    environ={"NIM_AUTO_INSTALL_BRIDGE": "false"},
                )
            create.assert_not_called()

    async def test_ensure_bridge_dependencies_skips_when_installed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bridge = Path(tmp) / "bridge"
            marker = bridge / "node_modules" / "@yxim" / "nim-bot" / "package.json"
            marker.parent.mkdir(parents=True)
            marker.write_text("{}", encoding="utf-8")
            (bridge / "package.json").write_text("{}", encoding="utf-8")
            with mock.patch("hermes_nim_channel.platforms.nim_bridge.asyncio.create_subprocess_exec") as create:
                await ensure_bridge_dependencies(["node", str(bridge / "index.mjs")])
            create.assert_not_called()

    async def test_ensure_bridge_dependencies_runs_npm_ci_for_locked_bridge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bridge = Path(tmp) / "bridge"
            marker = bridge / "node_modules" / "@yxim" / "nim-bot" / "package.json"
            bridge.mkdir()
            (bridge / "package.json").write_text("{}", encoding="utf-8")
            (bridge / "package-lock.json").write_text("{}", encoding="utf-8")
            calls: list[tuple[str, ...]] = []

            async def fake_exec(*args, **kwargs):
                calls.append(tuple(args))
                self.assertEqual(bridge.resolve(), Path(kwargs["cwd"]).resolve())
                return FakeNpmProcess(marker)

            with (
                mock.patch("hermes_nim_channel.platforms.nim_bridge.shutil.which", return_value="/usr/bin/npm"),
                mock.patch(
                    "hermes_nim_channel.platforms.nim_bridge.asyncio.create_subprocess_exec",
                    side_effect=fake_exec,
                ),
            ):
                await ensure_bridge_dependencies(["node", str(bridge / "index.mjs")])

            self.assertTrue(marker.exists())
            self.assertEqual("/usr/bin/npm", calls[0][0])
            self.assertEqual("ci", calls[0][1])
            self.assertIn("--omit=dev", calls[0])


if __name__ == "__main__":
    unittest.main()
