## Why

`openclaw-nim-channel` already transcribes inbound audio messages through the NIM SDK before handing them to the agent pipeline. The Hermes NIM plugin currently preserves audio attachments but does not turn voice messages into text, so downstream Hermes workflows cannot treat voice notes as first-class prompt input.

## What Changes

- Transcribe inbound NIM audio messages in the bridge before emitting Hermes events
- Preserve the original audio attachment metadata alongside the transcribed text
- Fall back to the existing audio placeholder text when transcription fails

## Capabilities

### New Capabilities

### Modified Capabilities

- `nim-channel`: extend inbound audio handling to include SDK-backed voice-to-text conversion

## Impact

- Affected code:
  - `bridge/index.mjs`
  - `bridge/src/config.mjs`
  - `bridge/test/protocol.test.mjs`
  - `hermes_nim_channel/inbound_media.py`
- Runtime behavior:
  - inbound audio messages are converted to text before dispatch when the SDK transcription call succeeds

