# HephAIstus Architecture

Version: 2.0
Date: 2026-08-19
Status: Product reset baseline

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
- library symbol references.

This is a runtime projection. It is not a required persisted `state.json` artifact.

### 1.3 Patch backend

Responsibilities:

- validate LLM-produced patch plans;
- convert plans into explicit operations;
- maintain mutation history;
- support dry-run and rollback;
- enforce preview-before-apply semantics.

The backend must reject unrecognized or unsafe operations.

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

## 8. Open technical gates

The architecture can proceed once these gates pass:

- schematic round-trip fidelity;
- deterministic patch operation coverage;
- fixture-level ERC integration;
- simulation output capture;
- safe file conflict handling.
