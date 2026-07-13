# OpenSpec SDD Workflow

This project uses the global `openspec` CLI with the default `spec-driven` schema as the standard SDD workflow.

## Entry Points

- Direct CLI: `openspec ...`
- Project wrapper: `./scripts/sdd ...`

The wrapper keeps commands rooted in this repository and standardizes the most common flows.

## Standard Flow

1. Create a change directory.

```bash
./scripts/sdd new <change-name>
```

Example:

```bash
./scripts/sdd new add-qchat-support
```

2. Generate artifact-specific guidance before editing files.

```bash
./scripts/sdd instructions proposal <change-name>
./scripts/sdd instructions specs <change-name>
./scripts/sdd instructions design <change-name>
./scripts/sdd instructions tasks <change-name>
```

3. Write and maintain the four artifacts under `openspec/changes/<change-name>/`.

- `proposal.md`
- `specs/<capability>/spec.md`
- `design.md`
- `tasks.md`

4. Validate the change before implementation and again before merge.

```bash
./scripts/sdd validate <change-name>
./scripts/sdd status <change-name>
```

5. Implement from `tasks.md`, updating checkboxes as work is completed.

6. Archive the change after delivery.

```bash
./scripts/sdd archive <change-name>
```

## Project Rules

- Treat `openclaw-nim-channel` as the first behavioral reference for NIM capabilities.
- Document only the Hermes-specific adaptation surface when behavior differs from the reference plugin.
- Keep host/plugin concerns in root entrypoints, Python orchestration in `hermes_nim_channel/`, and NIM SDK transport in `bridge/`.
- Re-run validation whenever proposal/spec/design/tasks or requirement-bearing code changes.

## Useful Commands

```bash
./scripts/sdd list
./scripts/sdd show <change-name>
./scripts/sdd templates
./scripts/sdd workflow
```
