## Context

`openclaw-nim-channel` treats QChat as a distinct NIM capability block: the bot logs into IM, subscribes to QChat servers/channels, auto-accepts invites based on policy, and only forwards mentioned channel messages to the host pipeline. The current Hermes plugin already has the Python/Node split needed for that shape, but it does not yet expose QChat as a dedicated target or bridge path.

## Goals / Non-Goals

**Goals:**
- Add QChat text inbound/outbound support without changing the Hermes host architecture
- Keep QChat SDK interaction inside the Node bridge
- Make policy controls explicit for mention-gated delivery and server invite handling
- Use a Hermes-specific QChat target shape that does not collide with P2P/team routing

**Non-Goals:**
- Topic/thread parity for QChat
- QChat media attachments
- Long-message chunking or streaming changes
- Multi-instance redesign beyond the current plugin shape

## Decisions

### 1. Expose QChat as an explicit Hermes target prefix

Decision: use `qchat:<serverId>:<channelId>` for Hermes-facing QChat routing.

Rationale:
- It is unambiguous inside the plugin and does not overload `team:` or `user:`.
- The bridge can still normalize to the NIM SDK's native server/channel identifiers.
- The shape stays readable in tests and adapter code.

### 2. Keep QChat policy handling split between the bridge and the adapter

Decision: the bridge owns subscription/invite handling, while the Python adapter owns host-facing message gating and target inference.

Rationale:
- The bridge has the SDK connection and can subscribe or accept invites directly.
- The adapter is where Hermes-facing delivery policy belongs.
- Splitting the logic keeps the JSONL protocol narrow and testable.

### 3. Default QChat policy to OpenClaw-style open behavior

Decision: treat QChat as enabled by default once NIM credentials are configured, with `open`, `allowlist`, and `disabled` policies controlling how much of that surface is exposed.

Rationale:
- This matches the reference implementation's default posture.
- It keeps QChat usable without extra configuration in the common case.
- Operators can still lock it down explicitly when needed.

## Risks / Trade-offs

- QChat adds another active SDK listener path -> acceptable because it is part of the reference capability baseline
- Server invite auto-accept can be broad when policy is `open` -> acceptable only as a documented default; operators can restrict it with `allowlist` or `disabled`
- The `qchat:` target prefix is new to Hermes-facing code -> acceptable because it avoids ambiguity and can be normalized internally

## Migration Plan

1. Add QChat proposal/spec/tasks under the existing OpenSpec change.
2. Extend the bridge config and listener setup for QChat subscriptions and invites.
3. Extend the Python adapter for QChat target inference and message gating.
4. Add bridge and adapter tests for QChat routing.
5. Validate the change with OpenSpec and the test suites before moving to the next slice.

## Open Questions

- Whether the next slice should add QChat reply/thread parity
- Whether QChat channel names should be resolved eagerly in the bridge or lazily in the adapter
