## Context

OpenClaw's QChat client calls `nim.qchatChannel.getChannels({ channelIds: [...] })` and caches channel info. Hermes already stores `conversation_name` and raw metadata from QChat payloads, so the bridge can enrich normalized events before emitting them.

## Goals / Non-Goals

**Goals:**
- Resolve QChat channel name and topic when SDK APIs are available.
- Cache channel info in the bridge process.
- Preserve message delivery when lookup fails.

**Non-Goals:**
- QChat topic reply.
- QChat media support.
- Persistent channel cache.
- Changing QChat allowlist or send policy.

## Decisions

### 1. Resolve in QChat runtime

Decision: enrich QChat messages inside `setupQChatRuntime` before emitting bridge events.

Rationale:
- The runtime has access to the native `nim` object and QChat SDK services.
- The adapter already consumes `conversation_name`.

### 2. Support common SDK response shapes

Decision: accept both array results and `{ datas: [...] }` results from `getChannels`.

Rationale:
- SDK wrappers can differ across versions.
- The enrichment remains best-effort.

## Risks / Trade-offs

- Channel name/topic changes may be stale during a bridge process lifetime.
- If SDK lookup fails, messages still emit with existing/fallback fields.

## Migration Plan

1. Add OpenSpec delta for QChat channel info resolution.
2. Add resolver helper and tests.
3. Enrich QChat message payloads before emit.
4. Validate Node tests, Python tests, and OpenSpec.
