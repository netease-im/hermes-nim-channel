## ADDED Requirements

### Requirement: QChat Subscription and Invite Handling

The system SHALL connect to NIM QChat after IM login, subscribe to joined servers, and auto-handle server invites according to QChat policy controls.

#### Scenario: Open policy subscribes and accepts
- **WHEN** NIM credentials are configured and QChat policy is `open`
- **THEN** the bridge registers QChat listeners after IM login
- **AND** it subscribes to joined QChat servers
- **AND** it auto-accepts QChat server invites

#### Scenario: Allowlist policy limits QChat surface
- **WHEN** QChat policy is `allowlist`
- **AND** the configured allowlist is non-empty
- **THEN** the bridge subscribes only the allowed QChat servers
- **AND** it accepts only invites for servers present in the allowlist

#### Scenario: Disabled policy suppresses QChat activity
- **WHEN** QChat policy is `disabled`
- **THEN** the bridge does not activate QChat subscriptions
- **AND** it ignores QChat server invites

### Requirement: Mention-Gated QChat Inbound Routing

The system SHALL forward inbound QChat text messages to Hermes only when the bot is explicitly mentioned and the QChat policy allows the server/channel/sender combination.

#### Scenario: Mentioned QChat message is accepted
- **WHEN** a QChat message mentions the bot account
- **AND** the message matches the configured QChat allowlist or policy
- **THEN** the adapter emits an inbound message event for `qchat:<serverId>:<channelId>`
- **AND** the event includes sender, target, session type, text, and mention metadata

#### Scenario: Unmentioned QChat message is ignored
- **WHEN** a QChat message does not mention the bot account
- **THEN** the adapter ignores the message even if the server is otherwise allowed

#### Scenario: Allowlist mismatch blocks QChat delivery
- **WHEN** QChat policy is `allowlist`
- **AND** the message does not match any configured allowlist entry
- **THEN** the adapter ignores the message

### Requirement: Outbound QChat Text Sending

The system SHALL send outbound text messages to QChat channels through the bridge and return a bridge-derived message identifier.

#### Scenario: Send a QChat text message
- **WHEN** Hermes asks the adapter to send text to `qchat:<serverId>:<channelId>`
- **THEN** the adapter sends a dedicated QChat send request to the bridge
- **AND** the bridge normalizes the QChat server and channel identifiers before calling the SDK
- **AND** the adapter returns a successful send result containing the bridge message identifier
