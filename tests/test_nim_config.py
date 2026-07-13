from __future__ import annotations

import unittest
from pathlib import Path

from unittest import mock

from hermes_nim_channel.config import (
    PlatformConfig,
    _resolve_bridge_command,
    load_nim_config,
    parse_nim_token,
)


class NimConfigTests(unittest.TestCase):
    def test_parse_pipe_token(self) -> None:
        creds = parse_nim_token("app|bot|secret")
        self.assertIsNotNone(creds)
        assert creds is not None
        self.assertEqual("app", creds.app_key)
        self.assertEqual("bot", creds.account)
        self.assertEqual("secret", creds.token)

    def test_parse_legacy_token(self) -> None:
        creds = parse_nim_token("app-bot-secret")
        self.assertIsNotNone(creds)
        assert creds is not None
        self.assertEqual("bot", creds.account)

    def test_shorthand_overrides_discrete_fields(self) -> None:
        config = PlatformConfig(
            extra={
                "nim_token": "from-token|bot|secret",
                "app_key": "ignored",
                "account": "ignored",
                "token": "ignored",
            }
        )
        resolved = load_nim_config(config, {})
        assert resolved.credentials is not None
        self.assertEqual("from-token", resolved.credentials.app_key)

    def test_env_fallback_and_lists(self) -> None:
        resolved = load_nim_config(
            PlatformConfig(),
            {
                "NIM_APP_KEY": "app",
                "NIM_ACCOUNT": "bot",
                "NIM_TOKEN": "secret",
                "NIM_ALLOWED_USERS": "alice,bob",
                "NIM_GROUP_ALLOWLIST": "team-a,team-b",
                "NIM_GROUP_POLICY": "open",
                "NIM_QCHAT_POLICY": "allowlist",
                "NIM_QCHAT_ALLOW_FROM": "server-a|channel-a,server-b",
                "NIM_TEXT_CHUNK_LIMIT": "1234",
            },
        )
        assert resolved.credentials is not None
        self.assertEqual(["alice", "bob"], resolved.allowed_users)
        self.assertEqual("allowlist", resolved.p2p_policy)
        self.assertEqual(["alice", "bob"], resolved.p2p_allow_from)
        self.assertEqual(["team-a", "team-b"], resolved.group_allowlist)
        self.assertEqual("open", resolved.group_policy)
        self.assertEqual("allowlist", resolved.qchat_policy)
        self.assertEqual(["server-a|channel-a", "server-b"], resolved.qchat_allow_from)
        self.assertEqual(1234, resolved.text_chunk_limit)
        self.assertEqual(1234, resolved.to_bridge_payload()["text_chunk_limit"])

    def test_qchat_allowlist_alias_is_supported(self) -> None:
        resolved = load_nim_config(
            PlatformConfig(
                extra={
                    "nim_token": "app|bot|secret",
                    "qchat_allowlist": ["server-x|channel-y"],
                }
            ),
            {},
        )
        assert resolved.credentials is not None
        self.assertEqual(["server-x|channel-y"], resolved.qchat_allow_from)

    def test_explicit_p2p_policy_overrides_legacy_direct_allowlist(self) -> None:
        resolved = load_nim_config(
            PlatformConfig(),
            {
                "NIM_APP_KEY": "app",
                "NIM_ACCOUNT": "bot",
                "NIM_TOKEN": "secret",
                "NIM_ALLOWED_USERS": "legacy-user",
                "NIM_P2P_POLICY": "open",
                "NIM_P2P_ALLOW_FROM": "alice,bob",
            },
        )
        payload = resolved.to_bridge_payload()
        self.assertEqual("open", resolved.p2p_policy)
        self.assertEqual(["alice", "bob"], resolved.p2p_allow_from)
        self.assertEqual({"policy": "open", "allowFrom": ["alice", "bob"]}, payload["p2p"])

    def test_private_deployment_endpoints_are_added_to_bridge_payload(self) -> None:
        resolved = load_nim_config(
            PlatformConfig(),
            {
                "NIM_APP_KEY": "app",
                "NIM_ACCOUNT": "bot",
                "NIM_TOKEN": "secret",
                "NIM_WEBLBS_URL": "https://lbs.example.com",
                "NIM_LINK_WEB": "wss://link.example.com",
                "NIM_NOS_UPLOADER": "https://upload.example.com",
                "NIM_NOS_DOWNLOADER_V2": "https://download.example.com/{bucket}/{object}",
                "NIM_NOS_SSL": "true",
                "NIM_NOS_ACCELERATE": "https://cdn.example.com/{object}",
                "NIM_NOS_ACCELERATE_HOST": "cdn.example.com",
            },
        )
        payload = resolved.to_bridge_payload()
        advanced = payload["advanced"]
        self.assertEqual("https://lbs.example.com", advanced["weblbsUrl"])
        self.assertEqual("wss://link.example.com", advanced["link_web"])
        self.assertEqual("https://upload.example.com", advanced["nos_uploader"])
        self.assertEqual("https://download.example.com/{bucket}/{object}", advanced["nos_downloader_v2"])
        self.assertTrue(advanced["nosSsl"])
        self.assertEqual("https://cdn.example.com/{object}", advanced["nos_accelerate"])
        self.assertEqual("cdn.example.com", advanced["nos_accelerate_host"])

    def test_bridge_command_prefers_installed_binary(self) -> None:
        with mock.patch("hermes_nim_channel.config.shutil.which", return_value="/usr/local/bin/hermes-nim-bridge"):
            self.assertEqual(["/usr/local/bin/hermes-nim-bridge"], _resolve_bridge_command(None))

    def test_bridge_command_falls_back_to_repo_script(self) -> None:
        with mock.patch("hermes_nim_channel.config.shutil.which", return_value=None):
            command = _resolve_bridge_command(None)
        self.assertEqual("node", command[0])
        self.assertEqual(
            str(Path(__file__).resolve().parent.parent / "bridge" / "index.mjs"),
            command[1],
        )


if __name__ == "__main__":
    unittest.main()
