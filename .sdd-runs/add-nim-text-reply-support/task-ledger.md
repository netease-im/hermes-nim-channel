# Task Ledger: add-nim-text-reply-support

## Scope

- Add a bounded bridge-side cache for recently received raw SDK messages.
- Index cached messages by `messageServerId` and `messageClientId`.
- Route outbound text sends with known `reply_to` through `messageService.replyMessage`.
- Return an explicit bridge error when `reply_to` cannot be resolved.

## Verification

- `python3 -m unittest discover -s tests -p 'test_*.py'` passed, 22 tests.
- `node --test bridge/test/*.test.mjs` passed, 24 tests.
- `./scripts/sdd validate add-nim-text-reply-support` passed.

## Review Notes

- Confirmed plain text sends without `reply_to` still use the existing `sendMessage` path.
- Confirmed reply support is intentionally limited to messages observed by the current bridge process and retained in cache.
- Confirmed topic/thread replies, media replies, and historical message lookup remain out of scope for this slice.

## Final Gate

Passed. No open P0/P1/P2 findings remain for this slice.
