## Context

The bridge already has all inputs required for native topic media replies:
- Raw SDK original messages are stored in `ReplyMessageCache`.
- `resolveTopicReplyContext` validates `topicRefer` and keeps the SDK topic service receiver.
- `createMediaMessage` creates image, file, audio, and video SDK messages.

OpenClaw reference:
- `src/media.ts`: `replyTopicImageNim`, `replyTopicFileNim`, `replyTopicAudioNim`, and `replyTopicVideoNim`.
- `src/client.ts`: `replyTopicImage`, `replyTopicFile`, `replyTopicAudio`, and `replyTopicVideo` all call `nim.V2NIMTopicService.replyTopicMessage`.

## Goals / Non-Goals

**Goals:**
- Preserve native topic context for media sends when `reply_to` points to a cached topic message.
- Support image, file, audio, and video media kinds using the existing media message creator.
- Keep existing ordinary media send behavior when no cached eligible topic context exists.

**Non-Goals:**
- Normal non-topic media replies with `replyMessage`.
- QChat media sending or QChat media replies.
- Historical lookup for uncached reply targets.
- Caption/topic bundling changes.

## Decisions

### 1. Topic media reply is opportunistic

Decision: if `reply_to` is present but the reply target is missing, non-topic, or the topic service is unavailable, send the media as an ordinary media message.

Rationale:
- This preserves prior behavior where media `reply_to` was accepted by adapter signatures but ignored by the bridge.
- Full non-topic media reply semantics can be addressed separately.

### 2. Reuse topic text reply helper shape

Decision: add a generic media reply sender helper near the existing topic reply context helpers.

Rationale:
- Keeps SDK receiver binding safeguards in one place.
- Allows small tests without spawning the bridge process.

## Risks / Trade-offs

- Missing cached topic context still produces an ordinary media send rather than a hard error.
- No full JSONL process test is added; helper tests and adapter bridge-request tests cover the routing decision.

## Migration Plan

1. Add OpenSpec delta for topic media replies.
2. Pass `reply_to` from adapter media sends to the bridge.
3. Use `replyTopicMessage` for eligible media messages in the Node bridge.
4. Add Python and Node tests.
5. Validate Python tests, Node tests, and OpenSpec change.
