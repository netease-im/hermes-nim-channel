## MODIFIED Requirements

### Requirement: Outbound Media Sending
The system SHALL send outbound media messages through the bridge and preserve native NIM topic reply context when eligible.

#### Scenario: Send an image attachment
- **WHEN** Hermes calls the NIM adapter's image-file send path with a local image
- **THEN** the adapter sends a `send_media` request to the bridge with media kind `image`
- **AND** the bridge creates and sends a native NIM image message

#### Scenario: Send a file attachment
- **WHEN** Hermes calls the NIM adapter's document send path with a local file
- **THEN** the adapter sends a `send_media` request to the bridge with media kind `file`
- **AND** the bridge creates and sends a native NIM file message

#### Scenario: Reply to a cached topic with media
- **WHEN** Hermes calls a media send path with `reply_to`
- **AND** the cached original message includes valid SDK `topicRefer`
- **AND** the SDK exposes `V2NIMTopicService.replyTopicMessage`
- **THEN** the bridge sends the media message with the SDK `replyTopicMessage` API using the original message and topic reference

#### Scenario: Fall back for non-topic media sends
- **WHEN** Hermes calls a media send path with `reply_to`
- **AND** the cached original message is unavailable or does not have eligible topic context
- **THEN** the bridge sends the media as an ordinary media message
