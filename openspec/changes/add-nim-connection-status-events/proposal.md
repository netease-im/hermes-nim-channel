## Why

`openclaw-nim-channel` listens for NIM login status, kickout, and disconnected callbacks and updates operational state. The Hermes bridge currently only reports connect success and inbound messages; later SDK disconnects are not surfaced to the Python adapter.

## What Changes

- Register bridge listeners for `onLoginStatus`, `onKickedOffline`, and `onDisconnected`
- Emit JSONL `connection` events with normalized statuses
- Update both Hermes plugin and compatibility adapters when connection events arrive
- Keep automatic reconnect out of scope for this slice
- Add tests for event normalization and adapter state updates

## Capabilities

### Modified Capabilities

- `nim-channel`: surface NIM SDK connection lifecycle changes to the Hermes adapter

## Impact

- Affected code:
  - `adapter.py`
  - `hermes_nim_channel/platforms/nim.py`
  - `bridge/index.mjs`
  - `bridge/src/config.mjs`
  - `bridge/test/protocol.test.mjs`
  - `tests/test_nim_adapter.py`
- Runtime behavior:
  - SDK logout, kickout, and disconnected callbacks can mark the adapter disconnected.
