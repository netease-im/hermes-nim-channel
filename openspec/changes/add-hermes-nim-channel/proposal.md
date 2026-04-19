## Why

Hermes Agent documents new messaging integrations as gateway platform adapters, but NetEase IM's maintained Bot SDK is delivered for Node.js rather than Python. A dedicated NIM channel is needed so Hermes agents can receive and send Yunxin messages without forking the full Hermes codebase first.

## What Changes

- Add a new `nim` channel capability for Hermes-style messaging workflows
- Introduce a Python adapter that enforces Hermes-facing config, routing, allowlists, and mention gating
- Introduce a Node bridge process that logs in with `aiBot: 2`, receives inbound NIM messages, and sends outbound messages through `@yxim/nim-bot`
- Add repository documentation and tests for config parsing, ACL behavior, and bridge protocol framing

## Capabilities

### New Capabilities
- `nim-channel`: Connect Hermes Agent to NetEase IM direct chats and team chats through a bridge-backed platform adapter

### Modified Capabilities

## Impact

- Affected code:
  - `gateway/config.py`
  - `gateway/platforms/base.py`
  - `gateway/platforms/nim.py`
  - `gateway/platforms/nim_bridge.py`
  - `gateway/platforms/nim_protocol.py`
  - `bridge/index.mjs`
  - `bridge/src/*.mjs`
  - `tests/*.py`
- New dependency surface:
  - Python 3.11+ standard library
  - Node.js runtime
  - `@yxim/nim-bot` in the bridge package

