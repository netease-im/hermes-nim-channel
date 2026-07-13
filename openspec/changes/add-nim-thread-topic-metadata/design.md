## Context

The existing text reply support can reply to cached raw SDK messages by `reply_to`, but full topic reply requires additional context and SDK calls. This slice adds only the inbound metadata foundation needed for later topic/thread work.

## Goals / Non-Goals

**Goals:**
- Preserve `threadReply` when the SDK provides it.
- Normalize valid `topicRefer` values with numeric `topicId` and `createTime`.
- Keep invalid topic references out of metadata.

**Non-Goals:**
- Native topic reply sending.
- Topic name lookup.
- Historical message lookup by thread reference.
- Session/thread restructuring in Hermes.

## Decisions

### 1. Keep metadata JSON-safe

Decision: expose `topic_refer` as a small plain object and `thread_reply` as the SDK-provided value.

Rationale:
- Hermes metadata must be serializable and inspectable.
- The raw SDK object remains available in `raw` for debugging, but stable metadata should not require parsing `raw`.

### 2. Validate topic refer shape

Decision: only emit `topic_refer` when `topicId`, `conversationId`, and `createTime` are usable.

Rationale:
- Avoids downstream code treating partial topic references as actionable.

## Risks / Trade-offs

- `thread_reply` remains SDK-shaped because the SDK can provide different reference fields; full normalization is deferred to the topic reply slice.
- This does not change outbound behavior.

## Migration Plan

1. Add OpenSpec delta for thread/topic metadata.
2. Add bridge normalization helper and tests.
3. Forward fields through adapter metadata.
4. Validate Python tests, Node tests, and OpenSpec.
