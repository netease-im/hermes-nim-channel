## Why

Hermes currently stores a bare QChat channel name as the session title, while `openclaw-nim-channel` labels the same conversation as `云信·圈组·<频道名>`. The bare value is also skipped by Hermes-specific title pinning, so the WebUI can replace it with an unrelated generated title.

## What Changes

- Build QChat session titles with the reference format `云信·圈组·<频道名>`.
- Fall back to `云信·圈组·<serverId>:<channelId>` when the SDK cannot resolve a channel name.
- Keep the raw channel name in the agent-visible QChat context instead of inserting the session-title prefix there.
- Apply the behavior to both the registered root plugin adapter and the compatibility adapter.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `nim-channel`: align QChat session titles and fallback labels with `openclaw-nim-channel`.

## Impact

- Affected Python routing helpers and adapters: `hermes_nim_channel/targets.py`, `adapter.py`, and `hermes_nim_channel/platforms/nim.py`.
- Affected tests: target helper and inbound QChat adapter coverage.
- No protocol, SDK bridge, dependency, or chat ID change.
