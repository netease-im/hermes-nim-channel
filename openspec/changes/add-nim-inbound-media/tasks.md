## 1. OpenSpec

- [x] 1.1 Add proposal, design, and spec delta for inbound media support
- [x] 1.2 Validate the change with OpenSpec

## 2. Bridge

- [x] 2.1 Add normalized attachment metadata to inbound bridge events
- [x] 2.2 Preserve placeholder text for media-only inbound messages
- [x] 2.3 Add Node tests for inbound media payload normalization

## 3. Hermes Adapter

- [x] 3.1 Add shared inbound attachment parsing and caching helpers
- [x] 3.2 Populate `media_urls` and `media_types` on inbound NIM events
- [x] 3.3 Keep inbound attachment loading testable without network access

## 4. Verification

- [x] 4.1 Add Python tests for inbound media dispatch
- [x] 4.2 Run Python tests, Node tests, and OpenSpec validation
