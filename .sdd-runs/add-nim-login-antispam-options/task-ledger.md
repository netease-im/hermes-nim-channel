# Task Ledger: add-nim-login-antispam-options

## Scope

- Add `legacy_login` / `NIM_LEGACY_LOGIN`.
- Add `antispam_enabled` / `NIM_ANTISPAM_ENABLED`.
- Apply legacy login by switching SDK login option from `aiBot: 2` to `aiBot: 0`.
- Apply configured antispam value to outbound text send and text reply SDK params.

## Verification

- `python3 -m unittest discover -s tests -p 'test_*.py'` passed, 22 tests.
- `node --test bridge/test/*.test.mjs` passed, 26 tests.
- `./scripts/sdd validate add-nim-login-antispam-options` passed.

## Review Notes

- Confirmed defaults preserve current behavior: `legacy_login=false`, `antispam_enabled=true`.
- Confirmed bridge parses string booleans explicitly so `"false"` does not become truthy.
- Confirmed media and QChat send options remain out of scope.

## Final Gate

Passed. No open P0/P1/P2 findings remain for this slice.
