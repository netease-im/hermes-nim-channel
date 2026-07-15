from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
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
    account_id: str = ""
    allowed_users: list[str] = field(default_factory=list)
    allow_all_users: bool = False
    p2p_policy: str = "open"
    p2p_allow_from: list[str] = field(default_factory=list)
    group_policy: str = "open"
    group_allowlist: list[str] = field(default_factory=list)
    qchat_policy: str = "open"
    qchat_allow_from: list[str] = field(default_factory=list)
    home_channel: str | None = None
    bridge_command: list[str] = field(default_factory=lambda: ["node", "bridge/index.mjs"])
    media_max_mb: int = 30
    text_chunk_limit: int = 4000
    inbound_debounce_ms: int = 0
    quick_comment_enabled: bool = False
    quick_comment_index: int = 71
    quick_comment_ttl_ms: int = 30000
    legacy_login: bool = False
    antispam_enabled: bool = True
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

    def resolved_account_id(self) -> str:
        if self.account_id:
            return self.account_id
        if self.credentials is None:
            return ""
        return f"{self.credentials.app_key}:{self.credentials.account}"

    def to_bridge_payload(self) -> dict[str, Any]:
        creds = self.credentials
        return {
            "enabled": self.enabled,
            "credentials": {
                "app_key": creds.app_key if creds else "",
                "account": creds.account if creds else "",
                "token": creds.token if creds else "",
            },
            "account_id": self.resolved_account_id(),
            "debug": self.debug,
            "media_max_mb": self.media_max_mb,
            "text_chunk_limit": self.text_chunk_limit,
            "inbound_debounce_ms": self.inbound_debounce_ms,
            "quick_comment": {
                "enabled": self.quick_comment_enabled,
                "index": self.quick_comment_index,
                "ttl_ms": self.quick_comment_ttl_ms,
            },
            "legacy_login": self.legacy_login,
            "antispam_enabled": self.antispam_enabled,
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


def _get_any(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return None


def _merge_instance_extra(raw: dict[str, Any]) -> dict[str, Any]:
    extra = dict(raw)
    p2p = raw.get("p2p") if isinstance(raw.get("p2p"), dict) else {}
    team = raw.get("team") if isinstance(raw.get("team"), dict) else {}
    qchat = raw.get("qchat") if isinstance(raw.get("qchat"), dict) else {}
    advanced = raw.get("advanced") if isinstance(raw.get("advanced"), dict) else {}

    aliases = {
        "nim_token": _get_any(raw, "nim_token", "nimToken"),
        "app_key": _get_any(raw, "app_key", "appKey"),
        "antispam_enabled": _get_any(raw, "antispam_enabled", "antispamEnabled"),
        "p2p_policy": _get_any(raw, "p2p_policy", "p2pPolicy") or p2p.get("policy"),
        "p2p_allow_from": _get_any(raw, "p2p_allow_from", "p2pAllowFrom") or p2p.get("allowFrom") or p2p.get("allow_from"),
        "group_policy": _get_any(raw, "group_policy", "groupPolicy") or team.get("policy"),
        "group_allowlist": _get_any(raw, "group_allowlist", "groupAllowlist") or team.get("allowFrom") or team.get("allow_from"),
        "qchat_policy": _get_any(raw, "qchat_policy", "qchatPolicy") or qchat.get("policy"),
        "qchat_allow_from": _get_any(raw, "qchat_allow_from", "qchatAllowFrom", "qchat_allowlist", "qchatAllowlist")
        or qchat.get("allowFrom")
        or qchat.get("allow_from"),
        "weblbs_url": _get_any(raw, "weblbs_url", "weblbsUrl") or advanced.get("weblbsUrl") or advanced.get("weblbs_url"),
        "link_web": _get_any(raw, "link_web", "linkWeb") or advanced.get("link_web") or advanced.get("linkWeb"),
        "nos_uploader": _get_any(raw, "nos_uploader", "nosUploader") or advanced.get("nos_uploader") or advanced.get("nosUploader"),
        "nos_downloader_v2": _get_any(raw, "nos_downloader_v2", "nosDownloaderV2")
        or advanced.get("nos_downloader_v2")
        or advanced.get("nosDownloaderV2"),
        "nos_ssl": _get_any(raw, "nos_ssl", "nosSsl") or advanced.get("nosSsl") or advanced.get("nos_ssl"),
        "nos_accelerate": _get_any(raw, "nos_accelerate", "nosAccelerate")
        or advanced.get("nos_accelerate")
        or advanced.get("nosAccelerate"),
        "nos_accelerate_host": _get_any(raw, "nos_accelerate_host", "nosAccelerateHost")
        or advanced.get("nos_accelerate_host")
        or advanced.get("nosAccelerateHost"),
        "bridge_command": _get_any(raw, "bridge_command", "bridgeCommand"),
        "text_chunk_limit": _get_any(raw, "text_chunk_limit", "textChunkLimit"),
        "inbound_debounce_ms": _get_any(raw, "inbound_debounce_ms", "inboundDebounceMs"),
        "quick_comment_enabled": _get_any(raw, "quick_comment_enabled", "quickCommentEnabled"),
        "quick_comment_index": _get_any(raw, "quick_comment_index", "quickCommentIndex"),
        "quick_comment_ttl_ms": _get_any(raw, "quick_comment_ttl_ms", "quickCommentTtlMs"),
        "legacy_login": _get_any(raw, "legacy_login", "legacyLogin"),
        "debug": _get_any(raw, "debug"),
        "home_channel": _get_any(raw, "home_channel", "homeChannel"),
    }
    for key, value in aliases.items():
        if value not in (None, ""):
            extra[key] = value
    return extra


def _as_optional_str(value: Any) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _platform_home_channel(platform: PlatformConfig) -> str | None:
    home_channel = getattr(platform, "home_channel", None)
    chat_id = getattr(home_channel, "chat_id", None)
    return _as_optional_str(chat_id)


def _as_int(value: Any, default: int, min_value: int | None = None) -> int:
    if value in (None, ""):
        return default
    try:
        parsed = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default
    if min_value is not None and parsed < min_value:
        return min_value
    return parsed


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

    account_id = ""
    if credentials is not None:
        account_id = str(extra.get("account_id") or extra.get("accountId") or f"{credentials.app_key}:{credentials.account}")

    return NimResolvedConfig(
        enabled=platform.enabled,
        credentials=credentials,
        account_id=account_id,
        allowed_users=allowed_users,
        allow_all_users=allow_all_users,
        p2p_policy=p2p_policy,
        p2p_allow_from=p2p_allow_from,
        group_policy=str(_pick(extra, env, "group_policy", "NIM_GROUP_POLICY") or "open").strip(),
        group_allowlist=_as_list(_pick(extra, env, "group_allowlist", "NIM_GROUP_ALLOWLIST")),
        qchat_policy=str(_pick(extra, env, "qchat_policy", "NIM_QCHAT_POLICY") or "open").strip(),
        qchat_allow_from=qchat_allow_from,
        home_channel=(
            _platform_home_channel(platform)
            or str(_pick(extra, env, "home_channel", "NIM_HOME_CHANNEL") or "").strip()
            or None
        ),
        bridge_command=_resolve_bridge_command(_pick(extra, env, "bridge_command", "NIM_BRIDGE_COMMAND")),
        media_max_mb=_as_int(_pick(extra, env, "media_max_mb", "NIM_MEDIA_MAX_MB"), 30, 1),
        text_chunk_limit=_as_int(_pick(extra, env, "text_chunk_limit", "NIM_TEXT_CHUNK_LIMIT"), 4000, 1),
        inbound_debounce_ms=_as_int(_pick(extra, env, "inbound_debounce_ms", "NIM_INBOUND_DEBOUNCE_MS"), 0, 0),
        quick_comment_enabled=_as_bool(_pick(extra, env, "quick_comment_enabled", "NIM_QUICK_COMMENT_ENABLED"), default=False),
        quick_comment_index=_as_int(_pick(extra, env, "quick_comment_index", "NIM_QUICK_COMMENT_INDEX"), 71, 1),
        quick_comment_ttl_ms=_as_int(_pick(extra, env, "quick_comment_ttl_ms", "NIM_QUICK_COMMENT_TTL_MS"), 30000, 1000),
        legacy_login=_as_bool(_pick(extra, env, "legacy_login", "NIM_LEGACY_LOGIN"), default=False),
        antispam_enabled=_as_bool(_pick(extra, env, "antispam_enabled", "NIM_ANTISPAM_ENABLED"), default=True),
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


def _instances_from_env(env: dict[str, str]) -> list[dict[str, Any]]:
    raw = env.get("NIM_INSTANCES", "").strip()
    if not raw:
        return []
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise ValueError("NIM_INSTANCES must be a JSON array")
    return [dict(item) for item in parsed if isinstance(item, dict)]


def load_nim_instances(
    platform: PlatformConfig,
    environ: dict[str, str] | None = None,
) -> list[NimResolvedConfig]:
    env = environ or dict(os.environ)
    extra = dict(platform.extra)
    raw_instances = extra.get("instances")
    if raw_instances in (None, ""):
        raw_instances = _instances_from_env(env)

    if not raw_instances:
        return [load_nim_config(platform, env)]
    if not isinstance(raw_instances, list):
        raise ValueError("NIM instances must be a list")
    if len(raw_instances) > 3:
        raise ValueError("NIM instances may have at most 3 entries")

    resolved: list[NimResolvedConfig] = []
    seen: set[str] = set()
    for raw in raw_instances:
        if not isinstance(raw, dict):
            raise ValueError("Each NIM instance must be an object")
        instance_extra = _merge_instance_extra(raw)
        instance_enabled = _as_bool(instance_extra.get("enabled"), default=False)
        instance_platform = PlatformConfig(enabled=platform.enabled and instance_enabled, extra=instance_extra)
        instance = load_nim_config(instance_platform, {})
        account_id = instance.resolved_account_id()
        if account_id:
            if account_id in seen:
                raise ValueError(f"Duplicate NIM instance credentials: {account_id}")
            seen.add(account_id)
        resolved.append(instance)
    return resolved
