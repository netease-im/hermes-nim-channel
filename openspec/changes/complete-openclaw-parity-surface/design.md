## Context

The remaining OpenClaw implementation depends heavily on its host pipeline. Hermes has a platform adapter API, not the OpenClaw runtime/session/batch dispatcher. This change migrates the transport-level behavior and exposes Hermes-safe metadata or adapter methods where direct host semantics do not exist.

Reference areas:
- `name-resolver.ts`: topic info/name resolution.
- `inbound-batcher.ts`: debounce grouping.
- `quick-comment.ts`: add/remove processing quick comment.
- `send.ts` and `client.ts`: stream send and edit facade.

## Goals / Non-Goals

**Goals:**
- Expose topic names and topic info in inbound metadata when the SDK can resolve them.
- Preserve one Hermes event per inbound NIM message while adding batch metadata.
- Support optional quick comments without blocking the Python event handler on bridge round trips.
- Route outbound metadata-driven stream sends to SDK `sendStreamMessage`/`replyStreamMessage` where available.
- Provide an edit-message facade that sends replacement text.

**Non-Goals:**
- Reimplement OpenClaw's full Agent pipeline, session store, prompt construction, or route registry.
- Combine multiple inbound NIM messages into one Hermes `MessageEvent`.
- Provide true message mutation when the SDK does not support edit.
- QChat streaming or QChat media.

## Decisions

### 1. Batch metadata, not event coalescing

Decision: debounce inbound messages per conversation and emit each message with `batch_id`, `batch_key`, `batch_index`, and `batch_size`.

Rationale:
- Hermes adapter contracts already expect one `MessageEvent` per inbound message.
- Batch metadata gives downstream consumers grouping information without losing message IDs or media attachments.

### 2. Quick comments are bridge-owned with TTL cleanup

Decision: add quick comments before emitting inbound messages and remove them after a configurable TTL.

Rationale:
- Python event handlers cannot safely call back into the same JSONL bridge while the stdout reader is dispatching an event.
- A timed cleanup preserves non-blocking behavior and avoids permanent reactions.

### 3. Streaming is metadata-driven

Decision: `adapter.send(..., metadata={stream: {...}})` routes to the stream send bridge method. Missing SDK stream APIs fall back to ordinary text send.

Rationale:
- Hermes has no dedicated stream-send platform hook in this plugin.
- Metadata routing keeps the public send contract stable.

### 4. Edit facade sends replacement text

Decision: expose edit facade by sending the new text to the target, matching OpenClaw's current fallback behavior.

Rationale:
- OpenClaw comments that NIM does not support true edit in this path.

## Risks / Trade-offs

- Quick-comment TTL cleanup can remove the marker before or after actual Hermes processing completes.
- Inbound debounce introduces optional latency when configured.
- Streaming support is best-effort because SDK availability differs by runtime.

## Migration Plan

1. Add OpenSpec delta for the remaining parity surface.
2. Add config parsing for inbound debounce and quick comments.
3. Add bridge helpers for batching, topic info, quick comments, stream send, and edit facade.
4. Wire adapter bridge methods and metadata routing.
5. Update tests and docs.
6. Run deterministic validation and review.
