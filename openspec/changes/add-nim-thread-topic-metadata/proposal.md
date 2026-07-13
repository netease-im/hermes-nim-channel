## Why

`openclaw-nim-channel` preserves NIM `threadReply` and `topicRefer` context on inbound messages so later reply flows can use native thread/topic information. The Hermes bridge currently keeps the raw SDK message, but the adapter metadata does not expose these fields in a stable shape.

## What Changes

- Normalize inbound `topicRefer` into bridge payload fields
- Preserve inbound `threadReply` in bridge payload fields
- Forward both fields into Hermes message metadata
- Add tests for valid and invalid topic/thread context

## Capabilities

### Modified Capabilities

- `nim-channel`: expose NIM thread/topic context metadata on inbound messages

## Impact

- Affected code:
  - `adapter.py`
  - `bridge/src/config.mjs`
  - `bridge/test/protocol.test.mjs`
  - `tests/test_adapter.py` if available
- Runtime behavior:
  - Inbound message metadata may include `thread_reply` and `topic_refer`.
