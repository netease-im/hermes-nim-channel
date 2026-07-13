## 1. OpenSpec

- [x] 1.1 Add proposal, design, and spec delta for topic text replies
- [x] 1.2 Validate the change with OpenSpec

## 2. Bridge

- [x] 2.1 Add helper to resolve native topic reply context from cached SDK messages
- [x] 2.2 Use `V2NIMTopicService.replyTopicMessage` for eligible text replies
- [x] 2.3 Preserve fallback to `replyMessage` for non-topic or unsupported SDK paths

## 3. Verification

- [x] 3.1 Add Node tests for topic reply eligibility and fallback
- [x] 3.2 Run Python tests, Node tests, and OpenSpec validation
