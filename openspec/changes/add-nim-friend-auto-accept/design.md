## Context

OpenClaw maps P2P access control to both inbound message acceptance and friend application auto-acceptance. Hermes already has equivalent inbound controls through `allowed_users` and `allow_all_users`, but the bridge does not receive an explicit P2P policy object and therefore cannot decide whether to accept friend applications.

## Goals / Non-Goals

**Goals:**
- Preserve existing Hermes direct-message allowlist behavior.
- Add an OpenClaw-compatible `p2p` bridge payload with `policy` and `allowFrom`.
- Auto-accept friend applications for `open` policy and matching `allowlist` entries.
- Ignore friend applications for `disabled` policy or unmatched allowlist entries.

**Non-Goals:**
- Runtime P2P policy hot-reload.
- Multi-account instance management.
- Outbound friend application sending.
- Changing existing direct-message filtering semantics.

## Decisions

### 1. Derive P2P policy from Hermes config

Decision: add optional `p2p_policy` and `p2p_allow_from` fields while keeping `allowed_users` and `allow_all_users` as backward-compatible aliases.

Rationale:
- OpenClaw has explicit `p2p.policy` and `p2p.allowFrom`.
- Existing Hermes operators already use `allowed_users` / `allow_all_users`.
- The bridge needs a stable policy payload independent of Hermes-only field names.

### 2. Keep friend handling in the bridge

Decision: register the SDK friend application listener in `bridge/index.mjs`.

Rationale:
- The SDK service exists only in Node.
- Auto-accepting a friend application is transport lifecycle work, not a Hermes message event.

## Risks / Trade-offs

- If the SDK event name or application shape differs by SDK version, the listener logs and ignores malformed applications.
- Auto-accept behavior can expand who may establish P2P contact when policy is `open`; this matches OpenClaw's default but operators can set `NIM_P2P_POLICY=allowlist` or `disabled`.

## Migration Plan

1. Add OpenSpec delta for friend auto-accept.
2. Extend Python config and plugin env vars.
3. Add bridge policy parser/helper tests.
4. Register `V2NIMFriendService` listener during connect.
5. Validate Python tests, Node tests, and OpenSpec.
