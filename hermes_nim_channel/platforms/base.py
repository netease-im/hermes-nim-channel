from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import inspect
from typing import Any, Awaitable, Callable

from hermes_nim_channel.config import Platform, PlatformConfig


class ChatType(str, Enum):
    DIRECT = "direct"
    GROUP = "group"


class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    FILE = "file"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class MessageSource:
    platform: str
    chat_id: str
    chat_type: str
    user_id: str
    user_name: str | None = None
    chat_name: str | None = None


@dataclass(slots=True)
class MessageEvent:
    message_id: str
    message_type: str
    text: str
    source: MessageSource
    raw: dict[str, Any]


@dataclass(slots=True)
class SendResult:
    success: bool
    message_id: str | None = None
    error: str | None = None


MessageHandler = Callable[[MessageEvent], Awaitable[None] | None]


class BasePlatformAdapter:
    def __init__(self, config: PlatformConfig, platform: Platform) -> None:
        self.config = config
        self.platform = platform
        self.connected = False
        self._message_handler: MessageHandler | None = None

    def set_message_handler(self, handler: MessageHandler) -> None:
        self._message_handler = handler

    async def handle_message(self, event: MessageEvent) -> None:
        if self._message_handler is None:
            return
        result = self._message_handler(event)
        if inspect.isawaitable(result):
            await result
