## MODIFIED Requirements

### Requirement: Bridge-Backed Connection
The system SHALL start a Node bridge process for NIM transport and surface subsequent SDK connection lifecycle changes to the adapter.

#### Scenario: Successful bridge connect
- **WHEN** the Hermes NIM adapter connects with valid credentials
- **THEN** it starts the configured bridge command
- **AND** it sends a `connect` request over the JSONL protocol
- **AND** the bridge logs in with `aiBot: 2`

#### Scenario: SDK disconnect is surfaced
- **WHEN** the SDK reports logout, kickout, or disconnected after startup
- **THEN** the bridge emits a `connection` event with a normalized status
- **AND** the adapter marks the platform as disconnected

#### Scenario: Manual disconnect remains explicit
- **WHEN** Hermes asks the adapter to disconnect
- **THEN** the adapter stops the bridge and marks itself disconnected
- **AND** bridge cleanup does not require an additional SDK logout event
