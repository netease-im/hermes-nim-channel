## Why

Most direct NIM transport capabilities from `openclaw-nim-channel` have been migrated in smaller slices. The remaining reference features are mostly operational and host-integration surfaces: topic info/name enrichment, inbound batching metadata, processing quick comments, streaming sends, and edit-message facade behavior.

## What Changes

- Resolve and expose topic info/name metadata for inbound topic messages
- Add configurable inbound debounce batching while preserving one emitted Hermes event per NIM message
- Add optional quick-comment processing markers in the bridge with timed cleanup
- Add stream-send bridge support and adapter routing through send metadata
- Add edit-message facade support that follows OpenClaw behavior by sending replacement text

## Capabilities

### Modified Capabilities

- `nim-channel`: complete the remaining directly portable OpenClaw NIM parity surface in the Hermes plugin architecture

## Impact

- Affected code:
  - `adapter.py`
  - `hermes_nim_channel/config.py`
  - `hermes_nim_channel/platforms/nim.py`
  - `hermes_nim_channel/platforms/nim_bridge.py`
  - `bridge/index.mjs`
  - `bridge/src/config.mjs`
  - tests and README/plugin configuration
- Runtime behavior:
  - Inbound events may include topic display metadata and batch metadata.
  - Optional quick comments may be added and removed by the bridge.
  - Outbound sends can use streaming when metadata requests it.
  - Edit facade sends replacement text instead of mutating prior messages.
