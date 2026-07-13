## Why

`openclaw-nim-channel` supports native topic replies for image, file, audio, and video messages by creating the media SDK message and calling `V2NIMTopicService.replyTopicMessage`. The Hermes plugin currently accepts `reply_to` on media adapter methods, but the bridge media request does not carry or use it, so media sent in response to a topic message is posted as a normal message.

## What Changes

- Pass `reply_to` through the Python bridge `send_media` request
- Detect cached topic reply targets for media sends in the Node bridge
- Use `V2NIMTopicService.replyTopicMessage` for eligible media replies
- Preserve existing ordinary media sending behavior when no eligible topic context is available
- Add tests for media reply parameter propagation and topic media send selection

## Capabilities

### Modified Capabilities

- `nim-channel`: media sends can preserve native topic reply context when replying to cached topic messages

## Impact

- Affected code:
  - `hermes_nim_channel/platforms/nim.py`
  - `hermes_nim_channel/platforms/nim_bridge.py`
  - `bridge/index.mjs`
  - `bridge/src/config.mjs`
  - `bridge/test/protocol.test.mjs`
  - `tests/test_nim_adapter.py`
- Runtime behavior:
  - Media sends with `reply_to` may use native NIM topic replies.
  - Media sends without eligible topic context continue using ordinary media send behavior.
