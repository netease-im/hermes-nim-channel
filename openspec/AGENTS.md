# OpenSpec Notes

## Project Shape

- This repository is a Hermes platform plugin, not a fork of Hermes core.
- Root plugin entrypoints are `plugin.yaml`, `adapter.py`, and `__init__.py`.
- Local implementation code lives under `hermes_nim_channel/`.
- NIM SDK transport remains in `bridge/`.

## Spec Expectations

- Use `openclaw-nim-channel` as the baseline reference when writing or updating NIM capability specs.
- Record Hermes-specific adaptation decisions explicitly instead of implying OpenClaw behavior transfers unchanged.
- Avoid spec text that assumes a top-level local `gateway/` package or direct edits to Hermes core.
