## Context

The Hermes adapter forwards `reply_to` through the bridge protocol today. The value is derived from inbound `message_id`, which maps to the SDK server id when available and otherwise the client id. The bridge needs access to the original SDK message object because `replyMessage` requires the original message, not just an id.

## Goals / Non-Goals

**Goals:**
- Use native NIM `replyMessage` for text replies when the original message is known.
- Preserve existing plain text behavior when `reply_to` is absent.
- Fail explicitly when a caller requests a reply to an unknown message id.
- Keep cache memory bounded.

**Non-Goals:**
- Topic/thread reply support.
- Media reply support.
- Fetching historical messages by id when the original message is no longer cached.
- Persisting reply cache across bridge restarts.

## Decisions

### 1. Cache recent inbound SDK messages in the bridge

Decision: maintain an in-memory reply cache keyed by both `messageServerId` and `messageClientId`, with a bounded maximum size.

Rationale:
- The bridge receives raw SDK messages before converting them to Hermes payloads.
- `replyMessage` requires the original SDK message object.
- Bounded in-memory cache avoids persistence and history-fetch complexity for this slice.

### 2. Unknown reply target is an error

Decision: if `reply_to` is provided but not found in cache, return a bridge error instead of silently sending a plain message.

Rationale:
- Silent fallback would misrepresent user intent and make reply loss hard to detect.
- Callers can retry without `reply_to` if plain sending is acceptable.

## Risks / Trade-offs

- Replies are only supported for messages observed since bridge startup and still present in the bounded cache.
- The cache stores raw SDK message objects in memory; bounding by message count limits growth.

## Migration Plan

1. Add OpenSpec delta for text reply support.
2. Add reply cache helper tests.
3. Cache inbound SDK messages during receive handling.
4. Route `send_message` with `reply_to` through `replyMessage`.
5. Validate Python tests, Node tests, and OpenSpec.
