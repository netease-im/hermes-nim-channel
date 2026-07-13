## Context

Hermes receives NIM messages from the Node bridge as normalized events. For audio messages, the most useful behavior is to hand Hermes a transcript instead of a raw voice-only payload while still preserving the attachment metadata for downstream tools. The OpenClaw reference performs this work in the inbound message pipeline and uses the NIM SDK's `voiceToText` API directly.

## Goals / Non-Goals

**Goals:**
- Transcribe inbound NIM audio messages before they are emitted to Hermes
- Keep the bridge as the only component that talks to the NIM SDK
- Preserve the original audio attachment metadata even when transcription succeeds
- Keep the fallback path explicit when transcription fails or returns empty text

**Non-Goals:**
- Outbound voice synthesis
- Hermes host API changes for audio messages
- Topic/thread-specific voice transcription behavior

## Decisions

### 1. Transcribe audio inside the Node bridge

Decision: perform voice-to-text in the bridge when the SDK receives an audio message.

Rationale:
- The bridge already owns the NIM SDK runtime and can call `voiceToText` without extra IPC.
- This matches the OpenClaw model where audio becomes text before the agent pipeline sees it.
- It avoids introducing a second request path from Python back into the bridge during event dispatch.

### 2. Preserve attachment metadata on the emitted event

Decision: keep the normalized audio attachment in the payload and emit the transcript as the event text when transcription succeeds.

Rationale:
- Hermes consumers can still inspect or store the audio path and attachment metadata.
- The event remains compatible with non-audio tooling because the body text is still a plain string.

### 3. Fall back to placeholder text on failure

Decision: if transcription fails or returns empty text, emit the existing audio placeholder text.

Rationale:
- The host still receives a readable message body.
- Failures do not block the rest of the inbound dispatch path.

## Risks / Trade-offs

- SDK transcription latency adds a small delay to audio delivery -> acceptable for parity with OpenClaw behavior
- Transcription failure can reduce message usefulness -> mitigated by retaining the audio placeholder
- Bridge-side transcription couples event formatting to SDK availability -> acceptable because the bridge already depends on the SDK at connect time

## Migration Plan

1. Extend the bridge payload to preserve audio attachment metadata needed for transcription.
2. Add bridge-side voice-to-text handling for inbound audio messages.
3. Validate the behavior with bridge protocol tests.
4. Keep the Python adapter path unchanged except for consuming the bridge-emitted transcript.

