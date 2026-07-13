## Why

The root Hermes plugin adapter already honors explicit `p2p_policy` and `p2p_allow_from`, but the compatibility adapter under `hermes_nim_channel/platforms/nim.py` still uses only legacy `allowed_users` fields. This leaves local tests and compatibility imports with different direct-message access behavior.

## What Changes

- Align compatibility adapter direct-message filtering with the root plugin adapter
- Add tests for disabled and allowlist P2P policy behavior

## Capabilities

### Modified Capabilities

- `nim-channel`: consistently apply P2P policy across both adapter entrypoints

## Impact

- Affected code:
  - `hermes_nim_channel/platforms/nim.py`
  - `tests/test_nim_adapter.py`
- Runtime behavior:
  - Compatibility adapter respects `p2p_policy=disabled|open|allowlist`.
