## MODIFIED Requirements

### Requirement: Outbound Native Media Sending
The system SHALL send outbound NIM media attachments through native Hermes adapter media hooks instead of falling back to warning text.

#### Scenario: Send an image attachment
- **WHEN** Hermes calls the NIM adapter's image-file send path with a local image
- **THEN** the adapter sends a `send_media` request to the bridge with media kind `image`
- **AND** the bridge creates and sends a native NIM image message

#### Scenario: Send a file attachment
- **WHEN** Hermes calls the NIM adapter's document send path with a local file
- **THEN** the adapter sends a `send_media` request to the bridge with media kind `file`
- **AND** the bridge creates and sends a native NIM file message

#### Scenario: Send an audio attachment
- **WHEN** Hermes calls the NIM adapter's voice send path with a local audio file
- **THEN** the bridge derives the audio duration required by the SDK
- **AND** the bridge creates and sends a native NIM audio message

#### Scenario: Send a video attachment
- **WHEN** Hermes calls the NIM adapter's video send path with a local video file
- **THEN** the bridge derives the video duration, width, and height required by the SDK
- **AND** the bridge creates and sends a native NIM video message

#### Scenario: Caption text is preserved
- **WHEN** Hermes supplies caption text alongside an outbound media send
- **THEN** the adapter sends the native media attachment first
- **AND** it sends the caption text as a follow-up text message after the media succeeds

#### Scenario: Metadata inference failure is surfaced
- **WHEN** the bridge cannot derive required audio or video metadata
- **THEN** the media send fails with an explicit bridge error
- **AND** the adapter does not report the send as successful
