## 1. OpenSpec

- [x] 1.1 Add proposal, design, and spec delta for topic media replies
- [x] 1.2 Validate the change with OpenSpec

## 2. Adapter

- [x] 2.1 Pass media `reply_to` through `NodeBridgeProcess.send_media`
- [x] 2.2 Preserve QChat media rejection and caption behavior

## 3. Bridge

- [x] 3.1 Add helper for eligible topic media reply sends
- [x] 3.2 Use topic media replies in `send_media` when cached topic context is available
- [x] 3.3 Preserve ordinary media send fallback

## 4. Verification

- [x] 4.1 Add Python tests for media `reply_to` propagation
- [x] 4.2 Add Node tests for topic media reply selection and fallback
- [x] 4.3 Run Python tests, Node tests, and OpenSpec validation
