# Hermes NIM Channel

Hermes NIM Channel is a spec-driven prototype for integrating NetEase IM (NIM, 网易云信) into Hermes Agent as a new messaging platform.

The repository follows a two-layer design:

- `gateway/platforms/nim.py`: a Hermes-compatible Python adapter that handles config, ACLs, mention gating, and bridge lifecycle
- `bridge/`: a Node.js process that talks to `@yxim/nim-bot`, because the official Bot SDK is maintained for Node rather than Python

## Why This Shape

Hermes documents new messaging platforms as gateway platform adapters, while the reference NIM implementation available inside NetEase is TypeScript-based. Splitting the implementation keeps Hermes-facing behavior in Python and NIM protocol details in a dedicated bridge process.

## Layout

```text
gateway/
  config.py
  platforms/
    base.py
    nim.py
    nim_bridge.py
    nim_protocol.py
bridge/
  index.mjs
  package.json
  src/
tests/
openspec/
```

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
- `NIM_HOME_CHANNEL`: default team target for proactive sends
- `NIM_BRIDGE_COMMAND`: override bridge command, defaults to `node bridge/index.mjs`

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

