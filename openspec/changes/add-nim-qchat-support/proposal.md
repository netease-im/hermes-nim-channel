## Why

The current Hermes NIM plugin still stops at P2P/team routing, while `openclaw-nim-channel` already implements QChat as a first-class NIM surface. Hermes needs the same QChat capability block so the plugin can receive mentioned channel messages, auto-handle server invites, and send outbound text to QChat channels without waiting for later thread/topic parity.

## What Changes

- Add QChat configuration, subscription, and invite handling to the NIM bridge
- Extend the Python adapter to recognize QChat targets and inbound QChat message events
- Route outbound QChat text through the bridge using a dedicated QChat send path
- Keep the Hermes-facing target shape explicit as `qchat:<serverId>:<channelId>` instead of overloading P2P/team syntax

## Capabilities

### New Capabilities

- `nim-qchat`: QChat inbound/outbound text routing with subscription and invite handling

### Modified Capabilities

- `nim-channel`: extend the current NIM plugin surface to include QChat alongside P2P and team flows

## Impact

- Affected code:
  - `adapter.py`
  - `plugin.yaml`
  - `hermes_nim_channel/config.py`
  - `hermes_nim_channel/platforms/nim.py`
  - `hermes_nim_channel/platforms/nim_bridge.py`
  - `bridge/index.mjs`
  - `bridge/src/config.mjs`
  - `bridge/test/protocol.test.mjs`
  - `tests/test_nim_adapter.py`
  - `tests/test_nim_config.py`
- Runtime behavior:
  - QChat is subscribed after IM login and filtered by QChat policy controls
  - QChat invite auto-accept behavior follows the configured policy
