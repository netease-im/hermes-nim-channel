## Context

Hermes stores `payload.conversation_name` as the `SessionSource.chat_name`. OpenClaw resolves team labels through `V2NIMTeamService.getTeamInfo(teamId, teamType)`, using team type `1` for normal team and `2` for super team.

## Goals / Non-Goals

**Goals:**
- Resolve team and superTeam names for inbound message payloads.
- Keep lookup failures non-fatal.
- Avoid repeated SDK lookups for the same team id.

**Non-Goals:**
- Topic name resolution.
- QChat channel name changes.
- Persistent name cache.
- Sender nickname enrichment beyond existing SDK fields.

## Decisions

### 1. Resolve in the bridge

Decision: perform name lookup in `toInboundMessage` because the bridge has the SDK instance.

Rationale:
- Python does not have direct access to NIM SDK services.
- The adapter already has a `conversation_name` field in its payload contract.

### 2. Use bounded process-local cache

Decision: cache team name lookups in module scope for the bridge process lifetime.

Rationale:
- Team names are stable enough for a process-local cache.
- This avoids adding config or persistence complexity.

## Risks / Trade-offs

- Team name changes during bridge lifetime may not be reflected immediately.
- Failed lookups fall back to ids, preserving delivery over display enrichment.

## Migration Plan

1. Add OpenSpec delta for team name resolution.
2. Add bridge helper and tests.
3. Populate `conversation_name` for team/superTeam inbound payloads.
4. Validate Node tests, Python tests, and OpenSpec.
