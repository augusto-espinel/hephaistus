# HephAIstus Architecture Blueprint (v2.1)

*Updated 2026-08-04 — stub-based apply flow (§4.2, §9): warnings replaced by programmatic clear-and-stub net restructuring.*

This document is the **authoritative reference** for HephAIstus architecture, parsing subsystem, and round-trip workflow.

For vision and use cases, see [vision.md](./vision.md). For implementation status, see [spec.md](./spec.md). For manual testing procedures, see [TEST-MANUAL-ROUNDTRIP.md](./TEST-MANUAL-ROUNDTRIP.md).

---

## Table of Contents

1. [Core Structure](#1-core-structure)
2. [Component Interaction Map](#2-component-interaction-map)
3. [Parsing Subsystem](#3-parsing-subsystem)
4. [Round-Trip Workflow](#4-round-trip-workflow)
5. [Sync Panel & User Control](#5-sync-panel--user-control)
6. [Tool Integration](#6-tool-integration)
7. [Iterative Autonomy](#7-iterative-autonomy)
8. [Permission Levels](#8-permission-levels)
9. [Stub Connections](#9-stub-connections)
10. [Configuration](#10-configuration)

---

## 1. Core Structure

The architecture has four domains: **Extension Host** (TypeScript), **Python Bridge** (TypeScript↔Python), **Python Package** (KiCad sync & simulation), and **Utilities**.

### 1.1 Extension Host Domain (`src/`)

| File | Role | Description |
|------|------|-------------|
| `extension.ts` | Entrypoint | Command registration, file watcher setup |
| `syncOrchestrator.ts` | Brain | Coordinates ingestion and drift detection |
| `hephaistusService.ts` | State Keeper | Manages `ProjectState`, hashing, change detection |
| `services/ingestionService.ts` | Ingestion | KiCad → JSON with KiUtils fallback |
| `services/deltaApplyService.ts` | Delta Apply | JSON → KiCad delta application |
| `ui/syncPanel.ts` | Sync Panel | VS Code sidebar for manual sync control |

### 1.2 Python Bridge Domain (`src/python/`)

| File | Role |
|------|------|
| `pythonBridge.ts` | Process spawner, JSON communication |
| `venvManager.ts` | Virtual environment management |
| `simulationRunner.ts` | SPICE simulation orchestration |

### 1.3 Python Package Domain (`python/hephaistus/`)

| Module | Status | Description |
|--------|--------|-------------|
| `kicad_sync/` | ✅ Complete | KiCad synchronization |
| `simulation/` | 📋 Planned | SPICE simulation |

**Scripts (`scripts/wrappers/`):**

| Script | Purpose |
|--------|---------|
| `kiutils_parser_wrapper.py` | KiCad → JSON parsing |
| `kiutils_delta_apply.py` | JSON → KiCad delta application |

---

## 2. Component Interaction Map

| Phase | Input | Primary Service | Output |
|-------|-------|-----------------|--------|
| **Detection** | `.kicad_sch` save | `syncOrchestrator.ts` | Status update |
| **Ingestion** | KiCad file | `ingestionService.ts` | JSON state |
| **Delta Apply** | JSON changes | `deltaApplyService.ts` | Modified KiCad |
| **User Action** | Button click | `syncPanel.ts` | Parse/Apply command |

---

## 3. Parsing Subsystem

### 3.1 Implementation Status

| Phase | Status | Description |
|-------|--------|-------------|
| Property Extraction | ✅ Complete | Reference, value, SPICE params |
| Net Mapping | ✅ Complete | Pin-to-net through wires/junctions |
| Wire Tracking | ✅ Complete | UUIDs for round-trip |
| Stub Net Coverage | ✅ Complete | Same-name labels across disjoint stub islands accumulate (2026-08-04) |
| Unnamed Nets | ✅ Complete | N$1, N$2, ... auto-naming |

### 3.2 Parser Script

**Location:** `scripts/wrappers/kiutils_parser_wrapper.py`

```bash
python scripts/wrappers/kiutils_parser_wrapper.py circuit.kicad_sch > state.json
```

### 3.3 kiutils Data Structures

| Type | Description | Key Attributes |
|------|-------------|----------------|
| `Schematic` | Root object | `schematicSymbols`, `libSymbols`, `labels`, `junctions` |
| `SchematicSymbol` | Placed component | `properties`, `pins`, `position`, `uuid` |
| `LibSymbol` | Library definition | `units[1].pins` (pin definitions) |
| `Connection` | Wire segment | `uuid`, `points[]` |
| `Junction` | Connection point | `uuid`, `position` |
| `LocalLabel` | Net name label | `text`, `position` |

### 3.4 Property Extraction

```python
props = {p.key: p.value for p in symbol.properties}
reference = props.get('Reference', '')      # "C1", "R1", "V1"
value = props.get('Value', '')              # "1000e-6", "10"
sim_device = props.get('Sim.Device', '')    # "V", "R", "C", "D"
sim_params = props.get('Sim.Params', '')    # "dc=0 ampl=10 f=50 ac=0"
```

### 3.5 Net Connectivity Algorithm

1. **Collect Labels**: Map position → net name
2. **Build Wire Graph**: Connect points through wires and junctions
3. **Propagate Labels**: Flood-fill from label positions
4. **Assign Pins**: For each pin, find net at its position
5. **Detect Unnamed Nets**: Group unassigned pins, name N$1, N$2, ...

### 3.6 JSON Output Schema

```json
{
  "schemaVersion": "1.1.0",
  "source": "rectifier.kicad_sch",
  "components": [
    {
      "uuid": "278a90bc-...",
      "reference": "C1",
      "libId": "Device:C",
      "value": "1000e-6",
      "position": {"x": 128.27, "y": 67.31},
      "pins": [
        {"number": "1", "uuid": "...", "net": "dc_minus"},
        {"number": "2", "uuid": "...", "net": "dc_plus"}
      ]
    }
  ],
  "nets": [
    {"name": "dc_plus", "connectedPins": ["C1.2", "R2.2", ...]}
  ],
  "wires": [{"uuid": "...", "points": [...]}],
  "junctions": [{"uuid": "...", "position": {...}}]
}
```

---

## 4. Round-Trip Workflow

### 4.1 Supported Operations

| Operation | Status | Description |
|-----------|--------|-------------|
| Value changes | ✅ Complete | Modifies `Value` property, preserves geometry |
| Component removal | ✅ Complete | Removes symbol, preserves connected wires/junctions |
| Component addition | ✅ Complete | Staging placement + stub connections; library auto-embedding |
| Net restructuring | ✅ Complete | Clear-and-stub: net splits / series insertion via pin net re-assignments (2026-08-04) |

### 4.2 Stub-Based Component Addition and Net Restructuring

Since 2026-08-04, all new connectivity is applied programmatically as
**stubs**: a short wire (5.08 mm) plus a net label placed directly on the
affected pin. Connectivity is carried by label names alone, so the schematic
is electrically complete — and simulatable — immediately after apply. The
user may redraw physical wires later for aesthetics, but no manual step is
required for correctness.

**Component addition** (`apply_component_addition_text`):
1. Resolve and, if missing, **embed the library symbol** into `lib_symbols`
   from the user's installed KiCad libraries (sym-lib-table resolution).
2. Place the symbol at the staging position with an `(instances ...)` block
   and `(pin N (uuid ...))` blocks (KiCad 6+ instance format — required for
   the parser to see the pins).
3. Place a stub carrying the assigned net name on every connected pin.

**Net restructuring** (`apply_net_restructure`) — runs between removals and
additions. When the modified JSON moves pins off a net (series insertion,
net split, net rename):
1. Build the affected net's wire island via kiutils topology
   (wires + junctions BFS from every member pin).
2. Strip ALL wires, junctions, and labels of that island.
3. Place a stub on every former member pin carrying its NEW net name.
4. Pins that gain a net from an unconnected state also receive stubs
   (without clearing anything).

Stub direction follows the removed wire's direction at that pin, falling
back to the library pin angle. Power symbols anchor their nets — attempting
to move a pin off a power-anchored net is rejected with a warning.

**Why clear-and-stub instead of surgical wire edits?**
- The AI contract is purely logical: topology changes are expressed as pin
  net re-assignments in JSON; geometry is derived, never specified.
- Surgical wire breaking is geometrically ambiguous (which segment? where?);
  clearing the island and re-stubbing is deterministic and always valid.
- Aesthetics are sacrificed temporarily (the affected net loses its drawn
  wires) — acceptable, because the user only redraws nets that changed.

### 4.3 Residual Warnings

Warnings now exist only for "could not complete" cases:

| Type | Condition | User Action |
|------|-----------|-------------|
| `missing_library` | libId not found in any installed KiCad library | Import the library in KiCad, then re-apply |
| `power_net_anchor` | AI tried to move pins off a power-symbol-anchored net | Re-express the change without moving the anchored net |

Successful applies emit **zero** warnings. The legacy `series_insertion`,
`missing_labels`, and `wiring_advice` warnings were removed on 2026-08-04 —
the situations they described are now applied automatically.

#### VS Code UI Guard

The `pendingWarnings` guard remains, but now triggers only on residual
warnings:
1. Save `pendingWarnings[]` to `state.json` after Apply JSON → KiCad
2. Check `pendingWarnings` before Parse KiCad → JSON
3. Show modal: "You have unfinished manual actions..."

### 4.4 Delta Application Script

**Location:** `scripts/wrappers/kiutils_delta_apply.py`

#### Integrity Validation (mandatory, added 2026-08-01)

Before computing any delta, the script validates **both** JSON states and
refuses to run (exit code 3, `integrity_validation_failed`) if it finds:

- components missing `reference` or `uuid`;
- duplicate component references;
- duplicate component UUIDs;
- duplicate pin UUIDs.

**Why:** `compute_delta()` keys components by UUID. A duplicated UUID — e.g.
hand-copying R2's JSON block to add R3 — makes the new component overwrite the
existing one in the lookup table. The differ then emits a *value change*
against the existing symbol (corrupting its value in the schematic) and the
addition is silently dropped: no symbol, no net labels, no warning (root cause
of the UT-06 failure, 2026-07-31). Failing loudly protects both hand-edited
and LLM-generated JSON states.

#### Auto-repair mode (`--repair`, added 2026-08-01)

Passing `--repair` as a 4th argument attempts to fix auto-repairable
violations in the **modified** JSON before applying:

- missing component/pin UUIDs → fresh UUID assigned;
- duplicate component UUIDs → the "rightful owner" (the component whose
  reference matches the original baseline's reference for that UUID, else the
  first occurrence) keeps it; others get fresh component **and** pin UUIDs;
- duplicate pin UUIDs → later occurrences get fresh UUIDs.

Duplicate or missing **references** are never auto-repaired (identity is
ambiguous) — the script still exits 3. On success the repaired JSON is written
back to the modified-state file so the extension stays consistent, and the
output includes a `repairs` list. The **original baseline is never repaired**.

The extension surfaces exit-3 violations in a modal dialog with a
"Fix uuids and retry" button that re-runs the apply with `--repair`
(`hephaistus.applyDelta` command, `syncPanel.ts`).

#### Added-component data contract (fixed 2026-08-01)

`apply_component_addition_text()` historically read pin→net mappings from a
`connections` dict (`{"1": "net"}`) that the parser/JSON state does not
produce — nets live on `pins[].net`. With `connections` absent, additions were
staged **without net labels, series-insertion warnings, or annotations**. The
script now derives `connections` from `pins[]` when missing, and reads the
component value from top-level `value` first (matching `compute_delta()`
precedence; `properties.Value` may be stale in edited JSON).

**Offset accounting (fixed 2026-08-01):** insertions into the schematic text
must advance `last_symbol_end` by the length of the *actually inserted* string
(`'\n\t' + block.replace('\n', '\n\t')`), never by `len(block)` — the replace
adds one tab per newline. The old `len(label) + 2` accounting made subsequent
insertions land mid-block (observed: a label uuid sliced in half → KiCad
"Unterminated delimited string" on load).

**IMPORTANT:** Uses **text-based editing** to preserve all KiCad 10 properties.

#### Stub architecture supersedes wiring advice (2026-08-04)

The per-pin `wiring` recipes added 2026-08-01 (`build_wiring_advice()`,
`series_insertion` / `missing_labels` / `wiring_advice` warnings, schematic
text annotations) were removed on 2026-08-04. The apply pass now performs
the wiring itself via clear-and-stub (see §4.2); warnings persist only for
genuine failure states (see §4.3). The verification-first ideas survive in
the advice-ledger design (`use_cases_blueprint.md` §2), which remains the
target for optional *aesthetic* re-wiring suggestions.

The script reads the `.kicad_sch` file as text, finds the symbol by UUID,
locates the `Value` property S-expression, and replaces only the value string.
This preserves all KiCad formatting including:

- `(show_name no)`
- `(do_not_autoplace no)`
- `(hide yes)`
- All other KiCad 10 properties

```bash
python scripts/wrappers/kiutils_delta_apply.py \
    original.json modified.json circuit.kicad_sch
```

**Why text-based?** The `kiutils` library doesn't fully support KiCad 10 properties.
When it reads and re-serializes a file, it strips properties it doesn't understand,
causing values like `show_name` to appear as visible text in the schematic.
Text-based editing avoids this by only modifying the exact value that changed.

### 4.5 Delta Types

**Value Change:**
```json
{
  "value_changes": [{
    "uuid": "...",
    "reference": "C1",
    "old_value": "1000e-6",
    "new_value": "470e-6"
  }]
}
```

**Component Removal:**
```json
{
  "removed_components": [{
    "uuid": "...",
    "reference": "R1"
  }]
}
```

**Component Addition:**
```json
{
  "added_components": [{
    "uuid": "...",
    "reference": "C2",
    "libId": "Device:C",
    "value": "100n",
    "pins": [
      {"number": "1", "uuid": "...", "net": "dc_plus"},
      {"number": "2", "uuid": "...", "net": "dc_minus"}
    ]
  }]
}
```

**Net Restructuring (series insertion of R3 between C1 and R2):**
```json
{
  "connection_changes": [
    {"reference": "R2", "pin": "2", "old_net": "dc_plus", "new_net": "dc_plus_shunt"}
  ],
  "added_components": [{
    "reference": "R3", "libId": "Device:R", "value": "0.001",
    "pins": [
      {"number": "1", "net": "dc_plus"},
      {"number": "2", "net": "dc_plus_shunt"}
    ]
  }]
}
```
Result: the `dc_plus` island is cleared; every former member pin gets a stub
with its new net name; R3 is staged with stubs on both potentials.

**Warning Output (residual only):**
```json
{
  "warnings": [{
    "type": "missing_library",
    "component": "U7",
    "libId": "MyVendor:ADC128S052",
    "message": "Library symbol not installed; import it in KiCad, then re-apply"
  }]
}
```

### 4.6 Geometry Preservation

The delta application preserves:
- **Wire paths of untouched nets** — Existing geometry unchanged
- **Junction positions** — Connection points preserved (except on cleared nets)
- **Component positions** — Only new components need placement
- **Labels of untouched nets** — Net labels preserved

Nets that the AI restructures are the deliberate exception: their wire island
is cleared and replaced by stubs (§4.2).

### 4.7 Backup Strategy

Before applying changes:
1. Automatic backup: `.kicad_sch.bak`
2. Original JSON saved for rollback

---

## 5. Sync Panel & User Control

### 5.1 Features

| Feature | Description |
|---------|-------------|
| Status Indicator | 🔴 KiCad newer, 🔵 JSON newer, 🟢 synced |
| Recommended Action | Arrow + "(recommended)" label on logical button |
| File Times | Shows modification timestamps |
| Manual Buttons | Parse KiCad → JSON, Apply JSON → KiCad |
| Confirmation Dialogs | Warns before destructive operations |
| Discard Option | "Discard KiCad changes" when KiCad newer but JSON unchanged |
| VS Code Sidebar | "HephAIstus Sync" panel in Explorer |

### 5.2 Manual Sync Workflow

The sync workflow is **one-way-at-a-time** (not circular):

1. **KiCad → JSON**: User clicks "Parse KiCad → JSON"
   - If JSON has uncommitted changes: warning dialog
   - Creates `{name}.json` and `{name}.original.json` baseline

2. **JSON → KiCad**: User clicks "Apply JSON → KiCad"
   - If KiCad has uncommitted changes: warning dialog
   - If no JSON changes but KiCad newer: offer "Discard KiCad changes"
   - Updates KiCad from JSON delta
   - Updates baseline to reflect new state

### 5.3 Baseline File Naming

Baseline files use `.original.json` suffix to avoid collision with `_backup.kicad_sch` files:

```
rectifier.kicad_sch        → KiCad schematic
rectifier.json             → JSON state (editable)
rectifier.original.json     → Baseline for delta comparison
```

**Note:** The pattern `{name}_backup.json` is reserved for JSON state of `{name}_backup.kicad_sch`.

### 5.4 Sync State Tracking

The `ProjectState.lastSync` field tracks sync history:

```typescript
lastSync?: {
    source: 'kicad' | 'json';  // Which file was the source
    timestamp: string;          // ISO timestamp of last sync
    kicadHash?: string;         // Hash of KiCad content (future use)
    jsonHash?: string;          // Hash of JSON content (future use)
}
```

**Current Use:** Timestamp-based sync detection

**Future Use (Planned):**
- Detect "touch" operations (file saved but content unchanged)
- Verify round-trip integrity (KiCad → JSON → KiCad hash comparison)
- Skip unnecessary re-parsing when hash unchanged

### 5.5 File Watcher Behavior

| Event | Action |
|-------|--------|
| KiCad file changed | Update panel status only |
| JSON file changed | Update panel status only |
| User clicks "Parse" | Run ingestion, update JSON |
| User clicks "Apply" | Run delta apply, update KiCad |

---

## 6. Tool Integration

| System | Interface | Purpose |
|--------|-----------|---------|
| **KiCad CAD** | `scripts/wrappers/` | Read schematics, write deltas |
| **LLMs** | `llmService.ts` | Reasoning, optimization proposals |
| **VS Code API** | `extension.ts`, `ui/*` | Commands, file watching, diff UI |
| **Python venv** | `venvManager.ts` | Dependency isolation |
| **kiutils** | Python package | KiCad file parsing |
| **SKiDL/ngspice** | Planned | Netlist generation, simulation |

---

## 7. Iterative Autonomy

### 7.1 Iteration Budget

The LLM can iterate through multiple simulation cycles (default N=3-5) before requiring human acknowledgment.

```
[User] "Optimize for efficiency"
    ↓
[LLM] Propose → Simulate → Analyze → Refine (iteration 1)
    ↓
[LLM] Adjust → Simulate → Analyze (iteration 2)
    ↓
[LLM] Converged? Checkpoint prompt
    ↓
[User] Accept / Continue / Abort & Revert
```

### 7.2 Savepoint Semantics

Before optimization:
- **`.hephaistus/backups/{timestamp}/`** — Snapshot of schematic, JSON, scripts
- Abort → revert to last known-good state

---

## 8. Permission Levels

| Level | Operations Allowed | Use Case |
|-------|-------------------|----------|
| `values` | Modify values only | Conservative, safe mode |
| `add` | Values + Add to staging | Missing components |
| `delete` | Values + Add + Mark removal | Redundant components |
| `restructure` | All + Connection stubs | Topology corrections |

**Default:** `add`

### 8.1 Intent Expression

Before structural changes, LLM must express:
1. **Problem:** "C1 is missing, causing DC offset"
2. **Solution:** "Add 100nF capacitor at staging area"
3. **Impact:** "You'll need to position C1 near input"

---

## 9. Stub Connections

### 9.1 The Problem

The LLM reasons about topology, not geometry. It cannot know where a new
component belongs on canvas, and surgical wire edits (which segment to cut,
where to route) are geometrically ambiguous.

### 9.2 The Solution (implemented 2026-08-04)

Stubs are **physical but minimal**: a 5.08 mm wire plus a net label placed on
the affected pin. Label names carry connectivity, so the schematic is valid,
ERC-clean, and simulatable the moment the apply finishes.

Two stub paths exist:

- **Addition stubs** — every connected pin of a newly staged component gets
  a stub with its assigned net.
- **Restructuring stubs** — when pins move off a net, the net's old wire
  island is cleared and every former member pin gets a stub carrying its new
  net name (§4.2).

### 9.3 User Experience

- The circuit works immediately after apply (ERC-clean, simulatable).
- Changed nets look "stubbed" until the user redraws wires — a visible,
  honest signal of exactly what the AI touched.
- Untouched nets keep their original geometry.

### 9.4 Placement Algorithm

```
1. LLM proposes component (C1: 100nF) with pin→net assignments in JSON
2. Extension computes staging origin:
   - Bounding box of existing components
   - Offset (dx=25mm, dy=25mm) to lower-right
3. Library symbol embedded if missing; symbol placed at staging coordinates
4. Stub direction = removed wire direction at that pin,
   else library pin angle
5. User repositions and redraws wires when convenient (optional)
```

---

## 10. Configuration

```json
{
  "hephaistus": {
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
    },
    "permissions": {
      "level": "add"
    },
    "iteration": {
      "maxAutonomousIterations": 5,
      "checkpointOnStart": true,
      "autoRevertOnAbort": true
    },
    "backup": {
      "enabled": true,
      "maxBackups": 10
    },
    "ui": {
      "mode": "simple"
    }
  }
}
```

---

## Appendix: Future Work

| Feature | Status | Notes |
|---------|--------|-------|
| Component addition | ✅ Complete | Staging + stubs + library auto-embedding (2026-08-04) |
| Net restructuring | ✅ Complete | Clear-and-stub for splits / series insertion (2026-08-04) |
| LLM integration | 📝 Planned | SKiDL code generation |
| Multi-sheet support | 📋 Planned | Hierarchical schematics |
| SKiDL/ngspice runner | 📋 Planned | Simulation execution |