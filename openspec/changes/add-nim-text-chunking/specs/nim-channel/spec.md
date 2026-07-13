## MODIFIED Requirements

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

#### Scenario: Long outbound text is chunked
- **WHEN** Hermes asks the adapter to send text longer than the configured text chunk limit
- **THEN** the bridge splits the text into ordered chunks
- **AND** it sends each chunk sequentially through the SDK
- **AND** the bridge response includes chunk metadata

#### Scenario: Long reply text is chunked
- **WHEN** Hermes asks the adapter to send reply text longer than the configured text chunk limit
- **AND** `reply_to` matches a recently received NIM message
- **THEN** the bridge sends each chunk sequentially using the SDK `replyMessage` API
