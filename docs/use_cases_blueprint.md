# HephAIstus: Use Cases Blueprint for LLM-Assisted Circuit Design

*Expanded 2026-07-23 — Grounding document for the next development phases.*

This document expands the persona-based use cases for HephAIstus. It is intentionally detailed because the next implementation phase is not just "wire the LLM to JSON"; it is **designing a safe collaboration protocol** between:

- the **human**, who owns KiCad geometry and physical wiring decisions;
- the **extension**, which synchronizes `.kicad_sch` ↔ JSON and guards destructive operations;
- the **LLM**, which proposes values, topology changes, simulation experiments, and manual wiring guidance;
- the **simulator**, which will eventually provide objective feedback through SKiDL/ngspice.

The current technical constraint that shapes every use case is:

> HephAIstus can already parse KiCad → JSON and apply useful JSON → KiCad deltas, but it cannot yet arbitrarily manipulate wires like a human routing on canvas. Therefore, the LLM must treat many topology changes as a combination of **machine-applied edits** plus **explicit human wiring advice**, then **remember that advice** and verify on the next parse whether the user completed it correctly.

---

## 1. Grounding Constraints

### 1.1 What the system can do programmatically today

From the current implementation and architecture docs, HephAIstus already supports:

- KiCad 10 parsing into JSON state with components, pins, nets, wires, and junctions.
- JSON → KiCad delta application for:
  - value changes;
  - component removal;
  - component addition using net labels and staging placement;
  - warning generation for cases that require manual user action.
- Sync state detection and a manual sync panel.
- Preservation of existing geometry when applying supported deltas.

### 1.2 What the system should not pretend it can do yet

The system should not claim that it can fully reroute a schematic autonomously.

Current practical limits:

- Arbitrary wire creation, deletion, rerouting, and cleanup are not reliably programmatic.
- Series insertion into an existing wire often requires the user to break a wire and place labels.
- New components can be placed at a staging location with labels, but final placement and routing belong to the user.
- Some "obvious" electrical changes are geometrically ambiguous on canvas and must be expressed as advice, not silent edits.

### 1.3 Design consequence

Every non-trivial LLM optimization must produce **three coordinated outputs**:

1. **Patch** — machine-appliable changes to JSON/KiCad/Python simulation inputs.
2. **Advice** — human-readable instructions and checklist items for manual schematic work.
3. **Verification plan** — concrete assertions the extension can check after the next KiCad parse.

If one of these outputs is missing, the workflow is incomplete.

---

## 2. Core Interaction Model

### 2.1 The loop

The canonical HephAIstus loop is:

```text
Parse KiCad → JSON
    ↓
User states goal or accepts review prompt
    ↓
LLM proposes: patch + advice + verification plan
    ↓
Extension applies allowed machine edits and shows manual actions
    ↓
User edits KiCad manually where required
    ↓
User saves schematic
    ↓
Parse KiCad → JSON again
    ↓
Extension verifies expected changes and resolves or escalates advice
    ↓
LLM continues optimization using verified state
```

### 2.2 The key state objects

The extension should treat LLM output as structured data, not as free-form prose. Prose is for the chat window; structured blocks are for state transitions.

#### `OptimizationProposal`

Top-level object returned by the optimization model.

```json
{
  "proposal_id": "prop_20260723_001",
  "goal": "Reduce output ripple below 20mV without dropping efficiency more than 2%",
  "permission_level_required": "add",
  "checkpoint": {
    "create_backup": true,
    "reason": "Value and component additions before simulation"
  },
  "patch": {},
  "advice": [],
  "verification": [],
  "simulation_plan": []
}
```

#### `patch`

Machine-appliable changes only. The extension may apply these if the current permission level allows them.

Examples:

- change `R1.value` from `10k` to `4.7k`;
- remove redundant `R7`;
- add `Cbulk` at staging with net labels `VIN` and `GND`;
- update a Python/SKiDL simulation parameter;
- mark a component as excluded from simulation.

The patch must **not** include instructions like "move this wire". That belongs in `advice`.

#### `advice[]`

Human-executed or human-confirmed actions. These are displayed in the chat/webview and stored so they survive the next parse.

```json
{
  "advice_id": "adv_001",
  "kind": "manual_wiring",
  "title": "Break VIN wire and insert Cbulk in series path",
  "detail": "Place one Cbulk pin label on VIN upstream of the switch node and the other on GND near the input connector.",
  "severity": "required",
  "linked_patch_operations": ["add_component:Cbulk"],
  "expected_evidence": [
    "component_exists:Cbulk",
    "pin_net_equals:Cbulk.1=VIN",
    "pin_net_equals:Cbulk.2=GND"
  ],
  "status": "pending_user"
}
```

Advice kinds:

- `manual_wiring` — connect, break, reroute, label, or clean up wires.
- `placement` — move staged component near its electrical peers.
- `inspection` — check datasheet, layout constraint, polarity, thermal path.
- `simulation_setup` — adjust source type, load, initial conditions, probe points.
- `documentation` — add notes or design rationale to schematic or project docs.
- `confirmation` — user must confirm an assumption before the LLM proceeds.

#### `verification[]`

Checks the extension or Python bridge can run after parsing.

```json
{
  "check_id": "ver_001",
  "type": "pin_net_equals",
  "subject": "Cbulk.1",
  "expected": "VIN",
  "on_fail": "reopen_advice:adv_001"
}
```

Verification types should start parser-centric:

- `component_exists`
- `component_absent`
- `value_equals`
- `pin_net_equals`
- `net_label_exists`
- `net_connected`
- `stub_resolved`
- `warning_cleared`
- `simulation_metric_lt` / `simulation_metric_gt` once simulation exists

### 2.3 Advice lifecycle

Advice must be remembered, not treated as ephemeral chat text.

Statuses:

| Status | Meaning |
|--------|---------|
| `draft` | Created by LLM but not yet shown/approved |
| `pending_user` | Shown to user; waiting for manual KiCad work |
| `awaiting_parse` | User indicated work is done or file save detected |
| `verified` | Next parse confirms expected evidence |
| `failed` | Next parse ran, but expected evidence is missing |
| `obsolete` | Superseded by a newer proposal or user rejection |
| `deferred` | User explicitly postpones the action |

Recommended lifecycle:

```text
draft → pending_user → awaiting_parse → verified
                          ↘ failed → pending_user or escalated
```

### 2.4 Where advice lives

Short-term:

- rendered as checklist items in the chat/webview;
- summarized in the Sync Panel when manual action blocks progress.

Persistent:

- `.hephaistus/state.json` or a dedicated `.hephaistus/advice.json`;
- copied into backup/savepoint snapshots;
- exported into the project history when a checkpoint is accepted.

The already-existing `pendingWarnings` concept should evolve into a more general `pendingManualActions` / `adviceLedger` model. Warnings are one kind of generated advice, but user-facing advice also includes rationale, verification, and links back to patch operations.

---

## 3. Advice vs. Modifications: Recognition Rules

A core design rule: **the extension must never infer executable edits from chat prose.** Chat prose can explain, warn, and teach; only structured payloads may mutate state.

### 3.1 Channel separation

| Channel | Content | Extension behavior |
|---------|---------|--------------------|
| Chat markdown | Human-readable explanation, rationale, warnings, learning notes | Display only |
| `hephaistus-patch` block | Machine-appliable JSON delta | Validate against schema and permission level, then apply or reject |
| `hephaistus-advice` block | Manual action ledger entries | Store, render checklist, track status |
| `hephaistus-verification` block | Assertions for next parse/simulation | Register in verifier |
| Python/SKiDL file edits | Simulation executable description | Diff and run only through simulation runner |

If the LLM emits a beautiful paragraph saying "connect C1 to VIN", that is **advice** unless accompanied by a structured patch/advice payload.

### 3.2 Recommended wire format

The LLM service should return a single structured message to the extension, and the extension should render the human-facing parts. If raw model text is used, fenced blocks must be schema-validated.

Example:

````markdown
I found two issues: missing input bulk capacitance and an undersized feedback divider.

```hephaistus-patch
{
  "value_changes": [
    {"reference": "R2", "old_value": "10k", "new_value": "22k"}
  ],
  "added_components": [
    {"reference": "Cbulk", "libId": "Device:C", "value": "470u", "connections": {"1": "VIN", "2": "GND"}}
  ]
}
```

```hephaistus-advice
[
  {
    "advice_id": "adv_bulk_001",
    "kind": "manual_wiring",
    "title": "Wire Cbulk across VIN/GND near the input connector",
    "detail": "I placed Cbulk in staging with VIN/GND labels. Move it near the input connector and connect the labels to the existing VIN and GND nets.",
    "severity": "required",
    "expected_evidence": ["component_exists:Cbulk", "pin_net_equals:Cbulk.1=VIN", "pin_net_equals:Cbulk.2=GND"]
  }
]
```

```hephaistus-verification
[
  {"type": "component_exists", "subject": "Cbulk"},
  {"type": "pin_net_equals", "subject": "Cbulk.1", "expected": "VIN"},
  {"type": "pin_net_equals", "subject": "Cbulk.2", "expected": "GND"}
]
```
````

### 3.3 Permission and safety mapping

| Proposal content | Required permission | Default handling |
|------------------|---------------------|------------------|
| Value changes only | `values` | Preview diff, apply after approval |
| Add component at staging | `add` | Apply, generate placement/wiring advice |
| Remove component | `delete` | Require explicit confirmation |
| Topology correction / stub / net relabel | `restructure` | Prefer advice-first; only apply labels/stubs where safe |
| Any wiring instruction | any | Never silently apply; track as manual action |

---

## 4. End-to-End Workflow in Detail

### Phase 0 — Baseline

1. User opens a KiCad project in VS Code.
2. Extension detects `.kicad_sch` and parses it to JSON.
3. Extension stores:
   - baseline JSON;
   - source hash/timestamp;
   - known warnings;
   - empty or restored advice ledger.
4. If restored advice exists, the chat/webview shows: "You have 3 pending manual actions from the last optimization round."

### Phase 1 — Goal intake

The user can enter goals in natural language:

- "Make this filter cutoff closer to 50 kHz."
- "Reduce ripple below 20 mV."
- "Review this converter for EMI problems."
- "Integrate this ADC with the FPGA and tell me what I must wire manually."

The extension packages for the LLM:

- current JSON state;
- user goal;
- permission level;
- UI mode (`simple`, `learning`, `advanced`);
- unresolved advice;
- recent verification failures;
- simulation results if available.

### Phase 2 — Proposal generation

The LLM must answer with:

- concise diagnosis;
- patch limited to allowed operations;
- manual advice for anything spatial or ambiguous;
- verification plan;
- optional simulation plan.

The LLM should explicitly separate:

- **"I will change"** — patch operations;
- **"You must do in KiCad"** — advice items;
- **"I will check after you save"** — verification assertions.

### Phase 3 — Patch preview and apply

The extension:

1. validates schema;
2. checks permission level;
3. creates backup/savepoint if required;
4. applies supported patch operations;
5. writes generated warnings and advice into the ledger;
6. updates chat/webview and sync panel.

If patch application creates warnings, those warnings become tracked advice rather than one-off notifications.

### Phase 4 — Human wiring and placement

The user works in KiCad:

- moves staged components into sensible positions;
- breaks wires where series insertion is required;
- adds net labels where unnamed nets are ambiguous;
- draws physical wires corresponding to logical stubs;
- adds documentation notes if requested.

The extension should not fight the user during this phase. It watches saves and keeps status visible.

### Phase 5 — Parse and verify

On save or manual parse:

1. Extension parses KiCad → JSON.
2. Before overwriting state, it checks whether pending advice would be erased and warns the user.
3. The verifier evaluates all pending `verification[]` checks and `expected_evidence`.
4. Each advice item transitions to `verified`, `failed`, or remains `awaiting_parse` if evidence is inconclusive.
5. The LLM receives a compact verification report:

```json
{
  "proposal_id": "prop_20260723_001",
  "verified": ["adv_bulk_001"],
  "failed": [
    {
      "advice_id": "adv_gate_002",
      "missing": ["pin_net_equals:Q1.1=PWM_DRV"],
      "observed": {"Q1.1": "N$7"}
    }
  ]
}
```

### Phase 6 — Continue, escalate, or revert

If verified:

- mark advice resolved;
- continue optimization or run simulation.

If failed:

- explain exactly what is missing;
- avoid re-applying duplicate components;
- either revise advice or ask a narrowing question;
- if the state is worse than baseline, offer revert to savepoint.

This is the critical memory behavior: the LLM should not give the same advice blindly after each parse. It should know whether the user did the job, partially did it, or did something unexpected.

---

## 5. Persona Use Cases

## 5.1 Hobbyist — Simple Signal Conditioning Filter

**Persona goal:** Build a low-pass filter for an Arduino-connected sensor signal, with cutoff near 50 kHz, powered from 3.3 V. The hobbyist wants a working circuit and clear instructions, not a lecture.

### Starting condition

- User sketches a partial RC filter or asks HephAIstus to propose one.
- KiCad schematic contains a sensor input net, 3V3 power, GND, and maybe an op-amp buffer.
- Permission level: `add`.
- UI mode: `simple`.

### Detailed workflow

1. **Ingestion**
   - Extension parses the schematic.
   - JSON shows `U1` op-amp, `R1`, `C1`, `Vsensor`, `Vout`, `3V3`, `GND`.
   - Parser identifies unnamed net `N$1` between sensor and filter input.

2. **User goal**
   - Hobbyist: "Clean up the sensor signal around 50 kHz and tell me if I need to wire anything."

3. **LLM proposal**
   - Diagnosis: first-order RC with R=47 kΩ and C=100 pF gives fc ≈ 33.9 kHz; R=47 kΩ and C=68 pF gives fc ≈ 49.8 kHz.
   - Patch: change `C1` to `68p`; optionally add `Cdecoup` if no local decoupling exists.
   - Advice:
     - if `N$1` is ambiguous, add a label such as `SENSOR_FILT_IN`;
     - if adding decoupling, wire it from `3V3` to `GND` near the op-amp.
   - Verification:
     - `value_equals:C1=68p`;
     - `component_exists:Cdecoup` if added;
     - `pin_net_equals:Cdecoup.1=3V3`;
     - `pin_net_equals:Cdecoup.2=GND`;
     - `net_label_exists:SENSOR_FILT_IN` if the unnamed net was labeled.

4. **Apply**
   - Extension changes `C1` value.
   - If `Cdecoup` is added, it appears in staging with labels.
   - Chat shows a short checklist:
     - "Move Cdecoup next to U1."
     - "Connect one side to 3V3 and the other to GND."
     - "Label the sensor-to-filter net SENSOR_FILT_IN."

5. **User action**
   - Hobbyist moves `Cdecoup`, draws wires/labels, saves.

6. **Parse and verify**
   - If all checks pass, advice becomes `verified`.
   - If `Cdecoup.1` still points to staging label but the net is not connected to real `3V3`, the check fails.
   - Extension reports: "Cbulk/Cdecoup exists, but pin 1 is still on N$3 instead of 3V3. Add a 3V3 label or wire it to the 3V3 rail."

7. **Optional simulation**
   - Once simulation is available, run AC sweep from 10 Hz to 10 MHz.
   - Report fc and passband attenuation in plain language.
   - If fc is off due to component tolerance, propose E24 alternatives and update the patch.

### Hobbyist-specific acceptance criteria

- The user is never asked to interpret raw JSON.
- Every manual step is small, numbered, and checkable.
- Failures are explained in terms of KiCad actions: label, wire, move, save.

---

## 5.2 Student — Half-Bridge DC-DC Converter Assignment

**Persona goal:** Design a 12 V → 5 V half-bridge converter switching at 1 MHz while learning why the LLM recommends each change. The student needs pedagogical transparency and guardrails against unsafe or non-physical suggestions.

### Starting condition

- Schematic has input source, high-side/low-side MOSFETs, gate driver, output inductor, output capacitor, load.
- Some nets may be incompletely labeled.
- Permission level: `add` initially; `restructure` only after review.
- UI mode: `learning`.

### Detailed workflow

1. **Ingestion and review**
   - Parser extracts components and nets.
   - LLM review pass flags likely issues before simulation:
     - missing input bulk capacitor;
     - missing gate-driver bootstrap capacitor;
     - output cap ripple current likely too high;
     - switch node label missing, making measurements ambiguous.

2. **Student asks**
   - "Help me finish the power stage and reduce ringing/EMI, but explain each change."

3. **LLM proposal with teaching annotations**
   - Patch:
     - add `Cbulk` across `VIN`/`GND`;
     - add `Cboot` if absent between `BOOT` and `SW`;
     - adjust gate resistor values if present;
     - optionally add an RC snubber placeholder if permission allows.
   - Advice:
     - place `Cbulk` close to half-bridge power loop;
     - ensure `SW` net is labeled before simulation probing;
     - if adding snubber, break the `SW` route and connect the snubber from `SW` to `GND` or across the low-side device depending on chosen topology;
     - keep high di/dt loop small on layout, even though HephAIstus cannot route the board.
   - Learning explanation:
     - why bulk capacitance reduces input impedance at switching frequency;
     - why bootstrap cap must be local to driver;
     - why gate resistors trade switching loss against ringing.

4. **Structured verification**
   - `component_exists:Cbulk`, `component_exists:Cboot`;
   - `pin_net_equals:Cboot.1=BOOT`, `pin_net_equals:Cboot.2=SW`;
   - `net_label_exists:SW`;
   - if snubber added: `pin_net_equals:Rsnub.1=SW` and `pin_net_equals:Csnub.1=SW` or expected topology-specific assertions.

5. **Manual iteration**
   - Student saves schematic after wiring only part of the advice.
   - Parser shows `Cboot` verified but `Cbulk.1` on `N$4` instead of `VIN`.
   - LLM remembers the failure and does not duplicate `Cbulk`; it only asks for the missing label/wire.

6. **Simulation-driven refinement**
   - SKiDL/ngspice runs switching or simplified averaged simulation.
   - Results show input rail droop or excessive gate ringing.
   - LLM updates values and, if needed, proposes one structural change at a time.
   - After N autonomous iterations, checkpoint prompt summarizes:
     - values changed;
     - components added;
     - manual actions verified;
     - manual actions still pending;
     - simulation metrics before/after.

### Student-specific acceptance criteria

- Every patch line has a "why" explanation.
- Structural advice includes a schematic-level instruction, not layout hand-waving.
- Failed verification becomes a teaching moment: "The schematic still shows Q1 gate on N$7; simulation needs it labeled PWM_DRV."

---

## 5.3 Senior Engineer — High-Speed ADC Integration into Legacy FPGA Design

**Persona goal:** Integrate an external high-speed ADC into a legacy FPGA schematic while preserving proprietary vendor properties, enforcing signal-integrity practices, and producing auditable documentation for board bring-up.

### Starting condition

- Existing schematic may be large and contain vendor-specific properties.
- Some pages/blocks are legacy and should not be reformatted.
- Permission level: conservative `values` or `add`; `restructure` only with explicit approval.
- UI mode: `advanced`.

### Detailed workflow

1. **Advanced ingestion**
   - Parser must preserve unknown/vendor properties by using text-based delta application and avoiding lossy serialization.
   - JSON state distinguishes:
     - verified connectivity;
     - inferred connectivity;
     - ambiguous regions needing labels.

2. **Engineer goal**
   - "Integrate the ADC interface, flag SI risks, and tell me exactly what I must wire before we simulate clock/data integrity."

3. **LLM review**
   - Detects high-speed nets: `ADC_D0_P/N`, `ADC_CLK_P/N`, `SCK`, `SDO`, `SDI`, `CS`.
   - Flags:
     - differential pairs not consistently labeled;
     - missing termination strategy;
     - clock net routed through an unnamed net;
     - no explicit note for impedance/length-matching constraints;
     - decoupling present but not verified near ADC power pins.

4. **Conservative patch**
   - Add documentation symbols or notes if supported.
   - Add missing decoupling components at staging with labels.
   - Propose value changes for termination resistors only if they already exist or if user approves adding them.

5. **Advice-heavy topology work**
   - Because arbitrary wire manipulation is limited, most SI work becomes tracked advice:
     - "Label the differential clock nets ADC_CLK_P and ADC_CLK_N on both ADC and FPGA sides."
     - "Insert series termination Rclk near the driver; this requires breaking the clock wire."
     - "Add a note requiring 100 Ω differential routing and length matching within the team standard."
     - "Verify bank voltage compatibility before connecting SDO to FPGA bank 14."

6. **Verification after parse**
   - Parser checks labels and connectivity.
   - For series termination, expected evidence might be:
     - `component_exists:Rclk`;
     - `pin_net_equals:Rclk.1=ADC_CLK_P_SRC`;
     - `pin_net_equals:Rclk.2=ADC_CLK_P`;
     - `net_label_exists:ADC_CLK_P_SRC`.
   - If the user instead wired directly without labels, the verifier may mark the check `failed` or `inconclusive` and ask for labels because high-speed review requires unambiguous net identity.

7. **Documentation output**
   - LLM generates an "Advisory Block" for schematic notes and a separate engineering summary:
     - termination assumptions;
     - required SI checks;
     - unresolved manual actions;
     - bring-up sequence;
     - simulation/probe points.

### Senior-engineer acceptance criteria

- No silent rewrite of legacy schematic regions.
- All structural interventions are auditable and reversible.
- Advice memory survives multiple parse cycles and is exportable for design review.

---

## 6. Cross-Cutting Use Cases

### 6.1 Proactive review pass

Trigger: schematic save, explicit command, or before simulation.

LLM checks:

- floating inputs;
- shorted outputs;
- missing decoupling;
- unlabeled high-speed or feedback nets;
- component ratings and power dissipation;
- placeholder values that were never optimized.

Output must be split into:

- patchable fixes;
- manual advice;
- verification checks;
- "not enough information" questions.

### 6.2 Iterative autonomy with checkpoint

The LLM may run multiple value-only simulation cycles autonomously. It must stop earlier when:

- a structural change is required;
- a manual action is pending and blocks further progress;
- simulation results conflict with parser state;
- permission level is insufficient.

Checkpoint summary must include:

- autonomous iterations used;
- best metric achieved;
- patch diff;
- verified advice;
- pending advice;
- revert option.

### 6.3 Stale or contradictory advice

If the user changes the schematic manually in a way that invalidates prior advice, the verifier marks old advice `obsolete` and records why. The LLM must not keep pushing stale instructions.

Example:

- advice said "connect C1 to VIN";
- user deleted C1 and chose a different topology;
- next parse shows C1 absent;
- advice becomes `obsolete`, and a new proposal is generated from the new baseline.

### 6.4 Partial completion

Users often do only part of the checklist. The system must support partial progress:

- verified items close;
- failed items reopen with exact missing evidence;
- ambiguous items ask for labels or user confirmation;
- patch state is not duplicated.

### 6.5 Rollback and design exploration

Before any non-trivial proposal, HephAIstus creates a savepoint. If the user rejects the direction:

- restore KiCad/JSON baseline;
- mark proposal rejected;
- retain the reasoning in history if the user wants to revisit it.

---

## 7. Development Implications

To make these use cases real, the next phases should build the following in order:

1. **Structured LLM output contract**
   - schema for `OptimizationProposal`;
   - strict separation of `patch`, `advice`, `verification`, and `simulation_plan`;
   - no executable inference from prose.

2. **Advice ledger**
   - persistent IDs, statuses, expected evidence, links to patch operations;
   - migration path from `pendingWarnings` to `pendingManualActions`/`adviceLedger`;
   - UI checklist in chat/webview and summary in sync panel.

3. **Verification engine**
   - parser-backed checks first;
   - simulation-metric checks later;
   - compact verification reports back to the LLM.

4. **Warning generalization**
   - series insertion and missing labels become typed advice with verification;
   - generated KiCad annotations should reference advice IDs where practical.

5. **Simulation integration**
   - SKiDL generation from verified JSON only;
   - refuse or degrade simulation when required manual actions are pending;
   - feed metrics into iterative optimization.

6. **Tests grounded in these use cases**
   - hobbyist: value change + decoupling advice verification;
   - student: bootstrap cap wiring remembered across parse cycles;
   - senior: legacy property preservation and label-based high-speed verification.

---

## 8. Design Principles to Keep Us Grounded

1. **Human owns geometry.** HephAIstus may place staged parts and labels, but final routing belongs in KiCad.
2. **Machine edits must be boring.** If a change cannot be applied deterministically and verified, make it advice.
3. **Advice is state.** Chat text is not enough; advice must be stored, tracked, and verified.
4. **Every proposal needs a check.** If the LLM asks the user to wire something, it must also define how the next parse proves it happened.
5. **Fail narrowly.** On verification failure, identify the exact pin/net/component that is missing; do not restart the whole design.
6. **Explain at the right altitude.** Hobbyist gets steps, student gets reasons, professional gets evidence and audit trail.
