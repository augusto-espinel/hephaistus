# HephAIstus Architecture

Version: 2.1
Date: 2026-08-20
Status: Implementation progress

## Architectural summary

HephAIstus is organized into four primary layers:

1. **Deterministic backend** — file parsing, patch validation, KiCad CLI calls, and simulation execution.
2. **LLM orchestration** — context selection, prompt construction, patch planning, and response synthesis.
3. **Companion UI** — chat, context, previews, apply/revert, and simulation history.
4. **Future KiCad adapter** — optional IPC/plugin integration when schematic APIs mature.

## Component map

```text
KiCad project files
   ↓
File adapter + parser
   ↓
Schematic graph / derived state
   ↓
Context service
   ↓
LLM orchestrator
   ↓
Patch plan
   ↓
Deterministic patch backend
   ↓
Validation (parse + ERC + simulation)
   ↓
Results/context back to chat
```

## 1. Deterministic backend

### 1.1 KiCad file adapter

Responsibilities:

- locate project files;
- parse `.kicad_sch` hierarchies;
- construct an in-memory circuit graph;
- preserve and re-emit schematic format details;
- write mutations atomically where possible;
- detect file freshness/conflicts.

Candidate libraries:

- `kicad-sch-api` for schematic-level operations;
- `kiutils` as a lower-level S-expression fallback;
- custom normalization layer for stable internal structures.

The adapter must not expose raw S-expressions as the main reasoning interface.

### 1.2 Schematic graph

Derived state should include:

- components;
- symbol properties;
- pins and pin UUIDs;
- nets;
- net memberships;
- wires, buses, junctions;
- labels/global/hierarchical labels;
- power symbols;
- sheet paths and instances;
- library symbol references;
- **net coverage** — multiple disjoint stub islands per net name (labels aggregate, not last-wins).

This is a runtime projection. It is not a required persisted `state.json` artifact.

**Implementation note:** The parser now correctly accumulates net coverage across same-name labels, enabling multiple disjoint stub islands per net name. This was a critical fix for stub-based restructuring.

### 1.3 Patch backend

Responsibilities:

- validate LLM-produced patch plans;
- convert plans into explicit operations;
- maintain mutation history;
- support dry-run and rollback;
- enforce preview-before-apply semantics.

The backend must reject unrecognized or unsafe operations.

**Implemented:** Stub-based net restructuring is fully implemented (commit `30414da`). The apply flow handles:

- **Series insertions** — expressed as pin net re-assignments in JSON state (e.g., `R2.2: dc_plus → dc_plus_shunt`)
- **Net cleanup** — when a net loses member pins, ALL wires/junctions/labels are stripped via kiutils island BFS
- **Stub attachment** — every former member pin gets a stub carrying its NEW net name
- **Power symbol anchoring** — power symbols anchor their nets; move attempts are rejected with warning
- **Library embedding** — missing libId symbols are auto-embedded from installed KiCad libraries via sym-lib-table resolution

Validation includes kicad-cli ERC runs confirming zero new violations against fixture baselines.

### 1.4 KiCad CLI adapter

Responsibilities:

- schematic ERC;
- netlist export;
- version detection;
- normalized command construction;
- machine-readable report parsing where supported.

Expected commands include:

```bash
kicad-cli sch erc <file.kicad_sch>
kicad-cli sch export netlist --format spice <file.kicad_sch>
```

### 1.5 Simulation adapter

Responsibilities:

- export or construct netlists;
- run ngspice/PySpice;
- capture stdout/stderr;
- store runtime metadata;
- parse waveform/raw output;
- compare runs;
- present logs and results to the companion UI.

HephAIstus should own the simulation run when it expects to answer questions about results. Reading KiCad GUI output as pixels should be a fallback, not the primary integration.

**Implemented (2026-08-20):**

- `hephaistus_simulation.parser` — ngspice console output, DC operating points, raw waveform parsing
- `hephaistus_simulation.run_metadata` — simulation run tracking with schematic hash correlation
- `hephaistus_simulation.context` — LLM context assembly from schematic + simulation
- `hephaistus_simulation.waveform` — waveform post-processing with trend detection, settling time, overshoot calculation
- CLI commands for parsing and context assembly
- Test fixtures for console, op, and raw output formats

**Context efficiency:**

Waveforms are summarized to minimize token usage:
- Summary stats: min, max, mean, std, initial, final
- Trend detection: settling, oscillating, rising, falling, stable
- Key points: final N points, initial N points, peaks, zero crossings
- Configurable limits: max_raw_points, max_signals
- LLM guidance for efficient simulation setup included in context

### 1.6 Simulation parameter management

Responsibilities:

- Manage SPICE simulation directives (`.tran`, `.ac`, `.dc`, `.op`, `.options`) in KiCad schematics
- Apply parameter changes via patch-plan operations
- Support text-level editing to preserve KiCad formatting

**Implemented (2026-08-20):**

- `hephaistus_circuit.simulation_directive` — Parse and manage simulation directives
- Patch-plan operations: `simulation.set_directive`, `simulation.remove_directive`
- Text application: Create, update, remove text elements for directives
- Parameter parsing: `tran`, `ac`, `dc`, `op`, `options`, `param`, `model`, `include`

**Workflow:**

1. LLM proposes parameter changes via patch-plan
2. Backend validates and applies changes to schematic
3. User triggers simulation in KiCad/ngspice
4. Simulation results are parsed and presented to LLM

**Example patch-plan:**

```json
{
  "type": "simulation.set_directive",
  "directive": "tran",
  "parameters": {"step": "1u", "stop": "10m"}
}
```

## 2. LLM orchestration

### 2.1 Context service

Builds a compact engineering context from:

- active schematic/project;
- selected or requested components/nets;
- parser diagnostics;
- ERC output;
- simulation settings and logs;
- recent runs;
- patch/audit history;
- optional screenshots or user notes.

The context service should rank sources and avoid overwhelming the model with entire files when summaries suffice.

### 2.2 Prompt contracts

The LLM receives:

- user request;
- relevant structured context;
- supported operation list;
- validation requirements;
- safety boundaries.

For mutation requests, the model should return a structured patch plan constrained by the backend schema.

### 2.3 Plan validation

Plans must pass:

- schema validation;
- existence checks;
- permission checks;
- semantic connectivity checks;
- file freshness checks.

Only validated plans may be presented as applyable.

## 3. Companion UI

### 3.1 Suggested host

Preferred near-term host: PySide6/Qt desktop companion window.

Alternatives:

- local web UI served by the backend;
- Tauri/Electron shell;
- archived VS Code extension prototype as reference only.

### 3.2 Panels

Minimum panels:

- Chat;
- Project/context status;
- Patch preview;
- Simulation runs;
- Logs;
- Audit/history.

### 3.3 UX rules

- Ask mode must not mutate.
- Act mode must show preview.
- Apply requires explicit confirmation.
- Failed validation must explain why.
- Backend file freshness must be visible.

## 4. Future KiCad adapter

The IPC/plugin route should remain optional.

Known integration posture:

- KiCad 9/10 IPC support is still centered on the PCB editor;
- schematic IPC support is future work;
- plugin actions are possible, but not enough to assume an embedded schematic panel today.

When schematic IPC matures, an adapter can provide:

- current-document awareness;
- selection awareness;
- simulation window state;
- embedded launch surface.

This adapter should consume the same backend; it must not become a parallel mutation engine.

## 5. Safety architecture

### 5.1 File safety

- never mutate without a validated plan and user confirmation;
- create backups or git-aware snapshots for schematic changes;
- check live KiCad unsaved-state conflicts;
- use atomic writes where practical.

### 5.2 LLM safety

- LLM cannot directly write schematic files;
- hallucinated components/nets must fail validation;
- destructive operations require explicit human confirmation;
- all applied changes enter the audit log.

### 5.3 Simulation safety

- simulation parameter changes are still patches;
- convergence failures should be treated as diagnostics, not hidden;
- result comparisons should be shown with run metadata.

## 6. Data flow examples

### Ask a schematic question

1. Companion UI sends request to orchestrator.
2. Context service loads active schematic graph and relevant excerpts.
3. LLM explains using components/nets from the graph.
4. No mutation occurs.

### Apply simulation parameter change

1. User asks for a different transient configuration.
2. LLM returns a structured simulation patch plan.
3. Backend validates it.
4. Companion shows preview.
5. User applies.
6. Simulation adapter reruns and stores output.
7. Chat shows convergence/log/result summary.

### Apply schematic topology change

1. User asks for a shunt/load/snubber insertion.
2. LLM proposes a stub-based patch plan.
3. Backend validates component/net references.
4. Companion shows affected pins/nets and validation plan.
5. User applies.
6. File adapter writes, re-parses, runs ERC, and optionally exports/simulates.
7. Chat reports result and rollback path.

## 7. Implementation sequence

### Phase 1 — Product grounding

- this document set;
- preserved legacy archive;
- clean feature branch.

### Phase 2 — Schematic round trip

- parse fixture;
- apply one stub patch;
- write/re-parse;
- run ERC.

### Phase 3 — Simulation context

- export SPICE netlist;
- run ngspice/PySpice;
- capture logs and waveform data.

### Phase 4 — Companion UI

- ask mode;
- patch preview;
- simulation history.

### Phase 5 — Optional IPC integration

- launch companion from KiCad;
- add current-document/selection context when APIs permit.

## 8. Implementation milestones

### Completed

- **KiCad ingestion (2026-07-18):** Extension activation, file watcher, Python/KiUtils path resolution, KiCad 10 parsing, JSON state generation. Tested with `rectifier.kicad_sch` (9 components, 5 nets).
- **Stub-based net restructuring (2026-08-04):** Apply flow rebuilt around stubs (wire + net label). 26/26 tests passing covering: no-op, series insertion, chained splits, parallel additions, RL chain with Device:L embedding, duplicate-UUID abort. kicad-cli ERC confirms zero new violations vs fixture baseline.
- **Simulation output parsing (2026-08-20):** Ngspice console output, DC operating points, and raw waveform parsing. Run metadata with schematic hash correlation. LLM context assembly from schematic + simulation state.

### In progress

- Simulation parameter management (patch-plan extension)
- Companion chat UI

### Future

- Optional KiCad IPC adapter when schematic support matures

## 9. Open technical gates

The architecture can proceed once these gates pass:

- ~~schematic round-trip fidelity~~ ✅ (validated via ERC)
- ~~deterministic patch operation coverage~~ ✅ (stub-based operations)
- ~~fixture-level ERC integration~~ ✅ (kicad-cli ERC runs)
- simulation output capture;
- safe file conflict handling.
