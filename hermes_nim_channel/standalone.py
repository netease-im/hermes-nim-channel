from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any


_DEFAULT_TIMEOUT_SECONDS = 15.0
_MAX_REQUEST_BYTES = 64 * 1024


class StandaloneRelayError(RuntimeError):
    pass


def standalone_socket_path(environ: dict[str, str] | None = None) -> Path:
    env = environ if environ is not None else os.environ
    hermes_home = env.get("HERMES_HOME", "").strip()
    base = Path(hermes_home).expanduser() if hermes_home else Path.home() / ".hermes"
    return base / "nim-channel.sock"


def _send_result_payload(result: Any, *, chat_id: str) -> dict[str, Any]:
    if not bool(getattr(result, "success", False)):
        error = getattr(result, "error", None) or "NIM adapter send failed"
        return {"error": str(error)}
    return {
        "success": True,
        "platform": "nim",
        "chat_id": chat_id,
        "message_id": getattr(result, "message_id", None),
    }


class NimStandaloneRelay:
    def __init__(self, adapter: Any, *, socket_path: Path | None = None) -> None:
        self._adapter = adapter
        self.socket_path = socket_path or standalone_socket_path()
        self._server: asyncio.AbstractServer | None = None
        self._socket_identity: tuple[int, int] | None = None

    async def start(self) -> None:
        if self._server is not None:
            return
        if not hasattr(asyncio, "start_unix_server"):
            raise StandaloneRelayError("NIM standalone relay requires Unix socket support")

        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        await self._remove_stale_socket()
        self._server = await asyncio.start_unix_server(
            self._handle_client,
            path=str(self.socket_path),
            limit=_MAX_REQUEST_BYTES,
        )
        os.chmod(self.socket_path, 0o600)
        stat_result = self.socket_path.stat()
        self._socket_identity = (stat_result.st_dev, stat_result.st_ino)

    async def stop(self) -> None:
        server = self._server
        self._server = None
        if server is not None:
            server.close()
            await server.wait_closed()
        self._unlink_owned_socket()

    async def _remove_stale_socket(self) -> None:
        if not os.path.lexists(self.socket_path):
            return
        try:
            _reader, writer = await asyncio.wait_for(
                asyncio.open_unix_connection(str(self.socket_path)),
                timeout=0.5,
            )
        except (OSError, asyncio.TimeoutError):
            self.socket_path.unlink(missing_ok=True)
            return

        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        raise StandaloneRelayError(
            f"NIM standalone relay is already active at {self.socket_path}"
        )

    def _unlink_owned_socket(self) -> None:
        identity = self._socket_identity
        self._socket_identity = None
        if identity is None:
            return
        try:
            stat_result = self.socket_path.stat()
        except OSError:
            return
        if (stat_result.st_dev, stat_result.st_ino) == identity:
            self.socket_path.unlink(missing_ok=True)

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            line = await asyncio.wait_for(reader.readline(), timeout=_DEFAULT_TIMEOUT_SECONDS)
            if not line or len(line) >= _MAX_REQUEST_BYTES:
                raise StandaloneRelayError("invalid or oversized standalone send request")
            request = json.loads(line.decode("utf-8"))
            if not isinstance(request, dict) or request.get("action") != "send":
                raise StandaloneRelayError("unsupported standalone relay request")
            chat_id = str(request.get("chat_id") or "").strip()
            if not chat_id:
                raise StandaloneRelayError("standalone send requires chat_id")
            metadata = request.get("metadata")
            if not isinstance(metadata, dict):
                metadata = None
            result = await self._adapter.send(
                chat_id=chat_id,
                content=str(request.get("message") or ""),
                metadata=metadata,
            )
            response = _send_result_payload(result, chat_id=chat_id)
        except Exception as exc:
            response = {"error": f"NIM standalone relay failed: {exc}"}

        try:
            writer.write((json.dumps(response, ensure_ascii=False) + "\n").encode("utf-8"))
            await writer.drain()
        except (BrokenPipeError, ConnectionError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass


async def standalone_send_via_gateway(
    _pconfig: Any,
    chat_id: str,
    message: str,
    *,
    thread_id: str | None = None,
    media_files: Any = None,
    force_document: bool = False,
    socket_path: Path | None = None,
) -> dict[str, Any]:
    del media_files, force_document
    path = socket_path or standalone_socket_path()
    writer: asyncio.StreamWriter | None = None
    timeout = _DEFAULT_TIMEOUT_SECONDS
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_unix_connection(str(path)),
            timeout=1.0,
        )
        metadata = {"thread_id": str(thread_id)} if thread_id else None
        request = {
            "action": "send",
            "chat_id": str(chat_id),
            "message": str(message or ""),
            "metadata": metadata,
        }
        writer.write((json.dumps(request, ensure_ascii=False) + "\n").encode("utf-8"))
        await writer.drain()
        line = await asyncio.wait_for(reader.readline(), timeout=timeout)
        if not line:
            raise StandaloneRelayError("gateway closed the relay without a response")
        response = json.loads(line.decode("utf-8"))
        if not isinstance(response, dict):
            raise StandaloneRelayError("gateway returned an invalid relay response")
        return response
    except (OSError, asyncio.TimeoutError, json.JSONDecodeError, StandaloneRelayError) as exc:
        return {
            "error": (
                "NIM standalone send requires the Hermes gateway with NIM connected; "
                f"local relay {path} is unavailable: {exc}"
            )
        }
    finally:
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
