# HephAIstus Context

Last updated: 2026-08-20

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

## Implementation progress

### Completed

1. **KiCad ingestion (2026-07-18):** Extension activation, file watcher, Python/KiUtils path resolution, KiCad 10 parsing, JSON state generation. Tested with `rectifier.kicad_sch` (9 components, 5 nets).

2. **Stub-based net restructuring (2026-08-04, commit `30414da`):**
   - Series insertions expressed as pin net re-assignments in JSON state
   - Net cleanup: ALL wires/junctions/labels stripped when net loses member pins (kiutils island BFS)
   - Stub attachment: every former member pin gets stub with new net name
   - Power symbol anchoring: moves rejected with warning
   - Library embedding: auto-embed from sym-lib-table resolution
   - Instance format fix: new components emit proper `(pin N (uuid ...))` and `(instances ...)` blocks
   - Net coverage fix: multiple disjoint stub islands per net name supported
   - **Test status:** 26/26 tests passing (no-op, series insertion, chained splits, parallel additions, RL chain with Device:L embedding, duplicate-UUID abort)
   - **Validation:** kicad-cli ERC confirms zero new violations vs fixture baseline

### In progress

3. Deterministic backend package — core operations implemented, extending coverage

4. **Simulation context pipeline (2026-08-20 — in progress)**
   - `backend/hephaistus_simulation/` — new module
   - Console output parsing (analyses, convergence, warnings, errors) ✅
   - DC operating points extraction ✅
   - Raw waveform parsing ✅
   - Run metadata with schematic correlation ✅
   - LLM context assembly ✅
   - CLI commands for testing ✅
   - Test fixtures in `fixtures/simulation/` ✅

5. Companion chat UI

### Future

6. Optional KiCad IPC adapter when schematic support matures

## Key technical decisions

### Stub-based restructuring (2026-08-04)

The apply flow was rebuilt around stubs (wire + net label) instead of physical wire-breaking advice:

- **AI contract:** series insertions / re-wiring are expressed purely as pin net re-assignments in the JSON state
- **Apply semantics:** when a net loses member pins, ALL its wires/junctions/labels are stripped, then every former member pin gets a stub carrying its NEW net name
- **Power symbols:** anchor their nets (move = rejected with warning)
- **Library embedding:** missing libId symbols are auto-embedded from installed KiCad libraries

This preserves user geometry and avoids complex wire surgery operations.
