# HephAIstus Use Cases Blueprint

Version: 2.1
Date: 2026-08-20
Status: Implementation progress

## Purpose

This blueprint turns Augusto's actual LLM-assisted electronics workflow into product use cases. It emphasizes eliminating manual copy/paste while preserving human approval for design changes.

## Use case families

### UC-01: Explain schematic behavior

**User prompt**

"Explain what this rectifier/filter stage does."

**Context used**

- schematic graph;
- component values;
- net topology;
- datasheet/model metadata if available;
- prior simulation results when referenced.

**Expected result**

A focused explanation naming concrete symbols and nets, with no file mutation.

---

### UC-02: Diagnose wiring/connectivity mistakes

**User prompt**

"Why is my three-level rectifier connection wrong?"

**Context used**

- pin/net memberships;
- labels and power symbols;
- ERC output;
- unconnected or inconsistent stubs;
- recent patch history.

**Expected result**

A diagnosis that identifies the problematic component pins/nets and proposes a patch plan if requested.

---

### UC-03: Tune simulation parameters

**User prompt**

"This transient simulation is failing to converge. What should I change?"

**Context used**

- simulation deck/settings;
- ngspice stdout/stderr;
- convergence errors;
- waveform data if present.

**Expected result**

Suggested parameter changes presented as a simulation patch preview, then optional rerun.

---

### UC-04: Interpret simulator console output

**User prompt**

"Why did ngspice fail after this timestep change?"

**Context used**

- captured console output;
- deck settings;
- simulation run metadata;
- previous successful/failed runs.

**Expected result**

An explanation grounded in normalized simulator logs, not copy/pasted console text.

---

### UC-05: Compare simulation runs

**User prompt**

"What changed after increasing the damping resistance?"

**Context used**

- two run records;
- parameter deltas;
- waveform summaries;
- pass/fail status.

**Expected result**

Comparison of parameter and waveform changes with relevant metrics.

---

### UC-06: Suggest implementation approaches

**User prompt**

"What is a good way to implement a constant-power load here?"

**Context used**

- target net/schematic topology;
- available component/model patterns;
- simulation objectives.

**Expected result**

A recommendation plus a previewable schematic/simulation recipe if the user requests implementation.

---

### UC-07: Insert a measurement shunt

**User prompt**

"Insert a small current shunt between C1 and R2."

**Context used**

- net topology;
- pin assignments;
- affected component terminals.

**Expected result**

A stub-based patch plan that splits the net, introduces the shunt, re-parses, and validates via ERC.

**Implementation status:** ✅ **Implemented** (2026-08-04). Stub-based restructuring supports series insertions, chained splits, parallel additions, and library symbol embedding. 26/26 tests passing. kicad-cli ERC confirms zero new violations vs fixture baseline.

---

### UC-08: Add or modify a simulation model

**User prompt**

"Model this output as a constant-power load."

**Context used**

- selected output/net;
- SPICE-compatible subcircuit or behavioral model;
- simulation recipe.

**Expected result**

A patch that can update schematic/model references or simulation-side model injection, depending on the product stage.

---

### UC-09: Patch preview and safe apply

**User prompt**

"Show me exactly what will change before applying."

**Expected result**

A patch card listing affected symbols, pins, nets, model files, and simulation settings, with dry-run/validation metadata.

---

### UC-10: Rollback and audit

**User prompt**

"The last change made things worse. Undo it."

**Expected result**

A rollback path based on the audit record and, where possible, restored project state plus validation rerun.

## Prioritized milestone use cases

### Milestone 1: Context Copilot

- UC-01 explain schematic behavior;
- UC-02 diagnose connectivity mistakes;
- UC-04 interpret console output;
- UC-05 compare simulation runs.

No mutation required.

### Milestone 2: Simulation Agent

- UC-03 tune simulation parameters;
- UC-06 suggest implementation approaches;
- UC-08 add/modify simulation model.

Simulation patches may be applied after preview.

### Milestone 3: Schematic Agent

- UC-07 insert a measurement shunt — ✅ **Implemented** (stub-based restructuring)
- UC-09 patch preview/apply — partial (apply validated, preview UI pending)
- UC-10 rollback/audit — not yet implemented

Schematic mutations use the stub-based apply flow and validation gates.

## Quality criteria

For each use case, success means:

- no manual copy/paste of schematic files;
- no manual copy/paste of simulator output;
- concrete component/net/parameter references in responses;
- deterministic validation before apply;
- auditability after apply.
