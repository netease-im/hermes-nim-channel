## Why

`openclaw-nim-channel` enriches QChat inbound messages with channel information fetched from the SDK. The Hermes bridge currently only uses `channelName` when it is already present on the message, so many QChat events arrive with no human-readable conversation name or topic context.

## What Changes

- Add a QChat channel info resolver with process-local cache
- Fetch channel info through `nim.qchatChannel.getChannels`
- Enrich inbound QChat payloads with `conversation_name` and `channel_topic`
- Keep lookup failures non-fatal
- Add Node tests for QChat channel info normalization and fallback

## Capabilities

### Modified Capabilities

- `nim-channel`: enrich inbound QChat messages with SDK-resolved channel name/topic when available

## Impact

- Affected code:
  - `bridge/index.mjs`
  - `bridge/src/qchat.mjs`
  - `bridge/test/qchat.test.mjs`
- Runtime behavior:
  - QChat inbound events may include a resolved channel name and topic metadata.
