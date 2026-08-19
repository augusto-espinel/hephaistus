# Migration from the VS Code Prototype

Date: 2026-08-19
Branch: `feature/companion-reset`

## Purpose

This document records how the original VS Code extension prototype was archived and what the new `feature/companion-reset` branch is meant to preserve, abandon, or replace.

## Archive

The old implementation was preserved before the reset:

- Branch: `archive/vscode-prototype`
- Tag: `vscode-prototype-2026-08-19`
- Suggested local worktree: `../hephaistus-legacy`

These references allow the old code and docs to be inspected without polluting the new branch.

## Why the reset happened

The product target changed from a VS Code-hosted extension to a KiCad schematic/simulation copilot. The new target requires:

- a companion UI beside KiCad;
- deterministic KiCad/simulation context;
- previewable AI actions;
- reduced dependency on a VS Code extension host;
- no persisted JSON state as the architectural source of truth.

## What is preserved

- fixture material for schematic parsing and round-trip experiments;
- decoupled collaboration between human schematic control and AI-assisted optimization;
- stub-based schematic restructuring semantics;
- emphasis on deterministic validation;
- the idea that LLM output must become structured patches before mutation.

## What is abandoned

- VS Code extension as the product endpoint;
- VS Code file watcher and sync panel as final UX;
- mandatory `state.json` product ledger;
- old extension browser/webview architecture;
- extension packaging/build tooling.

## What is replaced

| Old concept | New concept |
|---|---|
| VS Code extension | Companion desktop application |
| `state.json` product ledger | Runtime derived circuit graph |
| LLM bridge in extension | Orchestration service |
| KiCad file watcher in VS Code | Companion/backend project watcher |
| Manual UI patches | Previewable patch cards |
| Simulation module placeholder | First-class simulation adapter |
| IPC speculation | Optional future KiCad adapter |

## Lessons carried forward

1. **Round-trip fidelity is the critical gate.** KiCad schematic mutation must preserve format details, UUIDs, instances, library symbols, and hierarchy semantics.
2. **Stub-based restructuring is still the right mutation pattern.** It avoids geometric layout changes while allowing topology edits.
3. **Validation must be deterministic.** The LLM cannot be trusted to rewrite files directly.
4. **Simulation output must be captured by the backend.** Screenshots and copied console output are fallback context, not authoritative data.
5. **The product value is the loop.** Ingest context, explain/diagnose, propose, preview, apply, validate, and compare.

## Branch hygiene guidance

- Do not copy old files into an untracked `_reference/` folder inside this repo.
- Use the archive branch/tag or legacy worktree instead.
- New implementation should be introduced deliberately from the new architecture documents.
- If an old module is revived, port it explicitly and document why it is still valid.
