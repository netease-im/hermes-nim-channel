# Task Ledger: add-nim-friend-auto-accept

## Scope

- Add explicit P2P policy and allowlist config while preserving `allowed_users` and `allow_all_users` compatibility.
- Forward `p2p.policy` and `p2p.allowFrom` to the Node bridge.
- Register the NIM friend application listener and auto-accept applications only when policy allows the applicant.

## Verification

- `python3 -m unittest discover -s tests -p 'test_*.py'` passed, 22 tests.
- `node --test bridge/test/*.test.mjs` passed, 20 tests.
- `./scripts/sdd validate add-nim-friend-auto-accept` passed.

## Review Notes

- Confirmed legacy `NIM_ALLOWED_USERS` derives an `allowlist` P2P policy unless `NIM_ALLOW_ALL_USERS` or explicit `NIM_P2P_POLICY` overrides it.
- Confirmed disabled and unmatched allowlist policy do not accept friend applications.
- Confirmed listener registration is skipped if the SDK friend service or accept API is unavailable.

## Final Gate

Passed. No open P0/P1/P2 findings remain for this slice.
