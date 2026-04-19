# Project Conventions

## Purpose

This repository hosts a standalone Hermes Agent extension for NetEase IM (NIM). It is intentionally smaller than the full Hermes core repository and focuses on a patch-ready adapter plus the bridge process required by the official NIM Bot SDK.

## Structure

- `gateway/`: Hermes-facing Python code
- `bridge/`: Node-based NIM Bot SDK integration
- `tests/`: Python unit tests
- `openspec/changes/`: active proposals and implementation checklists

## Development Rules

- Keep Hermes-facing behavior in Python.
- Keep SDK-specific logic inside the Node bridge.
- Prefer line-delimited JSON for Python/Node IPC to keep failures observable.
- Specs define behavior; implementation details belong in `design.md`.

