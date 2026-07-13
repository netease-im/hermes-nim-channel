## MODIFIED Requirements

### Requirement: QChat Routing
The system SHALL support receiving and sending QChat text messages through the NIM bridge.

#### Scenario: Mentioned QChat message is accepted
- **WHEN** the bridge receives a QChat text message that mentions the bot
- **THEN** the adapter emits an inbound message event for `qchat:<serverId>:<channelId>`
- **AND** the event includes sender, target, session type, text, and mention metadata

#### Scenario: QChat channel info is resolved
- **WHEN** the bridge receives a QChat message for a channel whose info can be resolved by the SDK
- **THEN** the emitted payload includes the resolved channel name as `conversation_name`
- **AND** it includes the channel topic as metadata when present

#### Scenario: QChat channel info lookup fails
- **WHEN** QChat channel info cannot be resolved
- **THEN** the inbound message still emits normally
