## MODIFIED Requirements

### Requirement: Structured Bridge Protocol
The system SHALL exchange JSON line messages between Python and Node so that request/response correlation, event delivery, native context metadata, and optional operational markers remain deterministic.

#### Scenario: Topic info is enriched
- **WHEN** the bridge receives a NIM message with valid SDK `topicRefer`
- **AND** the SDK can resolve topic info
- **THEN** the emitted inbound payload includes `topic_info`
- **AND** it includes `topic_name` when a topic name is available

#### Scenario: Batch metadata is attached
- **WHEN** inbound debounce batching is enabled
- **AND** multiple messages arrive for the same conversation before the debounce window closes
- **THEN** the bridge emits one event per message
- **AND** each event includes `batch_id`, `batch_key`, `batch_index`, and `batch_size`

#### Scenario: Quick comment marker is optional
- **WHEN** quick comments are enabled
- **AND** the SDK supports quick comments for an inbound message
- **THEN** the bridge adds the configured quick comment before emitting the message
- **AND** it schedules cleanup for that quick comment

#### Scenario: Adapter forwards operational metadata
- **WHEN** the Python adapter receives bridge payload fields for topic info, batch metadata, or quick comment metadata
- **THEN** the Hermes message event preserves those fields under raw metadata for downstream consumers

### Requirement: Outbound Text Sending
The system SHALL send outbound text messages, text replies, stream chunks, and edit-facade replacement text through the bridge while preserving existing send behavior.

#### Scenario: Stream send is requested
- **WHEN** Hermes sends text with stream metadata
- **THEN** the adapter sends a `send_stream_message` request to the bridge
- **AND** the bridge uses the SDK stream send API when available
- **AND** it falls back to ordinary text send when stream sending is unavailable

#### Scenario: Edit facade is requested
- **WHEN** Hermes requests an edit facade with replacement text
- **THEN** the bridge sends the replacement text as a new text message to the target
