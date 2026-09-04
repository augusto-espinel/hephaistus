# Changelog

All notable changes to HephAIstus will be documented in this file.

## [2.3.0] - 2026-09-04

### Fixed
- **Critical: Y-coordinate inversion in pin position calculation.**
  - KiCad library symbols use Y-UP (Cartesian) coordinates, schematics use Y-DOWN (screen).
  - Pin positions were incorrectly calculated, causing swapped net assignments for IGBTs and other rotated components.
  - Fix: Negate Y when transforming from library to schematic space: `schematic_y = symbol_y - library_y`.

- **KiCad-compatible net naming for unnamed nets.**
  - Changed from synthetic names (`N$1`, `N$2`) to KiCad's `Net-(Ref-PadName)` convention.
  - Examples: `Net-(C1-Pad1)`, `Net-(B_gate3-N+)`.
  - Ensures parser output matches simulation logs and netlist exports for LLM cross-referencing.

- **Pin name extraction from library symbols.**
  - Pin data now includes the electrical name from the library (e.g., `C`, `G`, `E`, `Tc` for IGBTs).
  - Enables correct `Net-(Ref-PadName)` naming.

### Changed
- **Removed incorrect net-merge-through-components logic.**
  - KiCad's netlist model is wire-only; components don't merge wire islands.
  - Parser now faithfully reports wire connectivity without post-processing merges.

## [2.2.0] - 2026-08-24

### Added
- Stub-based net restructuring implementation (commit `30414da`).
- Power symbol anchoring — move attempts rejected with warning.
- Library embedding for missing libId symbols via sym-lib-table resolution.

### Fixed
- Net coverage accumulation — multiple same-name labels now aggregate (was last-wins).

## [2.1.0] - 2026-08-20

### Added
- Simulation output parsing module (`hephaistus_simulation`).
- Waveform post-processing with trend detection, settling time, overshoot calculation.
- Context assembly combining schematic state + simulation results.
- Session persistence in project directory (`.hephaistus/`).

## [2.0.0] - 2026-08-18

### Added
- FastAPI backend with `/parse`, `/generate`, `/apply` endpoints.
- React companion UI with chat interface.
- KiCad schematic parsing via kiutils.
- LLM orchestration with OpenRouter/Ollama support.
- Patch plan validation and apply workflow.
