from __future__ import annotations

import json
import sqlite3
import tempfile
import time
from pathlib import Path
from unittest import TestCase, mock

from hermes_nim_channel.session_titles import pin_nim_session_title


class NimSessionTitleTests(TestCase):
    def test_pin_nim_session_title_updates_hermes_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            sessions_dir = home / "sessions"
            sessions_dir.mkdir()
            db_path = home / "state.db"
            conn = sqlite3.connect(db_path)
            try:
                conn.execute(
                    """
                    create table sessions (
                        id text primary key,
                        source text,
                        chat_id text,
                        chat_type text,
                        title text,
                        display_name text,
                        origin_json text
                    )
                    """
                )
                conn.execute(
                    """
                    create table gateway_routing (
                        scope text,
                        session_key text,
                        entry_json text,
                        updated_at real,
                        primary key (scope, session_key)
                    )
                    """
                )
                conn.execute(
                    "insert into sessions values (?, ?, ?, ?, ?, ?, ?)",
                    (
                        "session-1",
                        "nim",
                        "team:1",
                        "group",
                        "auto title",
                        "old name",
                        json.dumps({"chat_id": "team:1", "chat_name": "old"}),
                    ),
                )
                conn.execute(
                    "insert into gateway_routing values (?, ?, ?, ?)",
                    (
                        str(sessions_dir),
                        "agent:main:nim:group:team:1:alice",
                        json.dumps(
                            {
                                "display_name": "old name",
                                "origin": {"chat_id": "team:1", "chat_name": "old"},
                            }
                        ),
                        time.time(),
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            (sessions_dir / "sessions.json").write_text(
                json.dumps(
                    {
                        "agent:main:nim:group:team:1:alice": {
                            "display_name": "old name",
                            "origin": {"chat_id": "team:1", "chat_name": "old"},
                        }
                    }
                )
            )
            (home / "channel_directory.json").write_text(
                json.dumps({"platforms": {"nim": [{"id": "team:1", "name": "old name"}]}})
            )

            with mock.patch("hermes_nim_channel.session_titles._hermes_home", return_value=home):
                pin_nim_session_title(
                    {"chat_id": "team:1", "chat_type": "group", "user_name": "Alice"},
                    "云信·群聊·Engineering",
                )

            conn = sqlite3.connect(db_path)
            try:
                row = conn.execute(
                    "select title, display_name, origin_json from sessions where id = 'session-1'"
                ).fetchone()
                self.assertEqual("云信·群聊·Engineering", row[0])
                self.assertEqual("云信·群聊·Engineering", row[1])
                self.assertEqual("Alice", json.loads(row[2])["user_name"])
            finally:
                conn.close()

            sessions = json.loads((sessions_dir / "sessions.json").read_text())
            self.assertEqual(
                "云信·群聊·Engineering",
                sessions["agent:main:nim:group:team:1:alice"]["display_name"],
            )
            directory = json.loads((home / "channel_directory.json").read_text())
            self.assertEqual("云信·群聊·Engineering", directory["platforms"]["nim"][0]["name"])
