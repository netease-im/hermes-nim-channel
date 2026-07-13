## Why

`openclaw-nim-channel` auto-accepts NIM P2P friend applications when the sender passes the configured P2P policy. The Hermes plugin currently filters inbound direct messages after they arrive, but it does not handle the friend-application lifecycle, which can prevent first-contact P2P messaging in deployments that require a friend relationship.

## What Changes

- Add explicit P2P policy and allowlist fields to the resolved plugin config
- Forward P2P policy controls through the bridge connect payload
- Register a NIM friend application listener in the Node bridge
- Auto-accept friend applications only when P2P policy allows the applicant
- Add unit tests for config resolution and policy evaluation

## Capabilities

### Modified Capabilities

- `nim-channel`: support OpenClaw-compatible friend application auto-acceptance for P2P message readiness

## Impact

- Affected code:
  - `adapter.py`
  - `plugin.yaml`
  - `README.md`
  - `hermes_nim_channel/config.py`
  - `bridge/src/config.mjs`
  - `bridge/index.mjs`
  - `bridge/test/protocol.test.mjs`
  - `tests/test_nim_config.py`
- Runtime behavior:
  - When `V2NIMFriendService` is available, the bridge may accept incoming friend applications according to P2P policy.
