## ADDED Requirements

### Requirement: Inbound Audio Voice-to-Text

The system SHALL transcribe inbound NIM audio messages to text in the bridge before dispatching them to Hermes when the NIM SDK voice-to-text call succeeds.

#### Scenario: Audio message is transcribed successfully
- **WHEN** the bridge receives an inbound audio message with an attachment URL and duration
- **AND** the SDK voice-to-text call returns transcript text
- **THEN** the bridge emits the transcript as the event text
- **AND** the event still includes the normalized audio attachment metadata

#### Scenario: Audio transcription fails
- **WHEN** the bridge receives an inbound audio message
- **AND** the SDK voice-to-text call fails or returns empty text
- **THEN** the bridge emits the original audio placeholder text
- **AND** the event still includes the normalized audio attachment metadata

