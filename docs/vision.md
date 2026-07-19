# HephAIstus Vision and Use Cases

*Captured 2026-07-15 — Reference for future development*

---

## The Core Problem

Analog/mixed-signal circuit design in KiCad is a **visual-spatial** discipline. The engineer thinks in terms of component placement, routing, topology — things that belong on a canvas. But optimizing that circuit — choosing the right resistor values, validating stability margins, tuning feedback loops — is a **mathematical-simulation** discipline. It belongs in code and numbers.

Today, these two worlds interact through a painful manual cycle: design in KiCad → export → write SPICE deck → simulate → interpret results → manually update KiCad → repeat. It's slow, error-prone, and breaks creative flow.

---

## Primary Use Cases

### 1. LLM-Guided Component Selection and Tuning

The engineer draws a schematic with placeholder or initial component values. They describe the optimization goal in natural language: "Make this LDO regulator more efficient while keeping output ripple under 20mV." The LLM proposes specific value changes (R1: 10kΩ → 4.7kΩ, C2: 100nF → 220nF), the engineer reviews the diff, approves, and the schematic updates automatically. The spatial layout is untouched — only values change.

### 2. Automated Simulation-Driven Validation

Once values are proposed, the tool doesn't just guess — it *runs the simulation*. SKiDL generates a netlist from the schematic state, ngspice executes it, and results feed back into the loop. The LLM can iteratively refine: "The transient simulation shows 35mV ripple, try increasing C2 to 470nF." This is a closed optimization loop, not a one-shot suggestion.

### 3. Schematic ↔ Simulation State Synchronization

The JSON ledger is the translation layer. When the engineer edits the schematic directly (adds a component, changes a value), the tool detects the change, updates the JSON state, and flags any Python simulation scripts as stale. When the LLM proposes a change, it flows back through the ledger to update the schematic. Bidirectional, with the human always in the loop for approval.

### 4. Incremental Design Exploration

The engineer doesn't need to start from a complete schematic. They can sketch a partial topology, ask the LLM to suggest missing components or alternative architectures, and iterate. The staging area for new components preserves layout integrity while adding parts that the engineer can then reposition.

### 5. Proactive Mistake Detection

The LLM can run a **review pass** on the schematic to detect issues before simulation:

- **Electrical rules:** Floating inputs, shorted outputs, missing decoupling
- **Design rules:** Voltage/current ratings, power dissipation
- **Best practices:** Bypass capacitors, proper grounding, stability margins
- **Topology errors:** Wrong amplifier configuration, missing feedback paths

Issues are presented with severity, explanation, and proposed fixes. The user chooses to accept, ignore, or learn more.

### 6. Structural Corrections (Add/Delete/Re-wire)

Beyond value changes, the LLM can propose structural modifications:

- **Add components:** Missing bypass capacitors, protection diodes
- **Delete components:** Redundant parallel resistors, unnecessary bypass paths
- **Re-wire connections:** Wrong net assignments, topology corrections

Re-wiring uses **stub connections** — logical connections that make the circuit simulatable while preserving user spatial control. The user sees the stub in KiCad and completes the physical wiring.

---

## Iterative Autonomy with Checkpoints

The LLM can **iterate through multiple simulation cycles** (troubleshoot, refine, retry) before interrupting the human. This is crucial: analog optimization often requires 5-10 simulation runs to converge, and you don't want to approve each one manually.

### Design Implications

- **Silence budget:** Configurable number of autonomous iterations (default N=3-5) before the human must acknowledge
- **Checkpoint/savepoint semantics:** Before the LLM proposes anything, the state is snapshotted. If the optimization diverges or the user aborts, they can revert to the last known-good state
- **Batch approval:** Like git rebase — you approve a *batch* of changes, not a single suggestion

---

## Multi-Audience Design

### Hobbyists

Need simplicity and defaults that "just work." They may not know what "phase margin" means, but they know their circuit oscillates and want help fixing it.

**Design:** Simple diff view, "Accept/Reject" buttons, sensible defaults, minimal configuration.

### Students

Need pedagogical transparency — not just "change R1 to 4.7kΩ" but "changing R1 from 10kΩ to 4.7kΩ increases the loop bandwidth, which improves transient response but reduces phase margin to 42°, which is still acceptable."

**Design:** Annotations explaining *why* each change was proposed, links to relevant theory, optional "learning mode" with expanded explanations.

### Professionals

Need control, visibility, and integration with existing workflows. They want to see the simulation waveforms, understand why the LLM made each decision, and export results to their existing toolchain.

**Design:** Advanced view with simulation plots, objective function traces, LLM reasoning logs, exportable reports, custom model configuration.

---

## Schematic Modification Permissions

The LLM can perform different types of modifications depending on user permission level. This ensures safety while allowing progressively more invasive corrections.

### Permission Levels

| Level | Operations Allowed | Use Case |
|-------|-------------------|----------|
| `values` | Modify component values only | Conservative, safe mode |
| `add` | Values + Add components to staging area | Missing components |
| `delete` | Values + Add + Mark for removal | Redundant components |
| `restructure` | All above + Add connection stubs | Topology corrections |

**Default:** `add` (values + staging area additions)

### Intent Expression

Before any structural change (add/delete/stub), the LLM must express intent:

1. **State the problem:** "The input capacitor C1 is missing, which will cause DC offset at the op-amp input"
2. **Propose the solution:** "Add a 100nF capacitor between VIN and ground at the staging area"
3. **Explain the impact:** "This will filter DC offsets. You'll need to position C1 near the input connector"
4. **Wait for approval:** User accepts/rejects/modifies

**Philosophy:** Minimum needed changes to achieve the goal. No speculative "improvements."

### Stub Connections for Re-wiring

When the LLM needs to change a net connection, it creates "stubs" — logical connections that make the circuit simulatable while preserving user spatial control.

**How it works:**

1. LLM identifies needed connection
2. Creates stub in JSON state (logical connection for simulation)
3. Marks it in KiCad (visual indicator)
4. Simulation proceeds with correct topology
5. User completes wiring in KiCad
6. Stub promotes to real connection on next sync

**Benefits:**

- Circuit becomes simulatable immediately
- User retains spatial control over wire routing
- Clear action items for manual completion
- Reversible via backup system

---

## Extensible EDA Backend

Starting with KiCad, but the architecture is deliberately CAD-agnostic. The JSON ledger pattern abstracts away the specific file format — each CAD tool needs an ingestion/sync module, but the optimization loop is independent.

### Future Targets

- **PLECS** — Power electronics simulation (thermal/electrical co-simulation)
- **GeckoCircuits** — Power electronics with SPICE backend
- **Altium/OrCAD/Eagle** — Commercial EDA tools

### Design Implication

The `kicad_sync` module should be abstracted to `cad_sync` with tool-specific adapters. The Python package structure (`hephaistus/cad_sync/`) anticipates this.

---

## Tiered Model Strategy

Not all tasks need frontier intelligence. The tool configures different model suppliers based on task complexity:

| Task | Model Tier | Reasoning |
|------|------------|-----------|
| JSON state sync | Local/cheap (Ollama, 3-8B) | Deterministic parsing, pattern matching |
| Ingestion fallback | Local/cheap | Same — KiCad→JSON is rule-based |
| Optimization proposal | Frontier (GLM, GPT-4, Claude) | Needs deep circuit understanding |
| Troubleshooting reasoning | Frontier | Needs domain knowledge and creativity |

### Design Implication

Configurable model routing:

```json
{
  "models": {
    "sync": {
      "provider": "ollama",
      "model": "llama3:8b",
      "endpoint": "http://localhost:11434"
    },
    "optimization": {
      "provider": "openrouter",
      "model": "google/gemini-2.5-flash"
    }
  }
}
```

---

## What's Novel

### 1. Decoupled Collaboration (Not Copilot Autocomplete)

Most "AI for EDA" tools try to autocomplete the schematic or generate everything from scratch. HephAIstus takes a fundamentally different stance: **the human owns the canvas, the AI owns the math**. This isn't about replacing the engineer's spatial judgment — it's about augmenting their mathematical reasoning. The geometry is immutable; only values and new parts (at a staging area) change.

### 2. The JSON Ledger as a Shared Mental Model

The `state.json` isn't just a cache — it's a **negotiated contract** between three parties: the human (schematic), the machine (LLM), and the simulator (Python). All three read and write through this ledger, with hash-based change detection ensuring no party gets out of sync. This is closer to collaborative software patterns (CRDTs, event sourcing) than traditional EDA tools.

### 3. Closed-Loop Optimization in the Editor

The tool doesn't just suggest — it *validates*. The LLM proposes, the simulator verifies, results feed back, and the loop repeats. This is "LLM as optimizer, SPICE as objective function." Most AI coding tools are open-loop (suggest and hope). HephAIstus closes the loop by running actual simulations inside VS Code.

### 4. Patch-Based Change Management

Changes aren't applied silently. Every LLM proposal is presented as a diff — a patch the engineer can inspect, accept, or reject. This is version-control thinking applied to circuit design. It creates an auditable trail of what the AI suggested and what the human approved.

---

## The Vision

**HephAIstus is a tiered-intelligence design partner that meets users where they are — hobbyist, student, or professional — and adapts its model usage to task complexity while keeping the human in control through checkpoints and transparent iteration.**

The "tiered intelligence" piece is important: cheap local models for deterministic tasks, frontier cloud models for creative optimization. This makes the tool economically viable for hobbyists and students while still powerful enough for professionals.

### Long-Term Direction

- **From one-shot optimization to continuous design assistance** — The tool watches as you design, flags potential issues proactively, and suggests improvements in real-time
- **From single-circuit to system-level optimization** — Managing tradeoffs across multiple subcircuits (power budget, thermal constraints, signal integrity)
- **From tool to design partner** — An agent that understands your design constraints, company standards, and past decisions, and proposes solutions consistent with your engineering culture