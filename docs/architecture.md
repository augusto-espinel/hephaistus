# HephAIstus Architecture Blueprint (v1.5 - Permission Levels & Stubs)

This document serves as the canonical, structural blueprint of the Hephaistus VS Code extension. It maps the physical file organization within the codebase to the functional roles they play in achieving goal-directed EDA Copiloting and simulation workflow orchestration.

For vision and use cases, see [vision.md](./vision.md).

## I. Core Structure & Dependencies

The architecture is split into four primary domains: **Extension Host Logic** (TypeScript/JavaScript), **Python Bridge** (TypeScript↔Python integration), **Python Package** (KiCad sync & simulation), and **Utilities**. These components interact through defined service boundaries, minimizing direct dependency coupling.

### A. The Extension Host Domain (`src/`)
This domain handles the user interface, lifecycle management, and top-level orchestration logic within VS Code.

*   **`src/extension.ts`**: *Entrypoint.* Registers all commands (`hephaistus.startSession`, etc.) and initializes the `FileWatcherService`. It provides external hooks for core functionality.
*   **`src/syncOrchestrator.ts`**: **The Brain.** This service is responsible for running the detection cycle (`runSyncCycle`). It determines *if* a change occurred (KiCad $\to$ JSON vs Python $\leftrightarrow$ JSON) and calls the appropriate backend services.
    *   Dependencies: `ingestionService.ts`, `scriptUpdateService.ts`.
*   **`src/hephaistusService.ts`**: **The State Keeper.** Manages the centralized, persisted `ProjectState` object (loaded from `.hephaistus/state.json`). It provides critical functions for change detection: hashing and identifying schema drift (`analyzeState()` function).
    *   Dependencies: `utils.ts`, File System APIs.
*   **`src/services/`**: Contains the business logic implementation, separated by functional concern (Ingestion, Patching, Scripting).

### B. The Python Bridge Domain (`src/python/`)
This domain bridges the TypeScript extension with the Python package, managing virtual environments and process communication.

*   **`pythonBridge.ts`**: **The Process Spawner.** Handles spawning Python processes, capturing output, and managing lifecycle. Supports JSON parsing of results.
*   **`venvManager.ts`**: **The Environment Manager.** Creates and manages Python virtual environments in VS Code global storage. Bootstraps dependencies on first activation.
*   **`simulationRunner.ts`**: **The Simulation Orchestrator.** Coordinates SPICE simulations via the Python package, supporting SKiDL and ngspice backends.

### C. The Python Package Domain (`python/hephaistus/`)
This self-contained Python package handles KiCad synchronization and SPICE simulation orchestration.

**KiCad Sync Module (`kicad_sync/`):**

*   **`kicad_update.py`**: **The Flow Coordinator.** This script coordinates the entire update process: loading schematic $\to$ computing delta $\to$ applying patches $\to$ saving backup.
    *   Dependencies: `delta.py`, `updater.py`.
*   **`delta.py`**: **The Comparator.** Reads both current `kicad_sch` (via parser) and `ledger.json` to compute the difference, identifying which components changed values or which new parts were added.
    *   Input: Schematic structure & JSON ledger state.
    *   Output: Structured dictionary of changes (`updated_values`, `new_parts`).
*   **`updater.py`**: **The Writer.** Takes the delta and applies physical updates to the schematic file, respecting spatial layout preservation rules (e.g., injecting new parts at a computed staging origin).
    *   Dependencies: `staging.py`, `utils.py`.

**Simulation Module (`simulation/`) — Planned:**

*   **`skidl_runner.py`**: SKiDL schematic generation and netlist export.
*   **`ngspice_runner.py`**: ngspice simulation execution and result parsing.
*   **`inspire_client.py`**: Circuit analysis and optimization via inspire.

### D. The User Experience (UI) Layer (`src/ui/`)
This layer handles presenting complex data and requiring user confirmation, separating 'what happened' from 'user approval'.

*   **`patchViewer.ts`**: Responsible for consuming the diff results ($\text{JSON}, \text{Python}, \text{KiCad}$) and rendering them into a structured view for manual review and approval via VS Code API commands (`hephaistus.approvePatch`).
*   **`llmWebView.ts` & `llmUIController.ts`**: Together manage the main chat interface, receiving and streaming LLM outputs (raw tokens) and presenting historical context, error messages, or simulation results.

## II. Component Interaction Map

This map details how components communicate during different phases:

| Phase/Action | Input Source(s) | Primary Service Triggered | Output Sink / Effect | Key Dependency Path |
|---|---|---|---|---|
| **1. Detection Cycle** | `kicad_sch` save event (File Watcher), State File (`state.json`) | `syncOrchestrator.ts` $\to$ `hephaistusService.ts` | Status Report / Issues List | `src/services/` |
| **2. Ingestion ($\text{KiCad} \to \text{JSON}$)** | `.kicad_sch` file path (from FileWatcher) | `ingestionService.ts` $\to$ `kicadParserService.ts` | Updated `.json` state in workspace | KiUtils Adapter, LLM fallback |
| **3. Semantic Drift ($\text{JSON} \leftrightarrow \text{Python}$)** | Loaded State (`stateHashes`) | `scriptUpdateService.ts` $\to$ `llmGenerateSync()` | Patched code snippets / Updated `.json` state in workspace | LLM Service, Patch Apply Service |
| **4. User Action (Patching)** | `hephaistus.approvePatch` command | `patchApplyService.ts` | Modification of target file (Python/JSON) and log creation | Logging system, State persistence |

## III. Critical Workflows Detail: KiCad $\to$ JSON Synchronization

The process is highly robust due to its layered fallback approach outlined in the code:

1. **KiCad Parsing (`kicadParserService.ts`):**
    *   **Priority 1 (Native):** Tries `kicadKiutilsAdapter.ts`, which spawns a Python wrapper calling external KiUtils binaries for semantic parsing.
    *   **Priority 2 (Fallback):** If KiUtils fails, it falls back to reading raw file content and generating a mock JSON structure, ensuring the system never halts due to missing dependencies.

2. **State Management (`hephaistusService.ts`):**
    *   The `analyzeState()` function is the gatekeeper. It compares the hash of the current `.kicad_sch` against the stored expectation in `stateHashes`. A mismatch immediately triggers an ingestion attempt, preventing stale data from corrupting the system.

3. **Python Patching (`patchApplyService.ts`):**
    *   All patches (whether generated by LLM or by UI action) are treated as abstract text replacements. They are applied via `applyPatch`, which guarantees logging and attempts to trigger an asynchronous full state sync after a successful write, closing the loop.

## IV. Tool/External Integration Summary

| External System | Interface Layer(s) | Interaction Goal |
|------------------|-------------------|----------------------|
| **KiCad CAD** | `python/hephaistus/kicad_sync/`, `src/services/kicadParserService.ts` | Read schema state; Write delta updates (read-only geometry, write parameters/new components). |
| **LLMs (Ollama/OpenRouter)** | `llmClientFactory.ts`, `llmService.ts` | Reasoning, planning, code generation, optimization proposal. |
| **VS Code API** | `extensionActivationHandler.ts`, `src/ui/*` | UI flow control, command registration, file watching, diff presentation. |
| **Python Environment** | `src/python/venvManager.ts`, `src/python/pythonBridge.ts` | Virtual environment management, process spawning. |
| **Python Package** | `python/hephaistus/` | KiCad parsing, SPICE simulation, circuit optimization. |
| **SKiDL/ngspice** | `python/hephaistus/simulation/` (planned) | Schematic generation and SPICE simulation execution. |

---

## V. Iterative Autonomy & Checkpoints

The optimization loop is not fully autonomous, nor is it one-shot approval. The LLM can iterate through multiple simulation cycles (troubleshoot, refine, retry) before interrupting the human.

### Iteration Budget

A configurable **silence budget** allows the LLM to run autonomous iterations (default N=3-5) before the human must acknowledge. This is crucial: analog optimization often requires 5-10 simulation runs to converge, and approving each one manually would break flow.

```
[User] "Optimize the LDO for efficiency"
    ↓
[LLM] Proposes values → Simulates → Analyzes → Refines (iteration 1)
    ↓
[LLM] Proposes adjusted values → Simulates → Analyzes (iteration 2)
    ↓
[LLM] Converged or stuck? Checkpoint prompt to user
    ↓
[User] Accept / Continue / Abort & Revert
```

### Savepoint & Revert Semantics

Before any optimization session begins, the current state is snapshotted:

- **`.hephaistus/backups/{timestamp}/`** — Contains schematic, JSON state, and Python scripts
- If the optimization diverges or the user aborts, they can revert to the last known-good state
- Similar to git's `stash` or `reflog` — you never lose work

### Implementation

| Component | Responsibility |
|-----------|---------------|
| `hephaistusService.ts` | Manage backups, snapshot/restore operations |
| `syncOrchestrator.ts` | Track iteration count, enforce budget |
| `src/ui/llmUIController.ts` | Render checkpoint prompts, handle user responses |

---

## VI. Schematic Modification Permissions

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

### Implementation

| Component | Responsibility |
|-----------|---------------|
| `hephaistusService.ts` | Track permission level setting |
| `syncOrchestrator.ts` | Enforce permission level before applying changes |
| `src/ui/llmUIController.ts` | Render intent expression, collect user decisions |

---

## VII. Stub Connections for Re-wiring

When the LLM needs to change a net connection, it creates "stubs" — logical connections that make the circuit simulatable while preserving user spatial control.

### How It Works

1. **LLM identifies needed connection:** "U1 pin 3 should connect to ground instead of VCC"
2. **Creates a stub in JSON state:** A logical connection that exists for simulation
3. **Marks it in KiCad:** Visual indicator showing "needs wiring"
4. **Simulation proceeds:** The stub makes the circuit simulatable with correct topology
5. **User completes wiring:** Opens KiCad, sees the stub, draws the actual wire
6. **Stub promotes to real connection:** On next sync, the stub is replaced by the actual wire

### Stub Representation

```json
{
  "type": "stub",
  "from": "U1.3",
  "to": "GND",
  "reason": "Input bias correction",
  "status": "pending",
  "created_at": "2026-07-15T18:20:00Z"
}
```

In KiCad, this renders as:
- A special symbol (e.g., `⚠STUB` label)
- A temporary wire with a visual marker
- A comment/note on the schematic

### Benefits

- **Circuit becomes simulatable immediately** — No waiting for user to re-wire
- **User retains spatial control** — They decide where the wire goes
- **Clear action items** — User sees exactly what needs manual attention
- **Reversible** — Backup before structural changes

### Implementation

| Component | Responsibility |
|-----------|---------------|
| `python/hephaistus/kicad_sync/` | Stub creation, promotion to real connections |
| `hephaistusService.ts` | Track pending stubs in state |
| `syncOrchestrator.ts` | Sync stub status with KiCad |

---

## VIII. Proactive Mistake Detection

The LLM can run a **review pass** on the schematic to detect issues before simulation.

### Trigger

- On save (configurable)
- On explicit request (`hephaistus.reviewSchematic`)
- Periodically (optional)

### Scope

| Category | Examples |
|----------|----------|
| Electrical rules | Floating inputs, shorted outputs, missing decoupling |
| Design rules | Voltage ratings, current ratings, power dissipation |
| Best practices | Bypass capacitors, proper grounding, stability margins |
| Topology errors | Wrong amplifier configuration, missing feedback paths |

### Review Output

```
📋 Schematic Review

⚠️ Medium: Missing decoupling capacitor
   C_bypass should be added near U1 power pins
   Proposing: 100nF ceramic capacitor between VCC/GND
   [Accept] [Ignore] [Learn more]

🔴 High: Voltage rating violation
   C2 is rated 6.3V but connected to 12V rail
   Proposing: Change to 25V rated capacitor
   [Accept] [Fix manually] [Dismiss]

ℹ️ Info: Suboptimal bias network
   R1/R2 ratio could be improved for lower quiescent current
   Proposing: R1=10kΩ→15kΩ, R2=4.7kΩ→6.8kΩ
   [Accept] [Ignore]
```

### Implementation

| Component | Responsibility |
|-----------|---------------|
| `syncOrchestrator.ts` | Trigger review pass |
| `llmService.ts` | Run review prompt, parse issues |
| `src/ui/llmUIController.ts` | Render review output, collect user decisions |
| `hephaistusService.ts` | Store dismissed issues, track accepted changes |

---

## X. Tiered Model Strategy

Not all tasks require frontier intelligence. The tool configures different model suppliers based on task complexity:

### Model Tiers

| Task | Model Tier | Reasoning |
|------|------------|-----------|
| JSON state sync | Local/cheap (Ollama, 3-8B) | Deterministic parsing, pattern matching |
| Ingestion fallback | Local/cheap | Same — KiCad→JSON is rule-based |
| Optimization proposal | Frontier (GLM, GPT-4, Claude) | Needs deep circuit understanding |
| Troubleshooting reasoning | Frontier | Needs domain knowledge and creativity |

### Configuration

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
    }
  }
}
```

### Implementation

| Component | Responsibility |
|-----------|---------------|
| `llmConfig.ts` | Parse model configuration, select endpoint by task type |
| `llmClientFactory.ts` | Create appropriate client (Ollama vs OpenRouter) |
| `llmService.ts` | Route requests: `llmGenerateSync()` for sync, `llmGenerateOptimization()` for optimization |

---

## XI. Multi-Audience Design

The tool serves three distinct audiences with different needs:

### Hobbyists

- Need simplicity and defaults that "just work"
- May not know technical terminology
- Want: Simple diff view, "Accept/Reject" buttons, sensible defaults
- UI Mode: **Simple** — Minimal configuration, clear outcomes

### Students

- Need pedagogical transparency — *why* each change was proposed
- Want: Annotations explaining reasoning, links to theory
- UI Mode: **Learning** — Expanded explanations, educational overlays

### Professionals

- Need control, visibility, and integration
- Want: Simulation waveforms, LLM reasoning logs, exportable reports
- UI Mode: **Advanced** — Full diagnostic views, custom model config

### Implementation

| Component | Responsibility |
|-----------|---------------|
| `extension.ts` | Detect user mode from settings |
| `src/ui/llmUIController.ts` | Render appropriate UI density based on mode |
| `hephaistusService.ts` | Include/exclude pedagogical annotations in state |

---

## XII. Extensible CAD Backend

Starting with KiCad, but the architecture is deliberately CAD-agnostic. The JSON ledger pattern abstracts away the specific file format.

### Adapter Pattern

```
python/hephaistus/
├── cad_sync/                 # Abstract CAD sync module
│   ├── __init__.py
│   ├── base_adapter.py       # Abstract base class
│   ├── kicad_adapter.py      # KiCad implementation
│   ├── plexs_adapter.py      # PLECS implementation (future)
│   └── gecko_adapter.py      # GeckoCircuits implementation (future)
└── simulation/
```

### Base Adapter Interface

```python
class CADAdapter(ABC):
    @abstractmethod
    def parse(self, file_path: str) -> dict:
        """Parse CAD file to JSON ledger format."""
        pass
    
    @abstractmethod
    def apply_delta(self, file_path: str, delta: dict) -> bool:
        """Apply changes to CAD file, preserving geometry."""
        pass
    
    @abstractmethod
    def create_stub(self, from_pin: str, to_net: str) -> dict:
        """Create a connection stub for re-wiring."""
        pass
    
    @abstractmethod
    def promote_stub(self, stub_id: str, wire_path: list) -> bool:
        """Promote stub to real wire after user completes wiring."""
        pass
```

### Future Targets

- **PLECS** — Power electronics simulation (thermal/electrical co-simulation)
- **GeckoCircuits** — Power electronics with SPICE backend
- **Altium/OrCAD/Eagle** — Commercial EDA tools

---

## XIII. Configuration Schema

Complete configuration schema for VS Code settings:

```json
{
  "hephaistus": {
    "models": {
      "sync": {
        "provider": "ollama | openrouter",
        "model": "string",
        "endpoint": "string (optional)"
      },
      "optimization": {
        "provider": "openrouter",
        "model": "string",
        "apiKey": "string (stored in VS Code Secrets)"
      }
    },
    "permissions": {
      "level": "values | add | delete | restructure"
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
    "review": {
      "onSave": false,
      "onRequest": true
    },
    "ui": {
      "mode": "simple | learning | advanced"
    },
    "execution": {
      "maxSteps": 100,
      "timeoutSeconds": 60
    }
  }
}
```