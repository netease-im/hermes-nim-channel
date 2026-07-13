# Hermes NIM Channel

`hermes-nim-channel` is a standalone Hermes Agent platform plugin project for NetEase IM (NIM, 网易云信). Its purpose is to let `hermes-agent` send and receive messages through the official NIM Bot SDK.

This repository uses `openclaw-nim-channel` as its NIM behavior baseline:

- Hermes host: `https://github.com/NousResearch/hermes-agent`
- Reference NIM channel: `https://github.com/openclaw/openclaw`
- Local reference implementation: `/Users/xumengxiang/Documents/00.NetEase/05.IM/openclaw-nim-channel`

## Project Direction

Hermes recommends third-party messaging integrations through the plugin path (`plugin.yaml` + `adapter.py`), while the proven NIM implementation already exists as the OpenClaw channel plugin. This repository is therefore initialized as:

- a Hermes platform plugin at the repository root
- a Python control layer for Hermes-facing adapter logic
- a Node.js bridge for `@yxim/nim-bot`
- an implementation plan that tracks `openclaw-nim-channel` capability parity where Hermes exposes equivalent host hooks

## Layout

```text
plugin.yaml
adapter.py
__init__.py
hermes_nim_channel/
  config.py
  platforms/
    base.py
    nim.py
    nim_bridge.py
    nim_protocol.py
bridge/
  index.mjs
  package.json
tests/
openspec/
```

## Capability Baseline

The long-term functional target is to align with the already implemented capabilities in `openclaw-nim-channel`, including:

- P2P, team, and QChat inbound/outbound flows
- media delivery
- voice-to-text handling
- long-message chunking and streaming-friendly delivery
- private deployment endpoints
- reconnect and operational hardening

The current repository already contains the bridge-backed Hermes prototype for credential resolution, inbound P2P/team handling, mention-gated team routing, and outbound text send. Further parity work should be implemented against this reinitialized plugin structure instead of reviving the old `gateway/` namespace layout.

## Configuration

The adapter resolves credentials in this order:

1. `platform.extra.nim_token` or `NIM_CREDENTIALS`, using `appKey|accid|token`
2. `platform.extra.app_key` + `account` + `token`
3. `NIM_APP_KEY` + `NIM_ACCOUNT` + `NIM_TOKEN`

Additional controls:

- `NIM_ALLOWED_USERS`: comma-separated DM allowlist
- `NIM_ALLOW_ALL_USERS`: allow all DMs when `true`
- `NIM_GROUP_POLICY`: `open`, `allowlist`, or `disabled`
- `NIM_GROUP_ALLOWLIST`: comma-separated team IDs
- `NIM_HOME_CHANNEL`: default NIM target for proactive sends
- `NIM_BRIDGE_COMMAND`: override bridge command; default points to the bundled `bridge/index.mjs`

## Local Verification

Python:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

Node:

```bash
node --test bridge/test/*.test.mjs
```

OpenSpec:

```bash
OPENSPEC_TELEMETRY=0 openspec validate add-hermes-nim-channel --type change --no-interactive
```

## SDD Workflow

This repository now standardizes on the global `openspec` CLI for spec-driven development.

- Project schema config: `openspec/config.yaml`
- Workflow wrapper: `./scripts/sdd`
- Usage guide: `docs/SDD_WORKFLOW.md`

Typical flow:

```bash
./scripts/sdd new <change-name>
./scripts/sdd instructions proposal <change-name>
./scripts/sdd instructions specs <change-name>
./scripts/sdd instructions design <change-name>
./scripts/sdd instructions tasks <change-name>
./scripts/sdd validate <change-name>
```
