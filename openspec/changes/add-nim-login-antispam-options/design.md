## Context

OpenClaw's advanced config includes `legacyLogin` and top-level `antispamEnabled`. `legacyLogin` changes the login option from AI bot mode to legacy login mode. `antispamEnabled` is passed to SDK send APIs under `antispamConfig`.

## Goals / Non-Goals

**Goals:**
- Preserve current default login behavior (`aiBot: 2`).
- Preserve current effective antispam default (`true`).
- Apply antispam config to text sends and text replies.

**Non-Goals:**
- Media antispam configuration.
- Runtime reconfiguration without reconnect.
- Changing QChat send options.

## Decisions

### 1. Keep defaults compatible with existing Hermes behavior

Decision: default `legacy_login` to `false` and `antispam_enabled` to `true`.

Rationale:
- Existing bridge behavior already uses `aiBot: 2`.
- OpenClaw defaults antispam to enabled.

### 2. Parse options in Python and bridge

Decision: expose explicit env/config fields in Python and also accept bridge-level aliases.

Rationale:
- Operators get Hermes-friendly env names.
- Tests can exercise bridge config directly without Python.

## Risks / Trade-offs

- Disabling antispam changes SDK-side moderation behavior and should be an operator decision.
- Legacy login may disable AI bot-specific behavior; it is opt-in only.

## Migration Plan

1. Add OpenSpec delta for login and antispam options.
2. Extend Python config/env/plugin docs.
3. Parse bridge config options.
4. Apply login and send option changes.
5. Validate Python tests, Node tests, and OpenSpec.
