## Context

Earlier P2P policy migration added explicit policy controls for the root plugin adapter and bridge friend auto-accept. The compatibility adapter retained the older direct allowlist logic, creating inconsistent behavior for the same resolved config.

## Goals / Non-Goals

**Goals:**
- Use the same direct sender policy logic in both Python adapter entrypoints.
- Preserve legacy `allowed_users` fallback for unknown policy values.

**Non-Goals:**
- Changing bridge P2P policy parsing.
- Changing friend auto-accept behavior.

## Decisions

### 1. Mirror root adapter logic

Decision: copy the root adapter's `_is_allowed_direct_sender` policy order into the compatibility adapter.

Rationale:
- Keeps behavior deterministic across entrypoints.
- Avoids introducing a shared helper refactor in this small fix slice.

## Risks / Trade-offs

- Compatibility users with explicit `p2p_policy=disabled` will now block DMs as configured; this is intended policy alignment.

## Migration Plan

1. Add OpenSpec delta.
2. Update compatibility adapter direct sender filtering.
3. Add Python tests.
4. Validate Python tests, Node tests, and OpenSpec.
