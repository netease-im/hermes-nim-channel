## Context

Hermes delivers generated media through adapter-native methods such as `send_image_file`, `send_document`, `send_voice`, and `send_video`. The current NIM plugin does not override those methods, so Hermes falls back to warning text instead of delivering attachments. The OpenClaw reference implementation already knows how to create NIM image/file/audio/video messages, but it receives more structured metadata from its host than Hermes does.

## Goals / Non-Goals

**Goals:**
- Add Hermes-native outbound media support for image, file, audio, and video
- Reuse the existing Python adapter + Node bridge split
- Keep text captions visible even when NIM media messages do not support native caption fields
- Infer required audio/video metadata locally instead of changing Hermes host APIs

**Non-Goals:**
- Inbound media parsing improvements
- QChat media
- Topic/thread media replies
- Streaming or chunked media batching

## Decisions

### 1. Extend the bridge with a dedicated `send_media` request

Decision: add a new bridge request for media instead of overloading `send_message`.

Rationale:
- The payload shape differs materially from text send.
- Media sends need per-kind handling and metadata inference.
- The protocol stays explicit and easier to test.

### 2. Infer audio/video metadata inside the Node bridge

Decision: use `ffprobe` in the bridge to extract duration and video dimensions when the SDK requires them.

Rationale:
- Hermes adapter methods only receive a local file path plus optional caption.
- The bridge already owns all SDK-specific message creation details.
- `ffprobe` is available locally and keeps metadata inference close to the actual media send.

Alternative considered:
- Infer metadata in Python: rejected because the SDK-facing argument contract still lives in Node.

### 3. Follow OpenClaw's media-then-text caption behavior

Decision: when Hermes passes caption text with a media send, send the media first and then a text message.

Rationale:
- This matches the current OpenClaw NIM outbound behavior.
- It avoids pretending NIM has caption semantics when our current bridge API does not.
- It preserves user-visible text instead of dropping it.

## Risks / Trade-offs

- `ffprobe` missing or failing -> surface a clear send error for audio/video instead of silently sending the wrong type
- Caption as separate text message -> behavior differs from platforms with native media captions, but remains explicit and lossless
- More bridge methods -> acceptable because the protocol remains small and well-scoped

## Migration Plan

1. Add a new OpenSpec delta for outbound media support.
2. Extend bridge media creation and metadata inference.
3. Override Hermes adapter native media methods.
4. Add Python and Node tests for the new request path.
5. Validate specs and tests before continuing to the next capability slice.

## Open Questions

- Whether later parity work should convert image/file sends to include a richer outbound text/media batching contract
- Whether future thread/topic support should share the same media helper or use separate bridge methods
