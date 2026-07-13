## Context

The bridge already keeps raw inbound SDK messages in `ReplyMessageCache` and exposes normalized `topic_refer` metadata in inbound payloads. This makes cached inbound messages sufficient for a minimal native topic reply implementation without adding history lookup or Hermes-side topic registries.

OpenClaw reference:
- `src/client.ts`: `replyTopicText(...)` creates a text message and calls `nim.V2NIMTopicService.replyTopicMessage(replyMsg, originalMsg, topic, sendParams)`.
- `src/send.ts`: `replyTopicMessageNim(...)` ensures a logged-in client and delegates to `replyTopicText`.

## Goals / Non-Goals

**Goals:**
- Use native NIM topic reply for text replies when the reply target is cached and has valid `topicRefer`.
- Keep long-text chunking behavior for topic replies.
- Keep normal `replyMessage` behavior for non-topic cached messages.
- Preserve antispam send options.

**Non-Goals:**
- Media topic replies.
- Historical lookup for uncached reply targets.
- Topic name lookup or topic context registry.
- Changing Hermes adapter public API beyond existing `reply_to`.

## Decisions

### 1. Topic reply is opportunistic

Decision: use `replyTopicMessage` only when both a valid `topicRefer` and `V2NIMTopicService.replyTopicMessage` are available.

Rationale:
- Some SDK/runtime versions may not expose topic reply service.
- Falling back to existing `replyMessage` preserves compatibility and avoids making topic support a hard dependency.

### 2. Reuse existing reply cache

Decision: derive the topic reference from the cached raw original message.

Rationale:
- The SDK topic reply API requires the original message object and topic reference.
- The cache already stores the original SDK message by server/client id.

### 3. Text-only in this slice

Decision: apply native topic reply only to `send_message` text chunks.

Rationale:
- Current Hermes text reply flow is already implemented and chunked.
- Media topic reply requires separate media message creation and acceptance rules.

## Risks / Trade-offs

- Topic replies only work for messages still present in the in-memory reply cache.
- If SDK topic service is unavailable, a topic message reply falls back to ordinary reply rather than failing hard.
- Multiple chunks become multiple native topic replies, matching current long-text chunk semantics.

## Migration Plan

1. Add OpenSpec delta for topic text reply support.
2. Add bridge helper for native topic reply eligibility.
3. Update `send_message(reply_to=...)` to prefer topic reply when eligible.
4. Add Node tests for eligibility and fallback.
5. Validate Python tests, Node tests, and OpenSpec change.
