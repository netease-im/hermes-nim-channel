## MODIFIED Requirements

### Requirement: Structured Bridge Protocol
The system SHALL exchange JSON line messages between Python and Node so that request/response correlation, event delivery, transport acknowledgements, and native context metadata remain deterministic.

#### Scenario: Bridge emits inbound message events
- **WHEN** the bridge receives a NIM message from the SDK
- **THEN** it emits a JSONL `event` message whose payload contains sender, target, session type, text, and mention metadata

#### Scenario: Topic context is preserved
- **WHEN** the bridge receives a NIM message with a valid SDK `topicRefer`
- **THEN** the emitted inbound payload includes normalized `topic_refer` metadata

#### Scenario: Thread reply context is preserved
- **WHEN** the bridge receives a NIM message with SDK `threadReply`
- **THEN** the emitted inbound payload includes `thread_reply` metadata
