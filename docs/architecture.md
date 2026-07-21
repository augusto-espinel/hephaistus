# HephAIstus Architecture Blueprint (v2.0)

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
| Component addition | ✅ Complete | Adds symbol with net labels, warning system |
| Connection changes | 📋 Planned | Creates stub markers |

### 4.2 Component Addition with Net Labels

When adding components, the system uses **net labels** instead of wire routing:

1. **Parse existing nets** — Extract net names from JSON state and schematic labels
2. **Generate net labels** — Create `(label "net_name" ...)` for each pin connection
3. **Place at staging position** — New components offset from existing components
4. **Detect manual action requirements** — Check for series insertion or missing labels

**Why net labels?**
- No geometry calculations needed
- User completes wiring in KiCad (their domain)
- Works for both parallel and series insertions (with warnings)

### 4.3 Warning System

#### Warning Types

| Type | Condition | User Action |
|------|-----------|-------------|
| `series_insertion` | All pins to same existing net | Break wire, connect labels |
| `missing_labels` | Pins to nets without labels | Add labels to existing wires |

#### Detection Functions

```python
def detect_series_insertion(connections, existing_nets):
    """Check if all pins connect to same existing net."""
    unique_nets = set(connections.values())
    if len(unique_nets) == 1 and unique_nets.pop() in existing_nets:
        return True, net_name
    return False, None

def detect_missing_labels(connections, existing_nets, nets_with_labels):
    """Check if component connects to nets without labels."""
    missing = []
    for net in set(connections.values()):
        if net in existing_nets and net not in nets_with_labels:
            missing.append(net)
    return len(missing) > 0, missing
```

#### Schematic Annotations

Both warning types add text annotations in KiCad:

```
(series insertion)
⚠ R3 requires series insertion.
Break wire on net 'dc_plus' and connect labels.

(missing labels)
⚠ R4 requires labels on existing nets.
Add net labels 'net_a', 'net_b' to existing wires.
```

#### VS Code UI Guard

**Problem:** User could parse KiCad → JSON after applying delta, erasing LLM suggestions before completing manual actions.

**Solution:**
1. Save `pendingWarnings[]` to `state.json` after Apply JSON → KiCad
2. Check `pendingWarnings` before Parse KiCad → JSON
3. Show modal: "You have unfinished manual actions... Parsing will erase LLM suggestions"

**User Flow:**
```
Apply JSON → KiCad
      │
      ├─ Warnings generated?
      │   └─ Modal: "Manual action required"
      │       └─ "Open Schematic" / "Dismiss"
      │
      └─ Warnings saved to state.json

User tries Parse KiCad → JSON
      │
      └─ Check pendingWarnings
          ├─ Has warnings? → Modal: "Continue?"
          └─ Clear if user confirms
```

### 4.4 Delta Application Script

**Location:** `scripts/wrappers/kiutils_delta_apply.py`

**IMPORTANT:** Uses **text-based editing** to preserve all KiCad 10 properties.

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
    "connections": {
      "1": "dc_plus",
      "2": "dc_minus"
    }
  }]
}
```

**Warning Output:**
```json
{
  "warnings": [{
    "type": "series_insertion",
    "component": "R3",
    "net": "dc_plus",
    "message": "⚠ R3 requires series insertion...",
    "action_required": "break_wire"
  }]
}
```

### 4.4 Geometry Preservation

The delta application preserves:
- **Wire paths** — Existing geometry unchanged
- **Junction positions** — Connection points preserved
- **Component positions** — Only new components need placement
- **Labels** — Net labels preserved

### 4.5 Backup Strategy

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

LLM cannot determine where to place new components spatially. The user controls layout.

### 9.2 The Solution

Stub connections are **logical-only** connections:

```json
{
  "stubs": [
    {
      "from": "C1.1",
      "to": "GND",
      "type": "logical",
      "status": "pending_placement"
    }
  ]
}
```

### 9.3 UI Representation

- Stubs appear as dashed lines in KiCad
- User completes physical wiring
- Stubs resolved → removed from state

### 9.4 Placement Algorithm

```
1. LLM proposes component (C1: 100nF)
2. Extension computes staging origin:
   - Bounding box of existing components
   - Offset (dx=25mm, dy=25mm) to lower-right
3. Symbol placed at staging coordinates
4. Stub connections created
5. User repositions, wires, resolves stubs
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
| Component addition | 📝 Planned | Requires library symbol lookup |
| Connection stubs | 📝 Planned | Logical-only connections |
| LLM integration | 📝 Planned | SKiDL code generation |
| Multi-sheet support | 📋 Planned | Hierarchical schematics |
| SKiDL/ngspice runner | 📋 Planned | Simulation execution |