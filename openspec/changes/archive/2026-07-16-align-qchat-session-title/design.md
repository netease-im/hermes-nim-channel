## Context

The Node bridge resolves QChat channel information and emits the raw channel name. Both Python adapters currently reuse that raw value as `SessionSource.chat_name`. `openclaw-nim-channel` instead passes the resolved name through `buildConversationLabel("qchat", ...)`, producing `云信·圈组·<displayName>`. Hermes also needs this prefix because its session-title pinning intentionally handles only stable `云信·` labels.

## Goals / Non-Goals

**Goals:**

- Match the reference QChat session-title format and fallback.
- Keep title construction identical in both Python adapters.
- Preserve the unprefixed channel name in agent-visible channel context.
- Make repeated formatting idempotent.

**Non-Goals:**

- Change QChat chat IDs, routing, mention requirements, policies, or replies.
- Change Node bridge channel-info resolution or its JSONL payload.
- Rename existing persisted sessions before another inbound message arrives.

## Decisions

Add a shared Python helper that accepts the resolved channel name plus server/channel IDs. It returns an already-prefixed value unchanged, otherwise prefixes the resolved name or the `serverId:channelId` fallback with `云信·圈组·`.

Each adapter will keep two values during inbound conversion: the raw channel display name for `qchat_context_text`, and the formatted conversation title for `SessionSource.chat_name`. This matches the reference title without leaking presentation labels into the agent prompt.

No Node bridge change is required because it already resolves and transports the raw channel name and target identifiers. The root Hermes adapter continues to invoke the existing title pin scheduler, which will now accept the formatted QChat label.

## Risks / Trade-offs

- [Existing WebUI sessions retain an old title until new activity] -> The next inbound message updates and pins the corrected stable title; no database migration is needed.
- [A channel name already contains the prefix] -> Make the shared helper idempotent.
- [Channel lookup fails] -> Use the same `serverId:channelId` fallback as the reference implementation.

## Migration Plan

Deploy the two Python adapter changes together. Existing QChat chat IDs and history remain unchanged. Rollback restores bare channel titles without data migration.

## Open Questions

None.
