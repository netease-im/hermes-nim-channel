## Why

The current Hermes plugin exposes SDK methods for streaming, QChat, and P2P Topics, but several host and bridge semantics remain incomplete: stream chunks do not share an SDK base message, QChat replies lose their native reply target, and different Topics from one user share a Hermes session. This parity change closes those gaps against `openclaw-nim-channel` while correcting reference behaviors that cannot be transferred safely as-is.

## What Changes

- Add stateful NIM stream sessions that reuse one SDK base message across chunks and clean up on completion, failure, timeout, or disconnect.
- Preserve ordinary-send fallback when SDK stream APIs are unavailable without retaining stale stream state.
- Register QChat passive listeners before login, retain bounded inbound reply context, and use native QChat reply APIs for replies.
- Inject resolved QChat channel name/topic context into the Hermes-visible inbound text and convert QChat outbound media into attachment links.
- **BREAKING**: Encode P2P Topic identity in Hermes chat IDs so different Topics from the same sender become separate sessions.
- Isolate Topic debounce batches, titles, reply contexts, and delayed/proactive outbound routing by NIM account, peer, and Topic ID.
- Fall back to ordinary outbound delivery when a requested reply or Topic context is no longer available.
- Route out-of-process `hermes send` and cron delivery through the running NIM adapter without creating a second NIM login.
- Add integration-oriented coverage for the registered Hermes adapter and multi-chunk bridge behavior.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `nim-channel`: complete stateful streaming, native QChat reply/context handling, and P2P Topic session/outbound parity.

## Impact

- Affected Python entrypoints and orchestration: `adapter.py`, `hermes_nim_channel/qchat.py`, `hermes_nim_channel/platforms/nim.py`, `hermes_nim_channel/platforms/nim_bridge.py`, and session-title helpers.
- Affected Node transport: `bridge/index.mjs`, `bridge/src/config.mjs`, `bridge/src/qchat.mjs`, and JSONL request parameters.
- Chat IDs for inbound Topic sessions gain a `:topic:<topicId>` suffix; existing non-Topic chat IDs remain unchanged.
- No new runtime dependency is introduced.
- A user-only Unix socket under the Hermes home directory is created while the NIM adapter is connected and removed on disconnect.
