## Context

Hermes host workflows expect adapters to populate `MessageEvent.media_urls` and `media_types` with local cached files so downstream tools can inspect images, documents, audio, and video. The current NIM bridge emits only basic text/message-type fields, which is enough for text routing but not for attachment-aware behavior. The OpenClaw reference implementation already classifies inbound media and preserves placeholder text plus attachment URLs.

## Goals / Non-Goals

**Goals:**
- Preserve normalized attachment metadata in bridge events
- Cache inbound media locally before dispatching the event
- Surface image, file, audio, and video attachments through Hermes-native event fields
- Keep the first implementation compatible with the current bridge-backed architecture

**Non-Goals:**
- QChat inbound media
- Voice-to-text conversion in this slice
- Reply/thread reconstruction for media messages
- Attachment deduplication or persistent download caching

## Decisions

### 1. Normalize attachments in the bridge payload

Decision: add a simplified `attachment` object to inbound bridge messages and synthesize placeholder text for media-only NIM messages.

Rationale:
- The Python adapter should not parse raw SDK objects ad hoc.
- The protocol becomes explicit and testable.
- Placeholder text keeps behavior readable when no body text exists.

### 2. Cache inbound media inside the Python adapter

Decision: download attachments in the adapter layer and convert them into local files before dispatch.

Rationale:
- Hermes host consumers want local paths, not remote NOS URLs.
- The bridge should stay focused on SDK interaction instead of local cache layout.
- The plugin can use Hermes core cache helpers in production and stdlib temp files in local tests.

### 3. Keep attachment loading injectable for local tests

Decision: allow the local test adapter to override attachment loading with a fake loader.

Rationale:
- Tests stay deterministic and do not hit real network resources.
- The production flow remains unchanged.

## Risks / Trade-offs

- Attachment URLs may expire or fail to download -> surface the message without media paths instead of crashing dispatch
- Downloading in the adapter adds latency -> acceptable for the first slice because correctness matters more than concurrency tuning
- Local temp caching in the compatibility adapter differs from Hermes production cache layout -> acceptable because only the production adapter controls real host behavior

## Migration Plan

1. Add an OpenSpec delta for inbound media behavior.
2. Extend bridge inbound payload normalization.
3. Add shared inbound-media helpers for parsing and local caching.
4. Populate `media_urls` / `media_types` in both production and local adapters.
5. Validate with Python tests, Node tests, and OpenSpec.

## Open Questions

- Whether a later slice should add voice-to-text before dispatch for audio messages
- Whether expired attachment URLs need bridge-side prefetching instead of adapter-side fetch
