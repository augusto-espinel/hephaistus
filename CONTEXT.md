# HephAIstus Context

Last updated: 2026-08-22

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
   - **Test status:** 26/26 tests passing
   - **Validation:** kicad-cli ERC confirms zero new violations vs fixture baseline

3. **Session persistence (2026-08-21):**
   - Project-scoped sessions in `<project>/.hephaistus/`
   - Auto-discovery of project root from schematic path
   - Shared ContextService between API and LLM orchestrator
   - Session survives server restarts
   - API endpoints: `/api/session/status`, `/api/session/restore`

4. **Simulation ingestion pipeline (2026-08-22):**
   - CSV file parsing with waveform statistics
   - Console output parsing (ngspice format)
   - Analysis type detection (tran, ac, dc, op)
   - FIFO archive (keeps last 5 runs)
   - Staleness detection via schematic hash comparison
   - API endpoints: `/api/simulation/import`, `/api/simulation/state`

5. **SPICE library context (2026-08-22):**
   - Extract `Sim.Library` properties from components
   - Load complete .lib files (comments stripped)
   - Expose subcircuits and models to LLM context
   - Enable topology reasoning (antiparallel diode detection verified)

6. **LLM orchestration (2026-08-21):**
   - Unified provider interface (Ollama, OpenRouter)
   - Patch-plan JSON extraction from responses
   - Context assembly with token budget
   - History persistence to SQLite

### In progress

7. **Companion UI (Phase 4):** React + Tauri desktop app
   - Import Simulation Dialog
   - Session Status Panel
   - LLM Chat Interface
   - Patch Plan Review

### Future

8. Optional KiCad IPC adapter when schematic support matures

## Key technical decisions

### Stub-based restructuring (2026-08-04)

The apply flow was rebuilt around stubs (wire + net label) instead of physical wire-breaking advice:

- **AI contract:** series insertions / re-wiring are expressed purely as pin net re-assignments in the JSON state
- **Apply semantics:** when a net loses member pins, ALL its wires/junctions/labels are stripped, then every former member pin gets a stub carrying its NEW net name
- **Power symbols:** anchor their nets (move = rejected with warning)
- **Library embedding:** missing libId symbols are auto-embedded from installed KiCad libraries

This preserves user geometry and avoids complex wire surgery operations.
