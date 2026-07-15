from __future__ import annotations

from types import SimpleNamespace
import unittest
from pathlib import Path

from unittest import mock

from hermes_nim_channel.config import (
    PlatformConfig,
    _resolve_bridge_command,
    load_nim_instances,
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
                "NIM_INBOUND_DEBOUNCE_MS": "250",
                "NIM_QUICK_COMMENT_ENABLED": "true",
                "NIM_QUICK_COMMENT_INDEX": "72",
                "NIM_QUICK_COMMENT_TTL_MS": "5000",
                "NIM_LEGACY_LOGIN": "true",
                "NIM_ANTISPAM_ENABLED": "false",
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
        self.assertEqual(250, resolved.inbound_debounce_ms)
        self.assertTrue(resolved.quick_comment_enabled)
        self.assertEqual(72, resolved.quick_comment_index)
        self.assertEqual(5000, resolved.quick_comment_ttl_ms)
        payload = resolved.to_bridge_payload()
        self.assertEqual(1234, payload["text_chunk_limit"])
        self.assertEqual(250, payload["inbound_debounce_ms"])
        self.assertEqual({"enabled": True, "index": 72, "ttl_ms": 5000}, payload["quick_comment"])
        self.assertTrue(payload["legacy_login"])
        self.assertFalse(payload["antispam_enabled"])

    def test_group_policy_defaults_to_open(self) -> None:
        resolved = load_nim_config(
            PlatformConfig(),
            {
                "NIM_APP_KEY": "app",
                "NIM_ACCOUNT": "bot",
                "NIM_TOKEN": "secret",
            },
        )

        self.assertEqual("open", resolved.group_policy)

    def test_platform_home_channel_is_supported(self) -> None:
        platform = SimpleNamespace(
            enabled=True,
            extra={},
            home_channel=SimpleNamespace(chat_id="team:123"),
        )
        resolved = load_nim_config(
            platform,  # type: ignore[arg-type]
            {
                "NIM_APP_KEY": "app",
                "NIM_ACCOUNT": "bot",
                "NIM_TOKEN": "secret",
            },
        )

        self.assertEqual("team:123", resolved.home_channel)

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

    def test_optional_numeric_config_falls_back_or_clamps_invalid_values(self) -> None:
        resolved = load_nim_config(
            PlatformConfig(extra={"nim_token": "app|bot|secret"}),
            {
                "NIM_TEXT_CHUNK_LIMIT": "bad",
                "NIM_INBOUND_DEBOUNCE_MS": "-20",
                "NIM_QUICK_COMMENT_INDEX": "0",
                "NIM_QUICK_COMMENT_TTL_MS": "30s",
            },
        )
        self.assertEqual(4000, resolved.text_chunk_limit)
        self.assertEqual(0, resolved.inbound_debounce_ms)
        self.assertEqual(1, resolved.quick_comment_index)
        self.assertEqual(30000, resolved.quick_comment_ttl_ms)

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

    def test_load_nim_instances_supports_multiple_enabled_accounts(self) -> None:
        instances = load_nim_instances(
            PlatformConfig(
                extra={
                    "instances": [
                        {
                            "enabled": True,
                            "nimToken": "app|bot-a|secret-a",
                            "p2p": {"policy": "allowlist", "allowFrom": ["alice"]},
                        },
                        {
                            "enabled": True,
                            "appKey": "app",
                            "account": "bot-b",
                            "token": "secret-b",
                            "p2p": {"policy": "open"},
                            "qchat": {"policy": "allowlist", "allowFrom": ["server|channel"]},
                        },
                    ]
                }
            ),
            {},
        )

        self.assertEqual(["app:bot-a", "app:bot-b"], [item.resolved_account_id() for item in instances])
        self.assertEqual("allowlist", instances[0].p2p_policy)
        self.assertEqual(["alice"], instances[0].p2p_allow_from)
        self.assertEqual("open", instances[1].p2p_policy)
        self.assertEqual(["server|channel"], instances[1].qchat_allow_from)

    def test_load_nim_instances_rejects_duplicates_and_limits(self) -> None:
        with self.assertRaises(ValueError):
            load_nim_instances(
                PlatformConfig(
                    extra={
                        "instances": [
                            {"enabled": True, "nimToken": "app|bot|secret-a"},
                            {"enabled": True, "nimToken": "app|bot|secret-b"},
                        ]
                    }
                ),
                {},
            )
        with self.assertRaises(ValueError):
            load_nim_instances(
                PlatformConfig(
                    extra={
                        "instances": [
                            {"enabled": True, "nimToken": "app|bot-1|secret"},
                            {"enabled": True, "nimToken": "app|bot-2|secret"},
                            {"enabled": True, "nimToken": "app|bot-3|secret"},
                            {"enabled": True, "nimToken": "app|bot-4|secret"},
                        ]
                    }
                ),
                {},
            )


if __name__ == "__main__":
    unittest.main()
