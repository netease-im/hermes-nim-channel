# Task Ledger: add-nim-private-deployment-endpoints

## Scope

- Add private deployment LBS/link/NOS endpoint config to the Hermes NIM plugin surface.
- Forward endpoint values through the Python adapter bridge payload.
- Build `privateConf` and `V2NIMLoginServiceConfig` for `@yxim/nim-bot` startup.

## Verification

- `python3 -m unittest discover -s tests -p 'test_*.py'` passed, 21 tests.
- `node --test bridge/test/*.test.mjs` passed, 18 tests.
- `./scripts/sdd validate add-nim-private-deployment-endpoints` passed.

## Review Notes

- Confirmed public-cloud startup remains unchanged when no private endpoints are configured.
- Confirmed blank endpoint strings are ignored before SDK option generation.
- Confirmed string boolean values such as `"false"` do not become truthy through JavaScript `Boolean()`.

## Final Gate

Passed. No open P0/P1/P2 findings remain for this slice.
