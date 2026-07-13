## Context

Hermes recommends shipping third-party messaging integrations as plugins. At the same time, the NIM behavior we want already exists in `openclaw-nim-channel`, which is implemented against a different host API. This repository therefore needs a plugin-compatible layout for Hermes, while keeping the Python/Node split that matches the available NIM SDK.

## Goals / Non-Goals

**Goals:**
- Provide a Hermes-compatible `nim` plugin entry point
- Resolve credentials and policy controls from Hermes-style config and environment variables
- Keep direct SDK calls inside a dedicated Node bridge
- Support inbound direct messages, mention-gated team messages, and outbound text sends
- Make bridge failures observable through a structured JSONL protocol
- Establish `openclaw-nim-channel` as the implementation baseline for later parity work

**Non-Goals:**
- Rebuild the full Hermes core repository inside this project
- Implement every Hermes routing hook or every NIM media operation in the first iteration
- Ship deployment automation or packaging to PyPI/npm in this change

## Decisions

### 1. Python adapter + Node bridge

Decision: split the implementation into a Python adapter and a Node subprocess bridge.

Rationale:
- Hermes platform adapters are Python-oriented in the official documentation.
- The available NIM Bot SDK and proven reference code are Node-based.
- JSONL over stdio keeps the integration simple, observable, and easy to mock in tests.

Alternative considered:
- Pure Python NIM client: rejected because no maintained equivalent to `@yxim/nim-bot` is available in this workflow.

### 2. Use Hermes plugin entrypoints and an internal package

Decision: expose the plugin at the repository root with `plugin.yaml`, `adapter.py`, and `__init__.py`, while keeping testable local code under `hermes_nim_channel/`.

Rationale:
- The layout matches Hermes' documented plugin path.
- A private package name avoids collisions with Hermes core modules such as `gateway`.
- Local compatibility helpers keep the repository testable without vendoring the full Hermes source tree.

Alternative considered:
- Keep a top-level local `gateway/` package: rejected because it can shadow Hermes core imports when the plugin is loaded.

### 3. Conservative group-chat behavior

Decision: only process group/team messages when the bot is mentioned and the team passes the configured policy.

Rationale:
- Hermes' Feishu integration defaults to explicit group control.
- The NIM reference implementation already treats `forcePushAccountIds` as the mention signal.
- This reduces accidental agent activation in busy shared groups.

### 4. Text-first bridge surface

Decision: implement bridge commands for connect, disconnect, health, and text send in the first iteration.

Rationale:
- Text paths are the minimum required to validate end-to-end message flow.
- The JSONL command schema stays extensible for media sends later.

## Risks / Trade-offs

- Bridge process drift from Hermes core expectations -> Keep the adapter contract small and file layout upstream-friendly
- SDK API differences across `@yxim/nim-bot` versions -> Reuse the same service names and login flow already proven in the internal TypeScript reference
- No live SDK verification in this environment -> Cover parsing and policy logic with local tests and document the remaining integration gap

## Migration Plan

1. Configure NIM credentials in Hermes platform config or environment variables.
2. Install bridge dependencies with `npm install` inside `bridge/`.
3. Install or copy the plugin directory into Hermes' plugin path.
4. Start Hermes and validate DM plus mention-gated team flows.
5. If rollout fails, disable the `nim` platform and stop the bridge process; no persistent migration is required.

## Open Questions

- How Hermes capability concepts should map to the broader `openclaw-nim-channel` surface, especially QChat and media behavior
- Whether future iterations should expose media uploads through the same bridge protocol or a separate transfer helper
