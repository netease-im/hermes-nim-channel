## Context

OpenClaw's splitter prefers newline boundaries, then spaces, and finally hard cuts at the configured maximum length. Its default limit is 4000 characters. Hermes already sends all text through the Node bridge, so the bridge can apply chunking uniformly to plain text and text replies.

## Goals / Non-Goals

**Goals:**
- Preserve existing behavior for text shorter than the limit.
- Send long text chunks sequentially.
- Support the same chunking for cached native text replies.
- Return chunk metadata so callers can inspect multi-message sends.

**Non-Goals:**
- Streaming delivery.
- QChat text chunking.
- Media caption chunking beyond the existing caption-as-text path.
- Retrying partially failed chunk sequences.

## Decisions

### 1. Chunk in the bridge

Decision: parse `textChunkLimit` in bridge config and split text before creating SDK text messages.

Rationale:
- The bridge owns SDK message creation.
- Reply chunking needs access to the cached original SDK message.
- Python remains host orchestration and does not need SDK message-size knowledge.

### 2. Stop on first chunk failure

Decision: send chunks sequentially and let the first SDK failure abort the bridge request.

Rationale:
- Continuing after a failed chunk would produce confusing partial conversations.
- Existing bridge send semantics already surface SDK failures as request errors.

## Risks / Trade-offs

- If a multi-chunk send fails after earlier chunks succeeded, the caller receives an error but prior chunks may already be visible in NIM.
- Character-count chunking follows OpenClaw behavior and does not attempt byte-level SDK payload sizing.

## Migration Plan

1. Add OpenSpec delta for text chunking.
2. Add Python config/env/plugin docs for chunk limit.
3. Add bridge chunk helper and tests.
4. Apply chunking to plain text and reply text send paths.
5. Validate Python tests, Node tests, and OpenSpec.
