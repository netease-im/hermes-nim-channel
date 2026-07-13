## Context

The current bridge start path returns a successful connect response after login, but connection state after startup is opaque to Python. OpenClaw records login state and kickout/disconnect callbacks. Hermes has adapter state markers, so the bridge should surface these callbacks as events.

## Goals / Non-Goals

**Goals:**
- Normalize SDK login status callbacks into stable bridge event payloads.
- Mark adapters disconnected on logout, kickout, or disconnected events.
- Keep message event behavior unchanged.

**Non-Goals:**
- Automatic reconnect loops.
- Backoff strategy.
- Re-login token refresh.
- Marking fatal errors for all disconnect reasons.

## Decisions

### 1. Use a dedicated `connection` event

Decision: emit JSONL events with `event: "connection"` and payload `{ status, reason }`.

Rationale:
- Keeps message events unchanged.
- Python adapters can update state without interpreting SDK-specific callback shapes.

### 2. Remove listeners before manual cleanup logout

Decision: bridge cleanup unregisters connection listeners before calling logout/destroy.

Rationale:
- Manual disconnect already updates adapter state.
- Avoids duplicate or misleading logout events during intentional cleanup.

## Risks / Trade-offs

- This slice detects disconnection but does not recover automatically.
- SDK callback shapes may vary; normalization keeps unrecognized login statuses as informational events.

## Migration Plan

1. Add OpenSpec delta for connection status events.
2. Add bridge status normalization helper and tests.
3. Register SDK connection listeners after successful login.
4. Update Python adapter event handling.
5. Validate Python tests, Node tests, and OpenSpec.
