## Why

`openclaw-nim-channel` splits long outbound text into multiple NIM messages using a configurable `textChunkLimit` so oversized replies do not fail at the SDK/server boundary. The Hermes bridge currently sends the whole text as one message.

## What Changes

- Add `text_chunk_limit` / `NIM_TEXT_CHUNK_LIMIT` config support with a default of 4000 characters
- Forward the limit through the bridge connect payload
- Split outbound text by newline/space/forced boundaries before sending
- Apply the same chunking to native text replies
- Add Python and Node tests for config and chunking behavior

## Capabilities

### Modified Capabilities

- `nim-channel`: support OpenClaw-compatible long text chunking for outbound text and text replies

## Impact

- Affected code:
  - `adapter.py`
  - `plugin.yaml`
  - `README.md`
  - `hermes_nim_channel/config.py`
  - `bridge/index.mjs`
  - `bridge/src/config.mjs`
  - `bridge/test/protocol.test.mjs`
  - `tests/test_nim_config.py`
- Runtime behavior:
  - A single Hermes text send may produce multiple NIM SDK text sends when the content exceeds the configured chunk limit.
