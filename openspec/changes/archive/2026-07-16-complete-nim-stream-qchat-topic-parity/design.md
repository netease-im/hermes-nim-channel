## Context

Hermes loads `adapter.py` as the real plugin entrypoint while NIM SDK objects live inside a per-account Node bridge process. SDK message objects cannot cross JSONL, so streaming, QChat replies, and Topic replies require bridge-owned state. The reference plugin keeps these objects in-process; Hermes must reproduce that ownership inside the bridge and expose only stable string identifiers to Python.

## Goals / Non-Goals

**Goals:**

- Make repeated stream requests operate on one SDK stream message.
- Preserve QChat native reply semantics and eliminate the post-login listener gap.
- Make Topic identity part of Hermes routing rather than metadata only.
- Support delayed Topic routing without depending on the small generic reply cache.
- Keep all state bounded and scoped to one bridge/account process.

**Non-Goals:**

- Add native QChat image/file/audio/video messages; links remain the compatibility fallback.
- Modify Hermes core or require a new Hermes streaming hook.
- Copy the reference behavior where Topic and group streams are inconsistently finalized.

## Decisions

### Bridge-owned stream registry

`bridge/index.mjs` will keep a registry keyed by an explicit `stream_id` plus target, session type, and reply target. Each entry stores the SDK base message, expected next chunk index, and an expiry timer. A missing `stream_id` is derived deterministically from the target and reply target for compatibility, but callers should pass one when concurrent streams are possible.

The bridge, rather than Python, owns the registry because SDK message objects are not JSON serializable. Completion and failed SDK calls remove the entry. Disconnect removes all entries.

### Two-phase QChat startup

QChat setup is split into passive listener registration before login and authenticated activation after login. The runtime returned by the setup helper exposes `activate()` and `stop()`. Inbound raw QChat messages are retained in a bounded cache keyed by server/client message IDs before normalized events are emitted.

QChat sends resolve `reply_to` against that cache. A hit calls `qchatMsg.replyMessage`; a miss calls `sendMessage` and returns fallback metadata. Media adapters convert local paths or URLs into a single text payload because the reference surface does not provide native QChat media.

### Topic-aware Hermes target format

The canonical Topic target is `user:<accid>:topic:<topicId>`, optionally prefixed by `acct:<encoded-account-id>:`. Parsing strips the Topic suffix before building a NIM conversation ID and forwards `topic_id` separately. Non-Topic P2P IDs remain compatible.

The adapter uses the Topic-aware target as `SessionSource.chat_id`, and the bridge includes Topic ID in debounce keys. Conversation names append the Topic name when available.

### Dedicated Topic context registry

The bridge maintains a 30-minute bounded registry keyed by account-local peer and Topic ID, with aliases for server/client message IDs. It stores the original SDK message and normalized Topic reference. Standard text, media, and stream requests can resolve by `reply_to` or `topic_id`. Context miss falls back to ordinary P2P delivery instead of throwing.

NIM does not expose a Topic-native stream API. Topic stream chunks therefore follow the reference implementation and call `V2NIMTopicService.replyTopicMessage` once per chunk. They must not call `replyStreamMessage`, which only carries Thread metadata. Stateful SDK base-message reuse remains enabled for ordinary P2P and team streams.

### Local standalone-send relay

Hermes invokes plugin `standalone_sender_fn` hooks from a separate CLI or cron process, so its in-process gateway adapter reference is unavailable. Starting another NIM bridge for each send risks kicking the persistent gateway login offline. The connected root adapter therefore owns a user-only Unix socket under the Hermes home directory. The standalone hook sends one bounded JSON request over that socket, and the connected adapter performs the normal account, QChat, and Topic routing.

The relay socket is mode `0600`, accepts only local filesystem clients, reports structured send results, and is removed before bridge logout. A stale socket is replaced only when no process accepts connections on it. If the gateway is not running, standalone delivery fails with an explicit instruction instead of creating an ephemeral NIM login.

## Risks / Trade-offs

- [Concurrent streams without explicit IDs can collide] -> Include `stream_id` in adapter metadata and scope derived compatibility IDs by target and reply target.
- [Bridge memory grows with SDK message objects] -> Bound caches, expire Topic/stream contexts, and clear all state on disconnect.
- [Topic chat IDs change existing Hermes session routing] -> Apply the suffix only to valid Topic messages; document the intentional session split.
- [Channel topic text could be duplicated by callers] -> Add one stable context prefix only in the adapter conversion path.
- [Hermes has no native block-stream callback] -> Complete the transport contract now and retain ordinary sends for normal host replies.
- [A second standalone NIM login can kick the gateway offline] -> Relay standalone sends through the connected adapter over a user-only Unix socket and never create an ephemeral bridge.

## Migration Plan

1. Deploy bridge and Python changes together because Topic target parsing changes across the JSONL boundary.
2. Existing non-Topic, team, and QChat chat IDs continue unchanged.
3. New Topic messages create separate Hermes sessions; old combined P2P history remains readable but is not migrated.
4. Rollback restores prior chat IDs; retained state is process-local and requires no data migration.

## Open Questions

None. The absence of a Hermes generation-stream hook is an upstream host limitation; this change completes the plugin transport contract without modifying Hermes core.
