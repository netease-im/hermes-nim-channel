## MODIFIED Requirements

### Requirement: Outbound Text Sending
The system SHALL send outbound text messages and text replies through the bridge and return bridge-derived message identifiers while preserving native NIM reply context when available.

#### Scenario: Send a direct text message
- **WHEN** Hermes asks the adapter to send text to `user:<accid>`
- **THEN** the adapter sends a `send_message` request to the bridge with session type `p2p`
- **AND** the adapter returns a successful send result containing the bridge message identifier

#### Scenario: Send a team text message
- **WHEN** Hermes asks the adapter to send text to `team:<teamId>`
- **THEN** the adapter sends a `send_message` request to the bridge with session type `team`
- **AND** the bridge normalizes the team target before calling the SDK

#### Scenario: Reply to a cached non-topic text message
- **WHEN** Hermes asks the adapter to send text with `reply_to`
- **AND** the cached original message does not include valid topic context
- **THEN** the bridge replies with the SDK `replyMessage` API

#### Scenario: Reply to a cached topic text message
- **WHEN** Hermes asks the adapter to send text with `reply_to`
- **AND** the cached original message includes valid SDK `topicRefer`
- **AND** the SDK exposes `V2NIMTopicService.replyTopicMessage`
- **THEN** the bridge replies with the SDK `replyTopicMessage` API using the original message and topic reference

#### Scenario: Fall back when topic reply service is unavailable
- **WHEN** Hermes asks the adapter to send text with `reply_to`
- **AND** the cached original message includes valid SDK `topicRefer`
- **AND** the SDK does not expose `V2NIMTopicService.replyTopicMessage`
- **THEN** the bridge replies with the SDK `replyMessage` API
