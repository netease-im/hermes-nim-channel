## MODIFIED Requirements

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

#### Scenario: Connect with private deployment endpoints
- **WHEN** the operator configures private LBS, link, or NOS endpoint values
- **THEN** the adapter includes those values in the bridge connect payload
- **AND** the bridge passes `privateConf` to the NIM SDK constructor
- **AND** LBS/link values are also passed through `V2NIMLoginServiceConfig`
