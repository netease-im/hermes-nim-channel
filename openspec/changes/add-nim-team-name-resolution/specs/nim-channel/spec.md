## MODIFIED Requirements

### Requirement: Mention-Gated Team Messages
The system SHALL only process NIM team messages when the bot is explicitly mentioned and the team satisfies policy controls.

#### Scenario: Mentioned team message is accepted
- **WHEN** a team message includes the bot account in `force_push_account_ids`
- **AND** the team policy permits the team
- **THEN** the adapter forwards the message to Hermes as a group message event

#### Scenario: Team name is resolved
- **WHEN** the bridge receives a NIM team or superTeam message
- **AND** the SDK can resolve the team name
- **THEN** the inbound event includes the resolved team name as `conversation_name`

#### Scenario: Team name lookup fails
- **WHEN** the bridge receives a NIM team or superTeam message
- **AND** the SDK cannot resolve the team name
- **THEN** the inbound event still emits normally
- **AND** `conversation_name` falls back to the team target id
