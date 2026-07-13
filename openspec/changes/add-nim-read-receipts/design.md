## Context

OpenClaw only sends read receipts for messages classified as online by the SDK and skips sync sources such as offline, roaming, or history. P2P receipts are sent per message; team receipts are sent in batches of up to 50 messages.

## Goals / Non-Goals

**Goals:**
- Match OpenClaw's online-message receipt behavior.
- Keep receipt failures non-fatal for inbound message delivery.
- Avoid sending receipts for QChat messages or historical sync messages.

**Non-Goals:**
- Surfacing receipt status to Hermes.
- Retrying failed receipts.
- Changing inbound message filtering in Python.

## Decisions

### 1. Receipt work stays in the bridge

Decision: handle receipt sending in the Node bridge receive callback immediately after emitting inbound messages.

Rationale:
- The SDK receipt APIs are Node-only.
- Hermes does not expose a read-receipt lifecycle hook for this plugin.

### 2. Extract deterministic helpers

Decision: add helper functions that classify receipt candidates and chunk team receipt batches.

Rationale:
- Unit tests can verify source/session semantics without starting the SDK.
- The bridge callback stays focused on SDK interaction and error isolation.

## Risks / Trade-offs

- SDK source enum values must match the reference implementation; this slice follows OpenClaw's `messageSource === 1` online check.
- Receipt API failures are logged but do not block message delivery.

## Migration Plan

1. Add OpenSpec delta for read receipts.
2. Add bridge helper tests.
3. Send P2P receipts per online P2P message.
4. Send team receipts in batches of 50 online team/superTeam messages.
5. Validate Node tests, Python tests, and OpenSpec.
