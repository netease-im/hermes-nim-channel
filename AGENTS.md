<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so `openspec update` can refresh the instructions.
<!-- OPENSPEC:END -->

## Project Identity

- This repository is the Hermes Agent NIM platform plugin project.
- Host project: `hermes-agent` (`https://github.com/NousResearch/hermes-agent`)
- Goal: enable Hermes Agent to send and receive messages through the NetEase Yunxin NIM SDK.
- NIM reference implementation: `openclaw-nim-channel`
- Local reference path: keep a private checkout of `openclaw-nim-channel` outside this repository when parity checks are needed.
- Functional target: keep this project aligned with the capabilities already implemented in `openclaw-nim-channel`, as long as Hermes exposes equivalent plugin hooks.

## Working Rules

- Check the corresponding implementation in `openclaw-nim-channel` before changing NIM behavior here.
- Prefer the Hermes plugin path (`plugin.yaml`, `adapter.py`, `__init__.py`) instead of vendoring Hermes core files.
- Keep Hermes-facing orchestration in Python and NIM SDK-specific transport logic in the Node bridge.
- Do not reintroduce a top-level local Python package named `gateway`; it collides with Hermes core imports when the plugin is loaded.

## SDD Workflow

- This project uses the global `openspec` CLI with the `spec-driven` schema configured in `openspec/config.yaml`.
- Use `./scripts/sdd` as the default entrypoint for OpenSpec operations inside this repository.
- For requirement-bearing work, create or update the corresponding change artifacts before editing implementation code.
- Run validation with `./scripts/sdd validate <change-name>` before considering a change ready.
