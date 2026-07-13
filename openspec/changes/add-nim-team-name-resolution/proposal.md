## Why

`openclaw-nim-channel` resolves NIM team names through the SDK and uses them as conversation labels. The Hermes adapter already consumes `conversation_name` from the bridge payload, but the bridge currently always sends `null`, so team conversations fall back to raw ids.

## What Changes

- Resolve team/superTeam names in the Node bridge using `V2NIMTeamService.getTeamInfo`
- Cache resolved names in memory
- Populate inbound `conversation_name` for team messages
- Fall back to the target id if lookup fails
- Add Node tests for team name lookup and fallback

## Capabilities

### Modified Capabilities

- `nim-channel`: provide SDK-resolved team names on inbound team messages when available

## Impact

- Affected code:
  - `bridge/src/config.mjs`
  - `bridge/test/protocol.test.mjs`
- Runtime behavior:
  - Inbound team events may include a human-readable `conversation_name` instead of `null`.
