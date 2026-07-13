## Why

The NIM plugin still treats inbound media as plain text or drops attachment context entirely, while `openclaw-nim-channel` already recognizes image, file, audio, and video messages. Hermes needs at least the attachment metadata and local cached files so existing host workflows can inspect or transcribe inbound media.

## What Changes

- Extend inbound bridge payloads to include normalized NIM attachment metadata
- Preserve media placeholder text for non-text NIM messages
- Download and cache inbound media attachments in the Python adapter
- Populate Hermes `MessageEvent.media_urls` and `media_types` for image, file, audio, and video messages

## Capabilities

### New Capabilities

### Modified Capabilities

- `nim-channel`: extend inbound message handling to surface native media attachments to Hermes

## Impact

- Affected code:
  - `bridge/src/config.mjs`
  - `adapter.py`
  - `hermes_nim_channel/inbound_media.py`
  - `hermes_nim_channel/platforms/base.py`
  - `hermes_nim_channel/platforms/nim.py`
  - `bridge/test/protocol.test.mjs`
  - `tests/test_nim_adapter.py`
- Runtime behavior:
  - inbound NIM media now downloads and caches attachment content before dispatch
