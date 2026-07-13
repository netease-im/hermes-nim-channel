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

#### Scenario: Reply to a recent NIM text context
- **WHEN** Hermes asks the adapter to send text with `reply_to` matching a recently received NIM message
- **THEN** the bridge sends the text using the SDK `replyMessage` API
- **AND** the adapter returns a successful send result containing the bridge message identifier

#### Scenario: Reply target is unknown
- **WHEN** Hermes asks the adapter to send text with `reply_to` that is not present in the bridge reply cache
- **THEN** the bridge returns an explicit error instead of silently sending a plain message
