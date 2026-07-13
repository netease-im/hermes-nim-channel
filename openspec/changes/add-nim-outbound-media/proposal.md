## Why

The current Hermes NIM plugin can only send text, while `openclaw-nim-channel` already supports native image, file, audio, and video delivery. Outbound media is the smallest high-value parity slice that materially improves usefulness without pulling in QChat or streaming complexity first.

## What Changes

- Add native outbound media delivery for NIM images, files, audio, and video
- Extend the Python adapter and Node bridge contract beyond text-only send
- Infer audio/video metadata needed by the NIM SDK from local files during bridge sends
- Preserve optional Hermes captions by following the reference plugin behavior: send the media first, then a trailing text message when caption text is present

## Capabilities

### New Capabilities

### Modified Capabilities

- `nim-channel`: extend outbound delivery requirements from text-only send to native media attachments

## Impact

- Affected code:
  - `adapter.py`
  - `hermes_nim_channel/platforms/nim_bridge.py`
  - `hermes_nim_channel/platforms/nim.py`
  - `bridge/index.mjs`
  - `bridge/src/config.mjs`
  - `bridge/test/protocol.test.mjs`
  - `tests/test_nim_adapter.py`
- Runtime dependencies:
  - local `ffprobe` for audio/video metadata extraction
- Behavioral scope:
  - outbound only for this slice
