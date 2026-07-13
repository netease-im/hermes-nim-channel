## Why

`openclaw-nim-channel` already supports NetEase IM private deployment endpoints for LBS, link, and NOS routing. The Hermes plugin currently always starts the NIM Bot SDK with public-cloud defaults, which blocks use in private or hybrid Yunxin environments.

## What Changes

- Add private deployment endpoint fields to the Python config resolver and plugin env surface
- Forward those fields through the bridge JSONL `connect` payload
- Apply `privateConf` and `V2NIMLoginServiceConfig` when constructing the NIM Bot SDK
- Add tests that verify endpoint parsing and bridge option generation

## Capabilities

### New Capabilities

### Modified Capabilities

- `nim-channel`: allow NIM SDK startup to use operator-supplied private deployment endpoints

## Impact

- Affected code:
  - `adapter.py`
  - `plugin.yaml`
  - `README.md`
  - `hermes_nim_channel/config.py`
  - `bridge/src/config.mjs`
  - `bridge/index.mjs`
  - `bridge/test/protocol.test.mjs`
  - `tests/test_nim_config.py`
- Runtime behavior:
  - NIM bridge startup can pass private LBS/link/NOS values to `@yxim/nim-bot`
