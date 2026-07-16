## ADDED Requirements

### Requirement: QChat Session Title Parity
The system SHALL label QChat sessions with the same stable conversation format as `openclaw-nim-channel` while keeping raw channel context separate from the title.

#### Scenario: Resolved channel name is available
- **WHEN** an inbound QChat message resolves a non-empty channel name
- **THEN** the Hermes session title is `云信·圈组·<频道名>`
- **AND** the agent-visible QChat context uses the unprefixed channel name

#### Scenario: Channel name is unavailable
- **WHEN** an inbound QChat message has no resolved channel name
- **THEN** the Hermes session title is `云信·圈组·<serverId>:<channelId>`

#### Scenario: Title is already formatted
- **WHEN** a QChat channel label already begins with `云信·圈组·`
- **THEN** the adapter does not add the prefix again

#### Scenario: Hermes generates a content title
- **WHEN** Hermes asynchronously generates a content-based title after the QChat session starts
- **THEN** the plugin pins the stable `云信·圈组·<频道名或目标>` title in Hermes session state
