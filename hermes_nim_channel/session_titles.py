from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _hermes_home() -> Path:
    try:
        from hermes_constants import get_hermes_home

        return Path(get_hermes_home())
    except Exception:
        return Path.home() / ".hermes"


def _source_value(source: Any, name: str) -> str:
    return str(getattr(source, name, "") or "").strip()


def schedule_nim_session_title_pin(source: Any) -> None:
    """Keep Hermes WebUI titles aligned with OpenClaw-style NIM labels.

    Hermes auto-generates content titles asynchronously after the first turn.
    For IM platform sessions that is noisy: the stable conversation label is the
    NIM chat label, e.g. ``云信·群聊·<team name>``. Pinning a few times after
    dispatch wins the race without touching Hermes core.
    """
    title = _source_value(source, "chat_name")
    if not title.startswith("云信·"):
        return

    snapshot = {
        "chat_id": _source_value(source, "chat_id"),
        "chat_type": _source_value(source, "chat_type"),
        "user_name": _source_value(source, "user_name"),
    }
    if not snapshot["chat_id"]:
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        pin_nim_session_title(snapshot, title)
        return

    for delay in (1.0, 5.0, 20.0):
        loop.create_task(_pin_later(snapshot, title, delay))


async def _pin_later(source: dict[str, str], title: str, delay: float) -> None:
    await asyncio.sleep(delay)
    try:
        await asyncio.to_thread(pin_nim_session_title, source, title)
    except Exception:
        logger.debug("Failed to pin NIM session title", exc_info=True)


def pin_nim_session_title(source: dict[str, str], title: str) -> None:
    home = _hermes_home()
    _pin_state_db(home / "state.db", source, title)
    _pin_gateway_routing(home / "sessions" / "sessions.json", source, title)
    _pin_channel_directory(home / "channel_directory.json", source, title)


def _update_origin(origin: dict[str, Any], source: dict[str, str], title: str) -> dict[str, Any]:
    origin["chat_name"] = title
    if source.get("user_name"):
        origin["user_name"] = source["user_name"]
    return origin


def _pin_state_db(db_path: Path, source: dict[str, str], title: str) -> None:
    if not db_path.exists():
        return
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            """
            select id, origin_json
            from sessions
            where source = 'nim' and chat_id = ? and chat_type = ?
            """,
            (source["chat_id"], source.get("chat_type") or "dm"),
        ).fetchall()
        for session_id, origin_json in rows:
            try:
                origin = json.loads(origin_json or "{}")
            except Exception:
                origin = {}
            origin = _update_origin(origin, source, title)
            conn.execute(
                "update sessions set title = ?, display_name = ?, origin_json = ? where id = ?",
                (title, title, json.dumps(origin, ensure_ascii=False), session_id),
            )

        route_rows = conn.execute(
            "select scope, session_key, entry_json from gateway_routing where session_key like 'agent:main:nim:%'"
        ).fetchall()
        for scope, session_key, entry_json in route_rows:
            try:
                entry = json.loads(entry_json)
            except Exception:
                continue
            origin = entry.get("origin") if isinstance(entry.get("origin"), dict) else {}
            if origin.get("chat_id") != source["chat_id"]:
                continue
            entry["display_name"] = title
            entry["origin"] = _update_origin(origin, source, title)
            conn.execute(
                "update gateway_routing set entry_json = ?, updated_at = ? where scope = ? and session_key = ?",
                (json.dumps(entry, ensure_ascii=False), time.time(), scope, session_key),
            )
        conn.commit()
    finally:
        conn.close()


def _pin_gateway_routing(path: Path, source: dict[str, str], title: str) -> None:
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text())
    except Exception:
        return
    changed = False
    for entry in data.values():
        if not isinstance(entry, dict):
            continue
        origin = entry.get("origin") if isinstance(entry.get("origin"), dict) else {}
        if origin.get("chat_id") != source["chat_id"]:
            continue
        entry["display_name"] = title
        entry["origin"] = _update_origin(origin, source, title)
        changed = True
    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def _pin_channel_directory(path: Path, source: dict[str, str], title: str) -> None:
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text())
    except Exception:
        return
    changed = False
    for item in ((data.get("platforms") or {}).get("nim") or []):
        if isinstance(item, dict) and item.get("id") == source["chat_id"]:
            item["name"] = title
            changed = True
    if changed:
        data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
