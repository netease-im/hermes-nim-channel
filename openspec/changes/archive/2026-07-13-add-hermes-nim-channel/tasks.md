## 1. OpenSpec

- [x] 1.1 Create proposal, design, and spec artifacts for the new `nim-channel` capability
- [x] 1.2 Validate the OpenSpec change with the CLI

## 2. Python Adapter

- [x] 2.1 Add Hermes-compatible config helpers and local compatibility types
- [x] 2.2 Implement the `nim` adapter with DM ACLs, team gating, and bridge lifecycle management
- [x] 2.3 Add Python unit tests for config parsing and inbound policy decisions
- [x] 2.4 Re-home local Python code under `hermes_nim_channel/` to avoid `gateway` module collisions

## 3. Node Bridge

- [x] 3.1 Implement JSONL protocol helpers and bridge config parsing
- [x] 3.2 Implement the Node bridge entrypoint with NIM login, receive, send, and health commands
- [x] 3.3 Add Node tests for protocol framing

## 4. Documentation

- [x] 4.1 Document repository layout, config, and verification commands in `README.md`
- [x] 4.2 Add Hermes plugin entrypoint files and project-level agent guidance
