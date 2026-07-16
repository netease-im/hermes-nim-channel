## 1. Shared Title Formatting

- [x] 1.1 Add an idempotent QChat conversation-title helper with resolved-name and target fallback behavior
- [x] 1.2 Add helper tests for resolved, fallback, and already-prefixed titles

## 2. Adapter Integration

- [x] 2.1 Use the formatted title in the registered root adapter while preserving the raw channel context
- [x] 2.2 Apply the same title/context separation in the compatibility adapter
- [x] 2.3 Add inbound QChat tests for title parity, fallback, and context preservation

## 3. Validation

- [x] 3.1 Run Python tests and root plugin syntax checks
- [x] 3.2 Validate `align-qchat-session-title` and run `git diff --check`
- [x] 3.3 Restart the development-mode Hermes gateway and verify the corrected live QChat session title
