## 1. OpenSpec

- [x] 1.1 Add proposal, design, and spec delta for text reply support
- [x] 1.2 Validate the change with OpenSpec

## 2. Bridge

- [x] 2.1 Add bounded reply message cache helper
- [x] 2.2 Cache inbound messages by server and client id
- [x] 2.3 Use SDK `replyMessage` when `send_message` includes a known `reply_to`
- [x] 2.4 Return an explicit error for unknown `reply_to`

## 3. Verification

- [x] 3.1 Add Node tests for reply cache indexing and lookup
- [x] 3.2 Run Python tests, Node tests, and OpenSpec validation
