## ADDED Requirements

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
