# HephAIstus Context

Last updated: 2026-08-19

## Project

HephAIstus is being rebuilt as an AI-assisted KiCad schematic and simulation copilot.

The new product target is a companion window beside KiCad. It reads schematic files, simulation results, validation reports, and console output directly; answers questions in context; and applies previewable, validated changes.

This avoids the current copy/paste workflow where schematics, screenshots, raw outputs, and logs are manually moved into an external chat.

## Repository reset

On 2026-08-19, the VS Code extension prototype was archived and the product reset was started.

- Archive branch: `archive/vscode-prototype`
- Archive tag: `vscode-prototype-2026-08-19`
- Reset branch: `feature/companion-reset`
- Suggested local legacy worktree: `../hephaistus-legacy`

The old implementation remains available for reference but is not part of the new build surface.

## Current architectural stance

- **Schematic is the source of truth.** The circuit graph/state is derived from KiCad files at runtime.
- **Backend is deterministic.** LLM output must be validated and converted into explicit patch operations.
- **UI is a companion application.** A docked KiCad panel is a future option once schematic IPC support matures.
- **Use KiCad-native tools.** Prefer `kicad-cli` for ERC/netlist export and native file parsers for `.kicad_sch` mutation.
- **Simulation output is first-class context.** HephAIstus should own simulation runs and capture raw waveforms, stdout/stderr, and convergence diagnostics.

## Implementation priorities

1. Product specification and architecture grounding.
2. Schematic round-trip proof of concept.
3. Deterministic backend package.
4. Simulation context pipeline.
5. Companion chat UI.
6. Optional future KiCad IPC adapter.
