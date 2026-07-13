## Why

`openclaw-nim-channel` exposes advanced switches for legacy login mode and SDK antispam send configuration. The Hermes bridge currently always logs in with `aiBot: 2` and sends text without an explicit antispam config, leaving those deployment controls unavailable.

## What Changes

- Add `legacy_login` / `NIM_LEGACY_LOGIN` configuration
- Add `antispam_enabled` / `NIM_ANTISPAM_ENABLED` configuration
- Forward both options through the bridge connect payload
- Use `aiBot: 0` when legacy login is enabled, otherwise `aiBot: 2`
- Include `antispamConfig.antispamEnabled` in text send and reply send params
- Add Python and Node tests

## Capabilities

### Modified Capabilities

- `nim-channel`: support OpenClaw-compatible login mode and antispam send options

## Impact

- Affected code:
  - `adapter.py`
  - `plugin.yaml`
  - `README.md`
  - `hermes_nim_channel/config.py`
  - `bridge/index.mjs`
  - `bridge/src/config.mjs`
  - `bridge/test/protocol.test.mjs`
  - `tests/test_nim_config.py`
- Runtime behavior:
  - Operators can opt into legacy login and disable SDK antispam for outbound text.
