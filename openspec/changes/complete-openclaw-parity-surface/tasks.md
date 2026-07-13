## 1. OpenSpec

- [x] 1.1 Add proposal, design, and spec delta for remaining parity surface
- [x] 1.2 Validate the change with OpenSpec

## 2. Configuration

- [x] 2.1 Add inbound debounce configuration
- [x] 2.2 Add quick comment configuration
- [x] 2.3 Document env vars

## 3. Bridge

- [x] 3.1 Resolve topic info/name for inbound topic messages
- [x] 3.2 Add inbound debounce batch metadata
- [x] 3.3 Add optional quick-comment processing marker and timed cleanup
- [x] 3.4 Add stream send and edit facade request handlers
- [x] 3.5 Preserve existing ordinary send, reply, media, and QChat behavior

## 4. Adapter

- [x] 4.1 Forward new config fields to the bridge
- [x] 4.2 Route metadata-driven stream sends
- [x] 4.3 Expose edit facade through adapter/bridge helpers
- [x] 4.4 Forward topic and batch metadata into Hermes events

## 5. Verification

- [x] 5.1 Add Python tests for config, metadata routing, and event metadata
- [x] 5.2 Add Node tests for topic info, batch metadata, quick comments, stream fallback, and edit facade helpers
- [x] 5.3 Run Python tests, Node tests, and OpenSpec validation
