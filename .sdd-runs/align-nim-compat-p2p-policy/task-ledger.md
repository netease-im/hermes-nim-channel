# Task Ledger: align-nim-compat-p2p-policy

## Scope

- Align compatibility adapter direct-message filtering with the root plugin adapter.
- Support explicit `p2p_policy` and `p2p_allow_from` in `hermes_nim_channel/platforms/nim.py`.
- Preserve legacy `allowed_users` fallback.

## Verification

- `python3 -m unittest discover -s tests -p 'test_*.py'` passed, 25 tests.
- `node --test bridge/test/*.test.mjs` passed, 33 tests.
- `./scripts/sdd validate align-nim-compat-p2p-policy` passed.

## Review Notes

- Confirmed `p2p_policy=allowlist` admits only configured senders.
- Confirmed `p2p_policy=disabled` blocks direct messages.
- Confirmed bridge behavior is unchanged.

## Final Gate

Passed. No open P0/P1/P2 findings remain for this slice.
