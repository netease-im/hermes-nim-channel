# Project Conventions

## Purpose

This repository hosts a standalone Hermes Agent platform plugin for NetEase IM (NIM). It follows Hermes' plugin path and uses the existing `openclaw-nim-channel` implementation as the behavior baseline for future capability alignment.

## Structure

- `plugin.yaml`, `adapter.py`, `__init__.py`: Hermes plugin entrypoint files
- `hermes_nim_channel/`: local Python implementation package
- `bridge/`: Node-based NIM Bot SDK integration
- `tests/`: Python unit tests
- `openspec/changes/`: active proposals and implementation checklists

## Development Rules

- Prefer Hermes plugin entrypoints over copied Hermes core file paths.
- Keep Hermes-facing behavior in Python.
- Keep SDK-specific logic inside the Node bridge.
- Use `openclaw-nim-channel` as the first reference when adding or changing NIM capabilities.
- Prefer line-delimited JSON for Python/Node IPC to keep failures observable.
- Specs define behavior; implementation details belong in `design.md`.
