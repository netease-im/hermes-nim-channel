## Why

`openclaw-nim-channel` sends replies inside native NIM topics by calling `V2NIMTopicService.replyTopicMessage` when the original SDK message carries `topicRefer`. The Hermes bridge currently replies to cached messages with `V2NIMMessageService.replyMessage`, which loses native topic threading for topic messages.

## What Changes

- Detect cached reply targets that include a valid SDK `topicRefer`
- Send text reply chunks through `V2NIMTopicService.replyTopicMessage` when the SDK service is available
- Preserve the existing `replyMessage` path for non-topic messages and SDKs without topic reply support
- Add tests for topic-reply eligibility and fallback behavior

## Capabilities

### Modified Capabilities

- `nim-channel`: outbound text replies can use native NIM topic replies when the cached original message has topic context

## Impact

- Affected code:
  - `bridge/index.mjs`
  - `bridge/src/config.mjs`
  - `bridge/test/protocol.test.mjs`
- Runtime behavior:
  - `send_message` with `reply_to` may call `V2NIMTopicService.replyTopicMessage` instead of `replyMessage` for topic messages.
  - Existing non-topic replies and unknown `reply_to` errors remain unchanged.
