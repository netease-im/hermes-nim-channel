## Why

This repository needs to be re-centered as a Hermes Agent platform plugin, not a leftover prototype. Hermes now documents a plugin-based platform path, and there is already a working NIM channel in `openclaw-nim-channel` that should define the feature baseline for this project.

## What Changes

- Reinitialize the repository around the Hermes plugin entrypoint shape
- Keep the Python adapter plus Node bridge split for NIM SDK access
- Declare `openclaw-nim-channel` as the NIM capability baseline
- Preserve and verify the existing prototype coverage for config parsing, ACL behavior, and bridge protocol framing

## Capabilities

### New Capabilities
- `nim-channel`: Connect Hermes Agent to NetEase IM direct chats and team chats through a bridge-backed platform adapter

### Modified Capabilities

## Impact

- Affected code:
  - `plugin.yaml`
  - `adapter.py`
  - `__init__.py`
  - `hermes_nim_channel/config.py`
  - `hermes_nim_channel/platforms/base.py`
  - `hermes_nim_channel/platforms/nim.py`
  - `hermes_nim_channel/platforms/nim_bridge.py`
  - `hermes_nim_channel/platforms/nim_protocol.py`
  - `bridge/index.mjs`
  - `bridge/src/*.mjs`
  - `tests/*.py`
- New dependency surface:
  - Python 3.11+ standard library
  - Node.js runtime
  - `@yxim/nim-bot` in the bridge package
