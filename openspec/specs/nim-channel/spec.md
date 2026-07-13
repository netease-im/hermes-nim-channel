# nim-channel Specification

## Purpose
Define the Hermes Agent NIM channel plugin contract for plugin layout, bridge-backed connectivity, message routing, and future capability alignment with the OpenClaw NIM channel baseline.
## Requirements
### Requirement: Hermes Plugin Layout
The system SHALL expose the NIM integration as a Hermes platform plugin with root entrypoint files and an internal implementation package that does not shadow Hermes core modules.

#### Scenario: Plugin entrypoint is discoverable
- **WHEN** Hermes loads the plugin directory
- **THEN** it finds `plugin.yaml`, `adapter.py`, and `__init__.py`
- **AND** the plugin registers a `nim` platform adapter without requiring copied files inside Hermes core

#### Scenario: Internal package avoids core-module collisions
- **WHEN** the plugin is imported inside a Hermes runtime
- **THEN** local implementation modules resolve from `hermes_nim_channel`
- **AND** the plugin does not rely on a top-level local package named `gateway`

### Requirement: NIM Adapter Configuration
The system SHALL expose a `nim` platform adapter configuration that resolves credentials from either a shorthand token or discrete App Key, account, and token fields.

#### Scenario: Shorthand credentials take priority
- **WHEN** the operator provides `nim_token` or `NIM_CREDENTIALS` in the form `appKey|accid|token`
- **THEN** the adapter resolves credentials from that shorthand value
- **AND** the adapter ignores discrete App Key, account, and token fields for the same platform instance

#### Scenario: Discrete credentials are used as fallback
- **WHEN** no shorthand credential is provided
- **THEN** the adapter resolves credentials from `app_key`, `account`, and `token`
- **AND** the adapter treats the platform as not configured if any required field is missing

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

### Requirement: Direct Message Access Control
The system SHALL support direct-message allowlists for inbound NIM messages.

#### Scenario: DM allowlist admits a sender
- **WHEN** `allow_all_users` is false and the sender appears in `allowed_users`
- **THEN** the adapter accepts the inbound direct message

#### Scenario: DM allowlist blocks a sender
- **WHEN** `allow_all_users` is false and the sender does not appear in `allowed_users`
- **THEN** the adapter ignores the inbound direct message

### Requirement: Mention-Gated Team Messages
The system SHALL only process NIM team messages when the bot is explicitly mentioned and the team satisfies policy controls.

#### Scenario: Mentioned team message is accepted
- **WHEN** a team message includes the bot account in `force_push_account_ids`
- **AND** the team policy permits the team
- **THEN** the adapter forwards the message to Hermes as a group message event

#### Scenario: Unmentioned team message is ignored
- **WHEN** a team message does not mention the bot
- **THEN** the adapter ignores the message even if the team policy is otherwise open

#### Scenario: Team allowlist blocks an unapproved team
- **WHEN** team policy is `allowlist`
- **AND** the target team is not present in `group_allowlist`
- **THEN** the adapter ignores the message

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

### Requirement: Structured Bridge Protocol
The system SHALL exchange JSON line messages between Python and Node so that request/response correlation and event delivery remain deterministic.

#### Scenario: Response matches request identifier
- **WHEN** the Python adapter sends a bridge request with an `id`
- **THEN** the bridge responds with a JSON object that includes the same `id`
- **AND** the adapter resolves the matching pending request with that response

#### Scenario: Bridge emits inbound message events
- **WHEN** the bridge receives a NIM message from the SDK
- **THEN** it emits a JSONL `event` message whose payload contains sender, target, session type, text, and mention metadata

### Requirement: Reference Capability Baseline
The system SHALL treat `openclaw-nim-channel` as the NIM feature baseline for future Hermes-side capability work.

#### Scenario: Capability expansion starts from the reference implementation
- **WHEN** a developer adds a new NIM behavior beyond the current prototype surface
- **THEN** they use the corresponding `openclaw-nim-channel` behavior as the first implementation reference
- **AND** they adapt only the host-specific integration points required by Hermes
