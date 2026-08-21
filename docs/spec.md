# HephAIstus Product Specification

Version: 2.1
Date: 2026-08-20
Status: Implementation progress

## 1. Scope

HephAIstus provides AI-assisted schematic design and simulation workflows for KiCad projects.

The product consists of:

1. a deterministic backend for KiCad file, validation, and simulation operations;
2. an LLM orchestration layer for context assembly and patch planning;
3. a companion desktop UI for chat, preview, apply, and result inspection;
4. optional future KiCad IPC/plugin adapters.

## 2. User roles

### Primary user

An electronics engineer working in KiCad who wants AI assistance without losing control of schematic geometry, simulation setup, or acceptance decisions.

### Secondary user

A developer/tester running HephAIstus in headless validation or CI contexts.

## 3. Supported workflows

### 3.1 Ask mode

The user asks a question without authorizing a mutation.

Examples:

- Explain a schematic section.
- Diagnose a wiring mistake.
- Interpret ERC output.
- Interpret simulation convergence failure.
- Compare two simulation runs.
- Explain a waveform anomaly.
- Suggest a component or topology approach.

Expected behavior:

- use relevant schematic/simulation context;
- cite concrete components, nets, parameters, or logs;
- avoid mutating files;
- optionally propose a previewable action.

### 3.2 Act mode

The user requests a change.

Examples:

- change simulation parameters;
- insert a shunt or damping element;
- split/rename a net;
- add a constant-power load model;
- rerun a simulation;
- apply a previously proposed schematic patch.

Expected behavior:

- translate the request into a structured patch plan;
- validate the plan;
- show an actionable preview;
- apply only after user confirmation;
- re-run validation and/or simulation;
- report the result and retain rollback metadata.

## 4. Context sources

The backend should progressively support these inputs:

### Schematic project

- root `.kicad_sch`
- hierarchical sheets
- symbols and properties
- wires, buses, labels, power symbols, junctions
- project libraries
- schematic version/generator metadata

### Project-scoped session

- `.hephaistus/session.json` — Session state persisted in project directory
- `.hephaistus/history.db` — Project-scoped conversation history (SQLite/FTS5)
- `.hephaistus/simulations/` — Simulation run metadata and results
- Auto-discovery of project root from schematic path
- Session survives server restarts

### Validation

- `kicad-cli sch erc` output
- parser diagnostics
- semantic graph validation

### Simulation

- exported netlists
- simulation decks/settings
- simulator stdout/stderr
- convergence messages
- waveform/raw data
- prior run metadata

### Optional UI context

- user-selected component/net names entered manually
- project tree metadata
- screenshot/image attachments as non-authoritative context

## 5. Patch model

Patches must be explicit and reviewable.

A patch plan should contain:

- human-readable intent;
- operation type;
- target schematic/project;
- affected symbols, pins, nets, labels, or simulation settings;
- validation requirements;
- safety/risk notes;
- reversible representation when possible.

The orchestration layer must reject plans that cannot be mapped to deterministic backend operations.

## 6. Schematic mutation policy

The backend uses **stub-based restructuring** semantics (implemented 2026-08-04):

- **Series insertions** are expressed as pin net re-assignments (e.g., `R2.2: dc_plus → dc_plus_shunt`)
- **Net cleanup** — when a net loses member pins, ALL wires/junctions/labels are stripped via kiutils island BFS
- **Stub attachment** — every former member pin gets a stub (wire + net label) carrying its NEW net name
- **Power symbols** anchor their nets; move attempts are rejected with warning
- **Library embedding** — missing libId symbols are auto-embedded from installed KiCad libraries via sym-lib-table resolution
- **UUID preservation** — instances and pin UUIDs are preserved; new components emit proper `(pin N (uuid ...))` and `(instances ...)` blocks
- **Net coverage** — multiple disjoint stub islands per net name are supported (labels aggregate, not last-wins)

This approach preserves user geometry where possible and avoids physical wire-breaking operations.

## 7. Validation gates

Before accepting a mutation:

- plan must be structurally valid;
- referenced components/nets must exist;
- target file must be available and not conflicting with an unsaved live editor state;
- patch must use supported operation types.

After mutation:

- schematic must re-parse;
- ERC should be run when applicable;
- simulation should be rerun when requested;
- results must be stored with run metadata.

## 8. Companion UI requirements

The UI should provide:

- persistent chat pane;
- context source list;
- patch preview cards;
- apply/revert controls;
- simulation run history;
- waveform/log viewers;
- audit log;
- explicit indication of file freshness and active project.

## 9. Non-goals for initial implementation

Initial implementation does not require:

- an embedded KiCad dock panel;
- schematic selection awareness through IPC;
- PCB editing;
- arbitrary geometry auto-placement;
- silent autonomous schematic mutation;
- cloud-only execution.

## 10. Technology posture

Preferred near-term interfaces:

- `.kicad_sch` direct file parsing/mutation;
- `kicad-cli sch erc` for schematic validation;
- `kicad-cli sch export netlist --format spice` for simulation export;
- ngspice/PySpice for simulation execution;
- PySide/Qt or local web UI for the companion window;
- KiCad IPC/plugin as a future enhancement once schematic support is appropriate.

## 11. Implementation status

### Completed

- **KiCad ingestion (2026-07-18):** Extension activation, file watcher, Python/KiUtils path resolution, KiCad 10 parsing, JSON state generation.
- **Stub-based net restructuring (2026-08-04):** Full apply flow with 26/26 tests passing. Operations include: no-op, series insertion, chained splits, parallel additions, component embedding (Device:L), and duplicate-UUID abort. kicad-cli ERC validates zero new violations vs fixture baseline.
- **Session persistence (2026-08-21):** Project-scoped sessions in `.hephaistus/` directory. Auto-discovery of project root. Session state survives server restarts. Shared context service for LLM requests.

### In progress

- Simulation context pipeline
- Companion chat UI

## 12. Acceptance criteria

A milestone is complete only when it can answer questions or execute changes against retained fixture projects without manual copy/paste of schematic files, console output, or simulation result metadata.
