# nim-channel Specification

## Purpose
Define the Hermes Agent NIM channel plugin contract for plugin layout, bridge-backed connectivity, message routing, and future capability alignment with the OpenClaw NIM channel baseline.
## Requirements
### Requirement: Hermes Plugin Layout
The system SHALL expose the NIM integration as a Hermes platform plugin with root entrypoint files and an internal implementation package that does not shadow Hermes core modules.

#### Scenario: Plugin entrypoint is discoverable
- **WHEN** Hermes loads the plugin directory
- **THEN** it finds `plugin.yaml`, `adapter.py`, and `__init__.py`
- **AND** the plugin registers a `nim` platform adapter without requiring copied files inside Hermes core

#### Scenario: Internal package avoids core-module collisions
- **WHEN** the plugin is imported inside a Hermes runtime
- **THEN** local implementation modules resolve from `hermes_nim_channel`
- **AND** the plugin does not rely on a top-level local package named `gateway`

### Requirement: NIM Adapter Configuration
The system SHALL expose a `nim` platform adapter configuration that resolves credentials from either a shorthand token or discrete App Key, account, and token fields.

#### Scenario: Shorthand credentials take priority
- **WHEN** the operator provides `nim_token` or `NIM_CREDENTIALS` in the form `appKey|accid|token`
- **THEN** the adapter resolves credentials from that shorthand value
- **AND** the adapter ignores discrete App Key, account, and token fields for the same platform instance

#### Scenario: Discrete credentials are used as fallback
- **WHEN** no shorthand credential is provided
- **THEN** the adapter resolves credentials from `app_key`, `account`, and `token`
- **AND** the adapter treats the platform as not configured if any required field is missing

### Requirement: NIM Multi-Instance Configuration
The system SHALL support up to three NIM account instances inside one Hermes `nim` platform adapter.

#### Scenario: Multiple enabled instances connect independently
- **WHEN** the operator provides an `instances` array or `NIM_INSTANCES` JSON array with two enabled credential entries
- **THEN** the adapter starts one independent bridge process per configured instance
- **AND** each bridge logs in with the credentials for its own instance
- **AND** one failed instance does not prevent other instances from staying connected

#### Scenario: Instance account IDs are derived
- **WHEN** an instance resolves credentials with app key `appKey1` and account `bot001`
- **THEN** the adapter derives the instance account ID as `appKey1:bot001`
- **AND** duplicate derived account IDs are rejected during configuration parsing

#### Scenario: Inbound multi-instance messages are routable
- **WHEN** the adapter receives an inbound message for a configured instance
- **THEN** it adds `nim_account_id` metadata with the derived account ID
- **AND** when more than one instance is configured, it prefixes the Hermes chat ID with `acct:<url-encoded-account-id>:`

#### Scenario: Outbound multi-instance messages select the correct bridge
- **WHEN** Hermes sends to `acct:<url-encoded-account-id>:user:<accid>` or passes `nim_account_id` metadata
- **THEN** the adapter uses the bridge for that account ID
- **AND** it strips the `acct:` prefix before sending the target to the Node bridge

### Requirement: Bridge-Backed Connection
The system SHALL start a Node bridge process for NIM transport and connect to NetEase IM by logging in as an AI Bot.

#### Scenario: Successful bridge connect
- **WHEN** the Hermes NIM adapter connects with valid credentials
- **THEN** it starts the configured bridge command
- **AND** it sends a `connect` request over the JSONL protocol
- **AND** the bridge logs in with `aiBot: 2`

#### Scenario: Bridge startup failure is surfaced
- **WHEN** the bridge cannot start or returns an error response during connect
- **THEN** the adapter marks the platform as disconnected
- **AND** the failure is surfaced as a bridge error rather than being silently ignored

### Requirement: Direct Message Access Control
The system SHALL support direct-message allowlists for inbound NIM messages.

#### Scenario: DM allowlist admits a sender
- **WHEN** `allow_all_users` is false and the sender appears in `allowed_users`
- **THEN** the adapter accepts the inbound direct message

#### Scenario: DM allowlist blocks a sender
- **WHEN** `allow_all_users` is false and the sender does not appear in `allowed_users`
- **THEN** the adapter ignores the inbound direct message

### Requirement: Mention-Gated Team Messages
The system SHALL only process NIM team messages when the bot is explicitly mentioned and the team satisfies policy controls.

#### Scenario: Mentioned team message is accepted
- **WHEN** a team message includes the bot account in `force_push_account_ids`
- **AND** the team policy permits the team
- **THEN** the adapter forwards the message to Hermes as a group message event

#### Scenario: Unmentioned team message is ignored
- **WHEN** a team message does not mention the bot
- **THEN** the adapter ignores the message even if the team policy is otherwise open

#### Scenario: Team allowlist blocks an unapproved team
- **WHEN** team policy is `allowlist`
- **AND** the target team is not present in `group_allowlist`
- **THEN** the adapter ignores the message

### Requirement: Outbound Text Sending
The system SHALL send outbound text messages through the bridge and return a bridge-derived message identifier.

#### Scenario: Send a direct text message
- **WHEN** Hermes asks the adapter to send text to `user:<accid>`
- **THEN** the adapter sends a `send_message` request to the bridge with session type `p2p`
- **AND** the adapter returns a successful send result containing the bridge message identifier

#### Scenario: Send a team text message
- **WHEN** Hermes asks the adapter to send text to `team:<teamId>`
- **THEN** the adapter sends a `send_message` request to the bridge with session type `team`
- **AND** the bridge normalizes the team target before calling the SDK

### Requirement: Structured Bridge Protocol
The system SHALL exchange JSON line messages between Python and Node so that request/response correlation and event delivery remain deterministic.

#### Scenario: Response matches request identifier
- **WHEN** the Python adapter sends a bridge request with an `id`
- **THEN** the bridge responds with a JSON object that includes the same `id`
- **AND** the adapter resolves the matching pending request with that response

#### Scenario: Bridge emits inbound message events
- **WHEN** the bridge receives a NIM message from the SDK
- **THEN** it emits a JSONL `event` message whose payload contains sender, target, session type, text, and mention metadata

### Requirement: Reference Capability Baseline
The system SHALL treat `openclaw-nim-channel` as the NIM feature baseline for future Hermes-side capability work.

#### Scenario: Capability expansion starts from the reference implementation
- **WHEN** a developer adds a new NIM behavior beyond the current prototype surface
- **THEN** they use the corresponding `openclaw-nim-channel` behavior as the first implementation reference
- **AND** they adapt only the host-specific integration points required by Hermes

### Requirement: Stateful Stream Sessions
The system SHALL preserve one SDK base message for all chunks in the same outbound NIM stream and SHALL bound the lifetime of that state.

#### Scenario: Consecutive chunks reuse the base message
- **WHEN** Hermes sends multiple stream chunks with the same stream ID, account, target, session type, and reply target
- **THEN** the bridge creates an SDK message for the first chunk
- **AND** it reuses the SDK result as the base message for each later chunk

#### Scenario: Stream completion releases state
- **WHEN** a stream chunk is marked complete
- **THEN** the bridge sends it with `finish = 1`
- **AND** it removes the retained stream state after the SDK call settles

#### Scenario: Abandoned stream state expires
- **WHEN** a stream receives no chunk before its configured timeout or the bridge disconnects
- **THEN** the bridge removes its retained SDK message state

#### Scenario: Missing stream API falls back
- **WHEN** the SDK stream API required for a chunk is unavailable
- **THEN** the bridge sends the chunk as ordinary text
- **AND** it does not retain stream state for that fallback send

### Requirement: Native QChat Reply Context
The system SHALL preserve bounded QChat inbound message context so replies can use the native QChat reply API.

#### Scenario: Agent response replies to the QChat message
- **WHEN** Hermes sends QChat text with a reply target that matches cached inbound QChat context
- **THEN** the bridge calls `qchatMsg.replyMessage` with the original QChat SDK message

#### Scenario: QChat reply context is unavailable
- **WHEN** the reply target is missing or no longer cached
- **THEN** the bridge sends ordinary QChat text rather than failing the whole response

#### Scenario: QChat listeners cover login transition
- **WHEN** a bridge starts with QChat enabled
- **THEN** passive QChat message and system-notification listeners are registered before NIM login
- **AND** authenticated server discovery and subscriptions run after login succeeds

### Requirement: QChat Agent Context and Media Fallback
The system SHALL expose resolved QChat channel context to the agent and SHALL preserve generated media as readable links when native QChat media is unavailable.

#### Scenario: Channel topic is visible to the agent
- **WHEN** QChat channel information contains a name or topic
- **THEN** the inbound Hermes message text includes that channel context exactly once
- **AND** the original user text remains available in the same event

#### Scenario: QChat reply contains media
- **WHEN** Hermes attempts to send QChat media with an optional caption
- **THEN** the adapter sends one QChat text message containing the caption and media path or URL
- **AND** it does not invoke unsupported native QChat media creation

### Requirement: P2P Topic Session Isolation
The system SHALL isolate P2P Topic sessions by receiving NIM account, sender account, and Topic ID.

#### Scenario: Topic chat ID is derived
- **WHEN** an inbound P2P message has a valid Topic ID
- **THEN** its Hermes chat ID ends with `user:<accid>:topic:<topicId>`
- **AND** multi-instance account prefixes remain ahead of that target

#### Scenario: Different Topics do not share a session
- **WHEN** the same sender sends messages in two different Topic IDs
- **THEN** Hermes receives different chat IDs and batch keys for those messages

#### Scenario: Topic title includes the Topic name
- **WHEN** a Topic name is resolved
- **THEN** the Hermes conversation title includes both the sender display name and Topic name

### Requirement: Durable Topic Outbound Routing
The system SHALL retain bounded Topic reply context independently from the generic recent-message cache and SHALL use it for immediate and delayed outbound sends.

#### Scenario: Reply resolves by message ID
- **WHEN** outbound text or media includes a reply target registered for a Topic
- **THEN** the bridge sends through `replyTopicMessage` using the cached original SDK message and Topic reference

#### Scenario: Delayed send resolves by Topic ID
- **WHEN** outbound metadata identifies a Topic ID but omits a reply message ID
- **THEN** the bridge uses the latest unexpired context for the same account, peer, and Topic

#### Scenario: Topic stream chunks preserve Topic routing
- **WHEN** Hermes sends a stream chunk to a Topic-aware P2P target with valid Topic context
- **THEN** the bridge sends that chunk through `V2NIMTopicService.replyTopicMessage`
- **AND** it does not use the Thread-only `replyStreamMessage` API

#### Scenario: Topic context miss degrades safely
- **WHEN** no matching reply or Topic context exists
- **THEN** the bridge sends an ordinary message to the underlying P2P target
- **AND** it reports fallback metadata in the send result

#### Scenario: Topic context expires
- **WHEN** Topic context exceeds its configured TTL or the bridge disconnects
- **THEN** the bridge removes the original SDK message and its aliases

### Requirement: Safe Standalone Delivery
The system SHALL support out-of-process Hermes delivery through the connected NIM adapter without creating a competing NIM login.

#### Scenario: CLI send uses the connected adapter
- **WHEN** `hermes send` targets NIM while the gateway adapter is connected
- **THEN** the standalone sender relays the request to that adapter over a user-only local socket
- **AND** the adapter applies its normal account, Topic, and QChat target routing

#### Scenario: Gateway is unavailable
- **WHEN** no connected NIM adapter owns the local relay socket
- **THEN** standalone delivery returns a descriptive error
- **AND** it does not start another NIM bridge process

#### Scenario: Adapter disconnects
- **WHEN** the NIM adapter begins disconnecting
- **THEN** it stops accepting standalone sends before logging out bridge runtimes
- **AND** it removes its local relay socket

### Requirement: QChat Session Title Parity
The system SHALL label QChat sessions with the same stable conversation format as `openclaw-nim-channel` while keeping raw channel context separate from the title.

#### Scenario: Resolved channel name is available
- **WHEN** an inbound QChat message resolves a non-empty channel name
- **THEN** the Hermes session title is `云信·圈组·<频道名>`
- **AND** the agent-visible QChat context uses the unprefixed channel name

#### Scenario: Channel name is unavailable
- **WHEN** an inbound QChat message has no resolved channel name
- **THEN** the Hermes session title is `云信·圈组·<serverId>:<channelId>`

#### Scenario: Title is already formatted
- **WHEN** a QChat channel label already begins with `云信·圈组·`
- **THEN** the adapter does not add the prefix again

#### Scenario: Hermes generates a content title
- **WHEN** Hermes asynchronously generates a content-based title after the QChat session starts
- **THEN** the plugin pins the stable `云信·圈组·<频道名或目标>` title in Hermes session state
