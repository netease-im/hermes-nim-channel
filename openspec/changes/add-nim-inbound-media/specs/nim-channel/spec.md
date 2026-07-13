## MODIFIED Requirements

### Requirement: Inbound Native Media Dispatch
The system SHALL preserve inbound NIM media attachments as Hermes-native media event fields instead of treating them as text-only messages.

#### Scenario: Image attachment is exposed to Hermes
- **WHEN** the bridge receives an inbound NIM image message with an attachment URL
- **THEN** it includes normalized attachment metadata in the event payload
- **AND** the adapter caches the attachment locally and populates `media_urls` and `media_types`

#### Scenario: File attachment is exposed to Hermes
- **WHEN** the bridge receives an inbound NIM file message with an attachment URL
- **THEN** the adapter caches the file locally
- **AND** the resulting event includes a document media path for Hermes tools

#### Scenario: Audio attachment is exposed to Hermes
- **WHEN** the bridge receives an inbound NIM audio message with an attachment URL
- **THEN** the adapter caches the audio locally
- **AND** the resulting event includes an audio media type for downstream host handling

#### Scenario: Video attachment is exposed to Hermes
- **WHEN** the bridge receives an inbound NIM video message with an attachment URL
- **THEN** the adapter caches the video locally
- **AND** the resulting event includes a video media type for downstream host handling

#### Scenario: Media-only messages keep a readable placeholder
- **WHEN** an inbound NIM media message has no text body
- **THEN** the bridge synthesizes a readable placeholder text
- **AND** the placeholder may include the attachment URL for operator visibility
