## MODIFIED Requirements

### Requirement: Structured Bridge Protocol
The system SHALL exchange JSON line messages between Python and Node so that request/response correlation, event delivery, and transport acknowledgements remain deterministic.

#### Scenario: Response matches request identifier
- **WHEN** the Python adapter sends a bridge request with an `id`
- **THEN** the bridge responds with a JSON object that includes the same `id`
- **AND** the adapter resolves the matching pending request with that response

#### Scenario: Bridge emits inbound message events
- **WHEN** the bridge receives a NIM message from the SDK
- **THEN** it emits a JSONL `event` message whose payload contains sender, target, session type, text, and mention metadata

#### Scenario: Online P2P message is acknowledged as read
- **WHEN** the bridge receives an online inbound P2P message
- **THEN** it sends a P2P read receipt through the SDK message service

#### Scenario: Online team messages are acknowledged as read
- **WHEN** the bridge receives online inbound team messages
- **THEN** it sends team read receipts through the SDK message service in batches no larger than 50 messages

#### Scenario: Synced messages are not acknowledged
- **WHEN** the bridge receives offline, roaming, or history messages
- **THEN** it does not send read receipts for those messages
