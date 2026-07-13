# Task Ledger: add-nim-text-chunking

## Scope

- Add `text_chunk_limit` / `NIM_TEXT_CHUNK_LIMIT` with default `4000`.
- Forward text chunk limit through the bridge payload.
- Split outbound plain text and cached text replies using OpenClaw-compatible newline/space/forced boundaries.
- Return chunk metadata while preserving top-level `message_id` compatibility.

## Verification

- `python3 -m unittest discover -s tests -p 'test_*.py'` passed, 22 tests.
- `node --test bridge/test/*.test.mjs` passed, 26 tests.
- `./scripts/sdd validate add-nim-text-chunking` passed.

## Review Notes

- Confirmed short text remains a single SDK send.
- Confirmed long text chunks are sent sequentially and stop on the first SDK failure.
- Confirmed partial-send risk is documented; retry semantics remain out of scope.

## Final Gate

Passed. No open P0/P1/P2 findings remain for this slice.
