## Why

Hermes already passes `reply_to` from the platform adapter to the NIM bridge, but the bridge currently ignores it and always calls `sendMessage`. `openclaw-nim-channel` uses the NIM SDK `replyMessage` API when replying to a known original message. This gap prevents Hermes replies from preserving native NIM reply context.

## What Changes

- Cache recent inbound SDK message objects in the Node bridge by server and client message ids
- Resolve `reply_to` against that cache for outbound text sends
- Call `messageService.replyMessage` when the original message is available
- Fall back to normal text sending when `reply_to` is absent
- Add bridge tests for reply cache indexing and lookup behavior

## Capabilities

### Modified Capabilities

- `nim-channel`: support native NIM text replies for recently received P2P and team messages

## Impact

- Affected code:
  - `bridge/index.mjs`
  - `bridge/src/config.mjs`
  - `bridge/test/protocol.test.mjs`
- Runtime behavior:
  - Text sends with a resolvable `reply_to` use the SDK reply API instead of plain send.
