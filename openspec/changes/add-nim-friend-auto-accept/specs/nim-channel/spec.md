## MODIFIED Requirements

### Requirement: Direct Message Access Control
The system SHALL support direct-message allowlists for inbound NIM messages and P2P friend application handling.

#### Scenario: DM allowlist admits a sender
- **WHEN** `allow_all_users` is false and the sender appears in `allowed_users`
- **THEN** the adapter accepts the inbound direct message

#### Scenario: DM allowlist blocks a sender
- **WHEN** `allow_all_users` is false and the sender does not appear in `allowed_users`
- **THEN** the adapter ignores the inbound direct message

#### Scenario: P2P friend application is auto-accepted
- **WHEN** the bridge receives a NIM friend application from an applicant allowed by P2P policy
- **THEN** it calls the SDK friend service to accept the application

#### Scenario: P2P friend application is ignored by policy
- **WHEN** the bridge receives a NIM friend application from an applicant blocked by P2P policy
- **THEN** it does not call the SDK friend service to accept the application
