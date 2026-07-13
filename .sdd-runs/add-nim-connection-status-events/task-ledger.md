# Task Ledger: add-nim-connection-status-events

## Scope

- Normalize NIM SDK login, kickout, and disconnected callbacks.
- Emit bridge `connection` events for lifecycle state changes.
- Update plugin and compatibility adapters from bridge connection events.
- Unregister lifecycle listeners before manual cleanup logout.

## Verification

- `python3 -m unittest discover -s tests -p 'test_*.py'` passed, 23 tests.
- `node --test bridge/test/*.test.mjs` passed, 31 tests.
- `./scripts/sdd validate add-nim-connection-status-events` passed.

## Review Notes

- Confirmed message events remain unchanged.
- Confirmed logout, kickout, and disconnected mark adapters disconnected.
- Confirmed automatic reconnect remains out of scope.

## Final Gate

Passed. No open P0/P1/P2 findings remain for this slice.
