## MODIFIED Requirements

### Requirement: Bridge-Backed Connection
The system SHALL start a Node bridge process for NIM transport and connect to NetEase IM by logging in as an AI Bot unless legacy login is configured.

#### Scenario: Successful bridge connect
- **WHEN** the Hermes NIM adapter connects with valid credentials
- **THEN** it starts the configured bridge command
- **AND** it sends a `connect` request over the JSONL protocol
- **AND** the bridge logs in with `aiBot: 2`

#### Scenario: Legacy login mode
- **WHEN** the operator enables legacy login
- **THEN** the bridge logs in with `aiBot: 0`

### Requirement: Outbound Text Sending
The system SHALL send outbound text messages through the bridge and return a bridge-derived message identifier.

#### Scenario: Send text with antispam config
- **WHEN** Hermes asks the adapter to send text
- **THEN** the bridge includes the configured `antispamEnabled` value in the SDK send params

#### Scenario: Send reply text with antispam config
- **WHEN** Hermes asks the adapter to send reply text
- **THEN** the bridge includes the configured `antispamEnabled` value in the SDK reply params
