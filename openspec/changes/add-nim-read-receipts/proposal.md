## Why

`openclaw-nim-channel` sends NIM read receipts for online P2P and team messages after inbound processing. The Hermes plugin currently emits messages to Hermes but never acknowledges them to NIM, which leaves senders without read state parity.

## What Changes

- Detect online inbound P2P and team messages in the bridge receive callback
- Send P2P read receipts with `sendP2PMessageReceipt`
- Send team read receipts with `sendTeamMessageReceipts` in bounded batches
- Skip offline, roaming, or history messages
- Add bridge tests for receipt candidate selection and batching

## Capabilities

### Modified Capabilities

- `nim-channel`: send OpenClaw-compatible read receipts for online P2P and team messages

## Impact

- Affected code:
  - `bridge/index.mjs`
  - `bridge/src/config.mjs`
  - `bridge/test/protocol.test.mjs`
- Runtime behavior:
  - Online inbound NIM messages may be acknowledged as read by the bridge after they are emitted to Hermes.
