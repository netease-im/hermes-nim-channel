## MODIFIED Requirements

### Requirement: Direct Message Access Control
The system SHALL support direct-message allowlists and explicit P2P policies for inbound NIM messages across adapter entrypoints.

#### Scenario: DM allowlist admits a sender
- **WHEN** `p2p_policy` is `allowlist` and the sender appears in `p2p_allow_from`
- **THEN** the adapter accepts the inbound direct message

#### Scenario: DM allowlist blocks a sender
- **WHEN** `p2p_policy` is `allowlist` and the sender does not appear in `p2p_allow_from`
- **THEN** the adapter ignores the inbound direct message

#### Scenario: DM policy disables direct messages
- **WHEN** `p2p_policy` is `disabled`
- **THEN** the adapter ignores inbound direct messages
