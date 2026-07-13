from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import os
from pathlib import Path
import shlex
import shutil
from typing import Any


class Platform(str, Enum):
    NIM = "nim"


@dataclass(slots=True)
class PlatformConfig:
    enabled: bool = True
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class NimCredentials:
    app_key: str
    account: str
    token: str


@dataclass(slots=True)
class NimResolvedConfig:
    enabled: bool
    credentials: NimCredentials | None
    allowed_users: list[str] = field(default_factory=list)
    allow_all_users: bool = False
    p2p_policy: str = "open"
    p2p_allow_from: list[str] = field(default_factory=list)
    group_policy: str = "allowlist"
    group_allowlist: list[str] = field(default_factory=list)
    qchat_policy: str = "open"
    qchat_allow_from: list[str] = field(default_factory=list)
    home_channel: str | None = None
    bridge_command: list[str] = field(default_factory=lambda: ["node", "bridge/index.mjs"])
    media_max_mb: int = 30
    debug: bool = False
    weblbs_url: str | None = None
    link_web: str | None = None
    nos_uploader: str | None = None
    nos_downloader_v2: str | None = None
    nos_ssl: bool | None = None
    nos_accelerate: str | None = None
    nos_accelerate_host: str | None = None
    raw_extra: dict[str, Any] = field(default_factory=dict)

    def configured(self) -> bool:
        return self.enabled and self.credentials is not None

    def to_bridge_payload(self) -> dict[str, Any]:
        creds = self.credentials
        return {
            "enabled": self.enabled,
            "credentials": {
                "app_key": creds.app_key if creds else "",
                "account": creds.account if creds else "",
                "token": creds.token if creds else "",
            },
            "debug": self.debug,
            "media_max_mb": self.media_max_mb,
            "home_channel": self.home_channel,
            "p2p": {
                "policy": self.p2p_policy,
                "allowFrom": self.p2p_allow_from,
            },
            "advanced": {
                "weblbsUrl": self.weblbs_url,
                "link_web": self.link_web,
                "nos_uploader": self.nos_uploader,
                "nos_downloader_v2": self.nos_downloader_v2,
                "nosSsl": self.nos_ssl,
                "nos_accelerate": self.nos_accelerate,
                "nos_accelerate_host": self.nos_accelerate_host,
            },
            "qchat": {
                "policy": self.qchat_policy,
                "allowFrom": self.qchat_allow_from,
            },
        }


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]


def _pick(extra: dict[str, Any], env: dict[str, str], key: str, env_key: str) -> Any:
    if key in extra and extra[key] not in (None, ""):
        return extra[key]
    return env.get(env_key)


def _pick_any(extra: dict[str, Any], env: dict[str, str], *keys: tuple[str, str]) -> Any:
    for key, env_key in keys:
        picked = _pick(extra, env, key, env_key)
        if picked not in (None, ""):
            return picked
    return None


def _as_optional_str(value: Any) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def parse_nim_token(value: Any) -> NimCredentials | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if "|" in raw:
        parts = raw.split("|", 2)
    else:
        parts = raw.split("-", 2)
    if len(parts) != 3 or any(not part for part in parts):
        return None
    return NimCredentials(app_key=parts[0], account=parts[1], token=parts[2])


def _default_bridge_command() -> list[str]:
    installed = shutil.which("hermes-nim-bridge")
    if installed:
        return [installed]
    bridge_script = Path(__file__).resolve().parent.parent / "bridge" / "index.mjs"
    return ["node", str(bridge_script)]


def _resolve_bridge_command(value: Any) -> list[str]:
    if value is None:
        return _default_bridge_command()
    if isinstance(value, str):
        return shlex.split(value)
    if isinstance(value, (list, tuple)):
        parts = [str(item).strip() for item in value if str(item).strip()]
        return parts or _default_bridge_command()
    raise TypeError("bridge_command must be a string or sequence of strings")


def load_nim_config(
    platform: PlatformConfig,
    environ: dict[str, str] | None = None,
) -> NimResolvedConfig:
    env = environ or dict(os.environ)
    extra = dict(platform.extra)

    nim_token = _pick(extra, env, "nim_token", "NIM_CREDENTIALS")
    credentials = parse_nim_token(nim_token)
    if credentials is None:
        app_key = _pick(extra, env, "app_key", "NIM_APP_KEY")
        account = _pick(extra, env, "account", "NIM_ACCOUNT")
        token = _pick(extra, env, "token", "NIM_TOKEN")
        if app_key and account and token:
            credentials = NimCredentials(
                app_key=str(app_key).strip(),
                account=str(account).strip(),
                token=str(token).strip(),
            )

    qchat_allow_from = _as_list(_pick(extra, env, "qchat_allow_from", "NIM_QCHAT_ALLOW_FROM"))
    if not qchat_allow_from:
        qchat_allow_from = _as_list(_pick(extra, env, "qchat_allowlist", "NIM_QCHAT_ALLOWLIST"))
    nos_ssl_value = _pick_any(extra, env, ("nos_ssl", "NIM_NOS_SSL"), ("nosSsl", "NIM_NOS_SSL"))
    allowed_users = _as_list(_pick(extra, env, "allowed_users", "NIM_ALLOWED_USERS"))
    allow_all_users = _as_bool(
        _pick(extra, env, "allow_all_users", "NIM_ALLOW_ALL_USERS"),
        default=False,
    )
    p2p_allow_from = _as_list(_pick(extra, env, "p2p_allow_from", "NIM_P2P_ALLOW_FROM"))
    if not p2p_allow_from:
        p2p_allow_from = allowed_users
    explicit_p2p_policy = _pick(extra, env, "p2p_policy", "NIM_P2P_POLICY")
    if explicit_p2p_policy not in (None, ""):
        p2p_policy = str(explicit_p2p_policy).strip() or "open"
    elif allow_all_users or not p2p_allow_from:
        p2p_policy = "open"
    else:
        p2p_policy = "allowlist"

    return NimResolvedConfig(
        enabled=platform.enabled,
        credentials=credentials,
        allowed_users=allowed_users,
        allow_all_users=allow_all_users,
        p2p_policy=p2p_policy,
        p2p_allow_from=p2p_allow_from,
        group_policy=str(_pick(extra, env, "group_policy", "NIM_GROUP_POLICY") or "allowlist").strip(),
        group_allowlist=_as_list(_pick(extra, env, "group_allowlist", "NIM_GROUP_ALLOWLIST")),
        qchat_policy=str(_pick(extra, env, "qchat_policy", "NIM_QCHAT_POLICY") or "open").strip(),
        qchat_allow_from=qchat_allow_from,
        home_channel=str(_pick(extra, env, "home_channel", "NIM_HOME_CHANNEL") or "").strip() or None,
        bridge_command=_resolve_bridge_command(_pick(extra, env, "bridge_command", "NIM_BRIDGE_COMMAND")),
        media_max_mb=int(_pick(extra, env, "media_max_mb", "NIM_MEDIA_MAX_MB") or 30),
        debug=_as_bool(_pick(extra, env, "debug", "NIM_DEBUG"), default=False),
        weblbs_url=_as_optional_str(_pick_any(extra, env, ("weblbs_url", "NIM_WEBLBS_URL"), ("weblbsUrl", "NIM_WEBLBS_URL"))),
        link_web=_as_optional_str(_pick(extra, env, "link_web", "NIM_LINK_WEB")),
        nos_uploader=_as_optional_str(_pick(extra, env, "nos_uploader", "NIM_NOS_UPLOADER")),
        nos_downloader_v2=_as_optional_str(_pick(extra, env, "nos_downloader_v2", "NIM_NOS_DOWNLOADER_V2")),
        nos_ssl=_as_bool(nos_ssl_value) if nos_ssl_value not in (None, "") else None,
        nos_accelerate=_as_optional_str(_pick(extra, env, "nos_accelerate", "NIM_NOS_ACCELERATE")),
        nos_accelerate_host=_as_optional_str(_pick(extra, env, "nos_accelerate_host", "NIM_NOS_ACCELERATE_HOST")),
        raw_extra=extra,
    )
