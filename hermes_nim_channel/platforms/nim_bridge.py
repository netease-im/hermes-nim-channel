from __future__ import annotations

import asyncio
from collections.abc import Sequence
import os
from pathlib import Path
import shutil
import sys
from typing import Any, Awaitable, Callable

from hermes_nim_channel.config import NimResolvedConfig
from hermes_nim_channel.platforms.nim_protocol import decode_jsonl_line, encode_jsonl


BridgeEventHandler = Callable[[dict[str, Any]], Awaitable[None] | None]


class BridgeError(RuntimeError):
    pass


def _env_enabled(value: str | None, *, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _bridge_dir_for_command(command: Sequence[str], cwd: str | None = None) -> Path | None:
    if not command:
        return None
    executable = Path(command[0]).name.lower()
    if executable not in {"node", "node.exe"}:
        return None

    base_dir = Path(cwd or Path.cwd())
    script: Path | None = None
    for arg in command[1:]:
        if arg.startswith("-"):
            continue
        candidate = Path(arg)
        if candidate.name == "index.mjs":
            script = candidate if candidate.is_absolute() else base_dir / candidate
            break
    if script is None:
        return None

    bridge_dir = script.resolve().parent
    if (bridge_dir / "package.json").exists():
        return bridge_dir
    return None


def _bridge_dependencies_installed(bridge_dir: Path) -> bool:
    return (bridge_dir / "node_modules" / "@yxim" / "nim-bot" / "package.json").exists()


async def ensure_bridge_dependencies(
    command: Sequence[str],
    *,
    cwd: str | None = None,
    environ: dict[str, str] | None = None,
) -> None:
    env = environ if environ is not None else os.environ
    if not _env_enabled(env.get("NIM_AUTO_INSTALL_BRIDGE"), default=True):
        return

    bridge_dir = _bridge_dir_for_command(command, cwd)
    if bridge_dir is None or _bridge_dependencies_installed(bridge_dir):
        return

    npm = shutil.which("npm")
    if not npm:
        raise BridgeError(
            "NIM bridge dependencies are not installed and npm is not available. "
            f"Install Node.js/npm, then run: cd {bridge_dir} && npm install --omit=dev"
        )

    timeout_raw = env.get("NIM_BRIDGE_INSTALL_TIMEOUT_SEC", "180")
    try:
        timeout = max(1.0, float(timeout_raw))
    except (TypeError, ValueError):
        timeout = 180.0

    commands: list[list[str]]
    common_args = ["--omit=dev", "--no-audit", "--no-fund", "--progress=false"]
    if (bridge_dir / "package-lock.json").exists():
        commands = [["ci", *common_args], ["install", *common_args]]
    else:
        commands = [["install", *common_args]]

    last_output = ""
    for args in commands:
        sys.stderr.write(f"NIM bridge dependencies missing; running npm {' '.join(args)} in {bridge_dir}\n")
        process = await asyncio.create_subprocess_exec(
            npm,
            *args,
            cwd=str(bridge_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            if process.returncode is None:
                process.kill()
                await process.wait()
            raise BridgeError(
                f"NIM bridge dependency install timed out after {timeout:.0f}s. "
                f"Run manually: cd {bridge_dir} && npm install --omit=dev"
            ) from exc

        output = (stdout + stderr).decode("utf-8", errors="replace").strip()
        last_output = output
        if process.returncode == 0 and _bridge_dependencies_installed(bridge_dir):
            return

    detail = f"\n{last_output[-2000:]}" if last_output else ""
    raise BridgeError(
        "NIM bridge dependency install failed. "
        f"Run manually: cd {bridge_dir} && npm install --omit=dev{detail}"
    )


class NodeBridgeProcess:
    def __init__(
        self,
        command: Sequence[str],
        *,
        cwd: str | None = None,
        request_timeout: float = 10.0,
        stop_timeout: float = 3.0,
    ) -> None:
        self._command = list(command)
        self._cwd = cwd or str(Path.cwd())
        self._request_timeout = request_timeout
        self._stop_timeout = stop_timeout
        self._process: asyncio.subprocess.Process | None = None
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._next_id = 0
        self._stdout_task: asyncio.Task[None] | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._event_handler: BridgeEventHandler | None = None

    async def start(
        self,
        config: NimResolvedConfig,
        *,
        event_handler: BridgeEventHandler | None = None,
    ) -> None:
        if self._process is not None:
            return
        self._event_handler = event_handler
        await ensure_bridge_dependencies(self._command, cwd=self._cwd)
        self._process = await asyncio.create_subprocess_exec(
            *self._command,
            cwd=self._cwd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._stdout_task = asyncio.create_task(self._read_stdout())
        self._stderr_task = asyncio.create_task(self._read_stderr())
        try:
            response = await self.request("connect", {"config": config.to_bridge_payload()})
            if response.get("status") != "ok":
                raise BridgeError(response.get("error", "bridge connect failed"))
        except Exception:
            await self._cleanup_process(kill=True)
            raise

    async def stop(self) -> None:
        if self._process is None:
            return
        process = self._process
        try:
            await self.request("disconnect", {})
        except Exception:
            pass
        await self._cleanup_process(kill=False)

    async def _cleanup_process(self, *, kill: bool) -> None:
        process = self._process
        if process is None:
            return
        if process.stdin is not None and not process.stdin.is_closing():
            process.stdin.close()
            try:
                await process.stdin.wait_closed()
            except Exception:
                pass
        try:
            await asyncio.wait_for(process.wait(), timeout=0 if kill else self._stop_timeout)
        except (asyncio.TimeoutError, ProcessLookupError):
            if process.returncode is None:
                process.kill()
            try:
                await asyncio.wait_for(process.wait(), timeout=self._stop_timeout)
            except Exception:
                pass
        for task in (self._stdout_task, self._stderr_task):
            if task is not None and not task.done():
                task.cancel()
        for future in self._pending.values():
            if not future.done():
                future.cancel()
        self._pending.clear()
        self._process = None
        self._stdout_task = None
        self._stderr_task = None

    async def health(self) -> dict[str, Any]:
        response = await self.request("health", {})
        if response.get("status") != "ok":
            raise BridgeError(response.get("error", "bridge health failed"))
        return dict(response.get("result") or {})

    async def send_text(
        self,
        *,
        chat_id: str,
        text: str,
        session_type: str,
        reply_to: str | None = None,
        topic_id: int | None = None,
    ) -> dict[str, Any]:
        response = await self.request(
            "send_message",
            {
                "chat_id": chat_id,
                "text": text,
                "session_type": session_type,
                "reply_to": reply_to,
                "topic_id": topic_id,
            },
        )
        if response.get("status") != "ok":
            raise BridgeError(response.get("error", "send_message failed"))
        return dict(response.get("result") or {})

    async def send_qchat_message(
        self,
        *,
        chat_id: str,
        text: str,
        session_type: str,
        reply_to: str | None = None,
    ) -> dict[str, Any]:
        response = await self.request(
            "send_qchat_message",
            {
                "chat_id": chat_id,
                "text": text,
                "session_type": session_type,
                "reply_to": reply_to,
            },
        )
        if response.get("status") != "ok":
            raise BridgeError(response.get("error", "send_qchat_message failed"))
        return dict(response.get("result") or {})

    async def send_media(
        self,
        *,
        chat_id: str,
        file_path: str,
        media_kind: str,
        session_type: str,
        reply_to: str | None = None,
        topic_id: int | None = None,
    ) -> dict[str, Any]:
        response = await self.request(
            "send_media",
            {
                "chat_id": chat_id,
                "file_path": file_path,
                "media_kind": media_kind,
                "session_type": session_type,
                "reply_to": reply_to,
                "topic_id": topic_id,
            },
        )
        if response.get("status") != "ok":
            raise BridgeError(response.get("error", "send_media failed"))
        return dict(response.get("result") or {})

    async def send_stream_text(
        self,
        *,
        chat_id: str,
        text: str,
        session_type: str,
        chunk_index: int = 0,
        is_complete: bool = True,
        reply_to: str | None = None,
        stream_id: str | None = None,
        topic_id: int | None = None,
    ) -> dict[str, Any]:
        response = await self.request(
            "send_stream_message",
            {
                "chat_id": chat_id,
                "text": text,
                "session_type": session_type,
                "chunk_index": chunk_index,
                "is_complete": is_complete,
                "reply_to": reply_to,
                "stream_id": stream_id,
                "topic_id": topic_id,
            },
        )
        if response.get("status") != "ok":
            raise BridgeError(response.get("error", "send_stream_message failed"))
        return dict(response.get("result") or {})

    async def edit_message(
        self,
        *,
        chat_id: str,
        text: str,
        session_type: str,
        message_id: str | None = None,
    ) -> dict[str, Any]:
        response = await self.request(
            "edit_message",
            {
                "chat_id": chat_id,
                "text": text,
                "session_type": session_type,
                "message_id": message_id,
            },
        )
        if response.get("status") != "ok":
            raise BridgeError(response.get("error", "edit_message failed"))
        return dict(response.get("result") or {})

    async def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        process = self._process
        if process is None or process.stdin is None:
            raise BridgeError("bridge process is not running")
        self._next_id += 1
        request_id = str(self._next_id)
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[request_id] = future
        process.stdin.write(encode_jsonl({"id": request_id, "type": "request", "method": method, "params": params}))
        await process.stdin.drain()
        try:
            return await asyncio.wait_for(future, timeout=self._request_timeout)
        finally:
            self._pending.pop(request_id, None)

    async def _read_stdout(self) -> None:
        assert self._process is not None
        assert self._process.stdout is not None
        while True:
            line = await self._process.stdout.readline()
            if not line:
                return
            message = decode_jsonl_line(line)
            await self._dispatch_stdout(message)

    async def _dispatch_stdout(self, message: dict[str, Any]) -> None:
        message_type = message.get("type")
        if message_type == "response":
            request_id = str(message.get("id", ""))
            future = self._pending.get(request_id)
            if future is not None and not future.done():
                future.set_result(message)
            return
        if message_type == "event" and self._event_handler is not None:
            result = self._event_handler(message)
            if asyncio.iscoroutine(result):
                await result

    async def _read_stderr(self) -> None:
        assert self._process is not None
        assert self._process.stderr is not None
        while True:
            line = await self._process.stderr.readline()
            if not line:
                return
            sys.stderr.write(line.decode("utf-8", errors="replace"))
