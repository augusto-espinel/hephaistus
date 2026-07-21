# HephAIstus - VS Code Extension Specification

For vision and use cases, see [vision.md](./vision.md). For architecture details, see [architecture.md](./architecture.md). For manual testing, see [TEST-MANUAL-ROUNDTRIP.md](./TEST-MANUAL-ROUNDTRIP.md).

## Executive Summary

HephAIstus is a VS Code extension bridging KiCad schematic design with Python/SPICE simulation workflows. It enables **Decoupled Collaboration**: the engineer maintains spatial control of the visual schematic, while an LLM-backed agent handles mathematical optimization and simulation in the background.

The system operates across three pillars:
1. **Schematic** (`.kicad_sch`) — Human's source of truth; geometry is immutable
2. **JSON State** (`.hephaistus/*.json`) — Machine-readable ledger for LLM reasoning
3. **Code** (Python/SKiDL) — Simulation catalyst for iterative optimization

---

## Implementation Status Summary

| Subsystem | Status | Notes |
|-----------|--------|-------|
| KiCad → JSON Parsing | ✅ Complete | Full component/net extraction |
| JSON → KiCad Delta Apply | ✅ Complete | Value changes, component removal, component addition |
| VS Code Extension | ✅ Complete | File watchers, sync panel |
| Round-Trip Integration | ✅ Complete | Both directions working |
| Warning System | ✅ Complete | Series insertion, missing labels detection |
| LLM Integration | 📝 Planned | SKiDL code generation |
| SPICE Simulation | 📋 Planned | ngspice execution |

---

### Extension Host Services

The extension runs in VS Code's Extension Host and provides:

| Service | File | Status | Description |
|---------|------|--------|-------------|
| Extension Entry | `src/extension.ts` | ✅ Complete | Command registration, file watcher setup |
| Sync Orchestrator | `src/syncOrchestrator.ts` | ✅ Complete | Coordinates ingestion, delta apply, loop prevention |
| State Manager | `src/stateManager.ts` | ✅ Complete | Project state persistence |
| LLM Service | `src/llmService.ts` | ✅ Complete | High-level LLM generation wrappers |
| LLM Config | `src/llmConfig.ts` | ✅ Complete | Ollama/OpenRouter backend configuration |

### Core Services (`src/services/`)

| Service | File | Status | Description |
|---------|------|--------|-------------|
| Ingestion Service | `ingestionService.ts` | ✅ Complete | KiCad → JSON ingestion via KiUtils |
| Delta Apply Service | `deltaApplyService.ts` | ✅ Complete | JSON → KiCad delta application |
| State Manager | `stateManager.ts` | ✅ Complete | Project state with sync tracking |
| KiCad Parser Service | `kicadParserService.ts` | ✅ Complete | Routes to KiUtils parser |
| KiUtils Adapter | `kicadKiutilsAdapter.ts` | ✅ Complete | Python bridge for KiUtils |
| Patch Apply Service | `patchApplyService.ts` | ✅ Complete | Deterministic patch application |

### State Tracking

The `ProjectState` interface tracks sync history:

```typescript
interface ProjectState {
    // ... other fields ...
    lastSync?: {
        source: 'kicad' | 'json';
        timestamp: string;
        kicadHash?: string;  // Future: detect touch operations
        jsonHash?: string;   // Future: verify round-trip integrity
    };
}
```

**Purpose:** Distinguish between "JSON newer after parse" (synced) vs "JSON newer after manual edit" (needs apply).

### UI Components (`src/ui/`)

| Component | File | Status | Description |
|-----------|------|--------|-------------|
| Sync Panel | `syncPanel.ts` | ✅ Complete | Manual sync panel with status indicators |
| LLM Webview | `llmWebView.ts` | 📝 Planned | Webview panel for LLM interaction |
| Patch Viewer | `patchViewer.ts` | ✅ Complete | Patch preview rendering |

### Utilities (`src/`)

| Utility | File | Status | Description |
|---------|------|--------|-------------|
| Core Utils | `utils.ts` | ✅ Complete | File hashing, workspace paths |
| Hephaistus Service | `hephaistusService.ts` | ✅ Complete | State management, change detection |

---

## Python Package: `python/hephaistus/`

A Python package for KiCad schematic synchronization and SPICE simulation:

### Package Structure

| Module | Status | Description |
|--------|--------|-------------|
| `hephaistus/__init__.py` | ✅ Implemented | Package entrypoint |
| `hephaistus/kicad_sync/` | ✅ Implemented | KiCad synchronization module |
| `hephaistus/simulation/` | 📋 Planned | SPICE simulation orchestration |
| `hephaistus/utils/` | ✅ Implemented | Common utilities |

### KiCad Sync Module (`kicad_sync/`)

| File | Status | Description |
|------|--------|-------------|
| `__init__.py` | ✅ Implemented | Module entrypoint |
| `kicad_update.py` | ✅ Implemented | Orchestrator for delta computation and updates |
| `delta.py` | ✅ Implemented | Delta computation between schematic and ledger |
| `updater.py` | ✅ Implemented | Apply updates to schematic (KiCad or JSON fallback) |
| `staging.py` | ✅ Implemented | Staging origin computation for new parts |
| `utils.py` | ✅ Implemented | Helper utilities |

### Simulation Module (`simulation/`) — Planned

| File | Status | Description |
|------|--------|-------------|
| `skidl_runner.py` | 📋 Planned | SKiDL schematic generation |
| `ngspice_runner.py` | 📋 Planned | ngspice simulation execution |
| `inspire_client.py` | 📋 Planned | inspire integration |

### Python Tests (`tests/python/`)

| File | Status | Description |
|------|--------|-------------|
| `test_kicad_sync.py` | 📋 Planned | KiCad sync unit tests |
| `test_simulation.py` | 📋 Planned | Simulation unit tests |
| `ingest_align.py` | ✅ Implemented | Ingestion alignment test |
| `min_run_delta.py` | ✅ Implemented | Minimal delta run test |

### KiCad Sync Workflow

1. **Load**: Parse schematic.kicad_sch into in-memory JSON model
2. **Compare**: Compute delta against ledger.json
3. **Update**: Apply value changes (preserve positions), inject new parts at staging origin
4. **Validate**: Re-parse and save with timestamped backup

---

## Python Bridge Services (`src/python/`)

TypeScript services that bridge to the Python package:

| Service | File | Status | Description |
|---------|------|--------|-------------|
| Python Bridge | `pythonBridge.ts` | ✅ Implemented | Spawns Python processes from TypeScript |
| Venv Manager | `venvManager.ts` | ✅ Implemented | Creates and manages Python virtual environments |
| Simulation Runner | `simulationRunner.ts` | ✅ Implemented | Orchestrates SPICE simulations via Python |

## Tools & Scripts

| Tool | Status | Description |
|------|--------|-------------|
| `scripts/bootstrap-venv.sh` | ✅ Implemented | Bootstrap Python virtual environment |
| `scripts/postinstall.js` | ✅ Implemented | npm postinstall hook for Python setup |
| `scripts/wrappers/kiutils_parser_wrapper.py` | ✅ Implemented | Python wrapper for KiUtils parsing |
| `scripts/wrappers/kicad_parser.py` | ✅ Implemented | KiCad parser script |

---

## Extension Commands

Defined in `package.json`:

| Command | ID | Status | Description |
|---------|-----|--------|-------------|
| Start Session | `hephaistus.startSession` | 🔶 Placeholder | Initialize HephAIstus session |
| Approve Patch | `hephaistus.approvePatch` | 🔶 Placeholder | Approve pending patch |
| Reject Patch | `hephaistus.rejectPatch` | 🔶 Placeholder | Reject pending patch |

---

## Configuration

### VS Code Settings (`contributes.configuration`)

**Model Configuration (Tiered):**

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `hephaistus.models.sync.provider` | string | `"ollama"` | Provider for sync tasks (ollama, openrouter) |
| `hephaistus.models.sync.model` | string | `"llama3:8b"` | Model for sync/ingestion tasks |
| `hephaistus.models.sync.endpoint` | string | `"http://localhost:11434"` | Endpoint for local models |
| `hephaistus.models.optimization.provider` | string | `"openrouter"` | Provider for optimization tasks |
| `hephaistus.models.optimization.model` | string | `"google/gemini-2.5-flash"` | Model for optimization tasks |
| `hephaistus.models.optimization.apiKey` | string | `""` | API key (stored in VS Code Secrets) |

**Permission Levels:**

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `hephaistus.permissions.level` | string | `"add"` | Modification permission: values, add, delete, restructure |

**Iteration Budget:**

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `hephaistus.iteration.maxAutonomousIterations` | number | `5` | Max LLM iterations before checkpoint |
| `hephaistus.iteration.checkpointOnStart` | boolean | `true` | Create backup before optimization |
| `hephaistus.iteration.autoRevertOnAbort` | boolean | `true` | Revert to backup on abort |

**Backup:**

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `hephaistus.backup.enabled` | boolean | `true` | Enable automatic backups |
| `hephaistus.backup.maxBackups` | number | `10` | Maximum backups to retain |

**Review:**

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `hephaistus.review.onSave` | boolean | `false` | Run review on save |
| `hephaistus.review.onRequest` | boolean | `true` | Run review on explicit request |

**UI Mode:**

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `hephaistus.ui.mode` | string | `"simple"` | UI density: simple, learning, advanced |

**Execution:**

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `hephaistus.execution.maxSteps` | number | `100` | Max simulation steps |
| `hephaistus.execution.timeoutSeconds` | number | `60` | Simulation timeout |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KICAD_PARSER_BACKEND` | `mock` | Parser backend: `mock`, `kiutils`, or `kiutils-node` |
| `KIUTILS_PYTHON_BIN` | `.venv/bin/python` | Python binary for KiUtils |
| `KIUTILS_WRAPPER_PATH` | `scripts/wrappers/kiutils_parser_wrapper.py` | Wrapper script path |

---

## Sync Orchestrator Flow

```
runSyncCycle(state)
├── needsIngestion && kicadFilePath?
│   └── executeIngestionPhase()
│       ├── parseKiCadToJson() [KiUtils or mock]
│       ├── calculateSemanticKicadHash()
│       └── writeToFile(json)
└── stateHashes exist?
    └── updateScriptsIfNeeded()
        └── llmGenerateSync() → applyPatch()
```

---

## Ingestion Phase

The ingestion service (`ingestionService.ts`) implements KiCad → JSON conversion:

1. **Parser Selection**: Routes to KiUtils adapter if `KICAD_PARSER_BACKEND=kiutils`, otherwise falls back to mock
2. **Semantic Hash**: Computes SHA-256 hash of KiCad content for provenance
3. **LLM Fallback**: If parser fails, requests LLM to regenerate JSON structure
4. **Persistence**: Writes JSON state to workspace

---

## Patch Application

The patch service (`patchApplyService.ts`) supports two formats:

### JSON Payload
```json
[
  {"file": "path/to/file.py", "find": "old_text", "replace": "new_text"}
]
```

### DSL Format
```
PATCH-FILE: path/to/file.py
REPLACE old_text WITH new_text
END-PATCH
```

Applied patches are logged to `patch-logs/` with timestamps and trigger async sync cycle.

---

## LLM Backends

### Ollama (Local)
- Endpoint: `http://localhost:11434/api/generate`
- Configuration: `hephaistus.ollama.endpoint`
- Graceful fallback when offline

### OpenRouter (Cloud)
- Endpoint: `https://openrouter.ai/api/v1/chat/completions`
- Model: `google/gemini-2.5-flash` (default)
- Configuration: `hephaistus.openrouter.apiKey`

---

## Optimization Workflow

### Iterative Autonomy

The optimization loop is not fully autonomous, nor is it one-shot approval. The LLM can iterate through multiple simulation cycles before interrupting the human:

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

**Key concepts:**

- **Iteration Budget:** Configurable number of autonomous iterations (default 5) before checkpoint
- **Backups:** State snapshot before optimization, restorable on abort
- **Batch Approval:** User approves a batch of changes, not each iteration

### Multi-Audience UI Modes

| Mode | Audience | Characteristics |
|------|----------|----------------|
| Simple | Hobbyists | Minimal config, clear outcomes, Accept/Reject only |
| Learning | Students | Annotations explain reasoning, links to theory |
| Advanced | Professionals | Full diagnostics, waveforms, LLM logs, custom config |

---

## Schematic Modification Permissions

The LLM can perform different types of modifications depending on user permission level:

| Level | Operations Allowed | Use Case |
|-------|-------------------|----------|
| `values` | Modify component values only | Conservative, safe mode |
| `add` | Values + Add components to staging area | Missing components |
| `delete` | Values + Add + Mark for removal | Redundant components |
| `restructure` | All above + Add connection stubs | Topology corrections |

**Default:** `add`

**Philosophy:** Minimum needed changes to achieve the goal. No speculative "improvements."

---

## Stub Connections

When the LLM needs to change a net connection, it creates "stubs" — logical connections that make the circuit simulatable while preserving user spatial control:

```json
{
  "type": "stub",
  "from": "U1.3",
  "to": "GND",
  "reason": "Input bias correction",
  "status": "pending"
}
```

**How it works:**

1. LLM identifies needed connection
2. Creates stub in JSON state (logical connection for simulation)
3. Marks it in KiCad (visual indicator)
4. Simulation proceeds with correct topology
5. User completes wiring in KiCad
6. Stub promotes to real connection on next sync

---

## Proactive Mistake Detection

The LLM can run a **review pass** on the schematic:

| Trigger | Config |
|---------|--------|
| On save | `hephaistus.review.onSave: false` |
| On request | `hephaistus.review.onRequest: true` |

**Categories:**

- Electrical rules (floating inputs, shorted outputs, missing decoupling)
- Design rules (voltage/current ratings, power dissipation)
- Best practices (bypass capacitors, proper grounding)
- Topology errors (wrong configuration, missing feedback)

---

## Gap Analysis

| Gap | Priority | Status | Remediation |
|-----|----------|--------|-------------|
| Parser Wiring | High | 🔶 Partial | KiUtils adapter wired; fallback to mock working |
| End-to-End Patch | High | 🔶 Open | UI patch → apply → state refresh not wired |
| UI Command Mapping | Medium | 🔶 Open | Commands registered but placeholder logic |
| Workspace Path Normalization | Medium | ✅ Resolved | `WORKSPACE_ROOT` centralized in `utils.ts` |
| Testing & Validation | Medium | 🔶 Partial | Test scaffolds exist in `tests/` and `kicad_sync/tests/` |

---

## File Structure

```
hephaistus/
├── .vscode/                           # VS Code development config
├── src/                                # TypeScript extension
│   ├── extension.ts                    # Extension entrypoint
│   ├── extensionActivationHandler.ts   # Activation wiring
│   ├── syncOrchestrator.ts             # Central orchestrator
│   ├── llmService.ts                   # LLM generation
│   ├── llmConfig.ts                    # Backend config
│   ├── llmClientFactory.ts             # Client factory
│   ├── fileWatcherService.ts           # File watching
│   ├── hephaistusService.ts            # State management
│   ├── hephaistusServiceBridge.ts      # Bridge
│   ├── hephaistusServiceOrchestratorWrapper.ts
│   ├── utils.ts                        # Utilities
│   ├── services/
│   │   ├── ingestionService.ts         # KiCad → JSON
│   │   ├── kicadParserService.ts       # Parser routing
│   │   ├── kicadKiutilsAdapter.ts      # KiUtils bridge
│   │   ├── patchApplyService.ts       # Patch application
│   │   ├── patchUtils.ts              # Diff utilities
│   │   └── scriptUpdateService.ts     # Script drift
│   ├── python/                         # Python bridge services
│   │   ├── pythonBridge.ts            # Spawn Python processes
│   │   ├── venvManager.ts             # Manage virtual environments
│   │   └── simulationRunner.ts        # SPICE simulation orchestration
│   └── ui/
│       ├── llmWebView.ts              # Webview stub
│       ├── patchViewer.ts             # Patch preview
│       ├── llmUIController.ts         # UI controller stub
│       └── uiBridge.ts                # UI bridge stub
├── python/                             # Python package
│   ├── hephaistus/                     # Main package
│   │   ├── __init__.py
│   │   ├── kicad_sync/                 # KiCad synchronization
│   │   │   ├── __init__.py
│   │   │   ├── kicad_update.py
│   │   │   ├── delta.py
│   │   │   ├── updater.py
│   │   │   ├── staging.py
│   │   │   └── utils.py
│   │   ├── simulation/                 # SPICE simulation (planned)
│   │   │   └── __init__.py
│   │   └── utils/                      # Common utilities
│   │       └── __init__.py
│   ├── requirements.txt                # Python dependencies
│   ├── pyproject.toml                  # Modern Python packaging
│   └── setup.py                        # Legacy pip support
├── scripts/                            # Utility scripts
│   ├── bootstrap-venv.sh               # Bootstrap Python venv
│   ├── postinstall.js                  # npm postinstall hook
│   └── wrappers/                       # Python wrapper scripts
│       ├── kiutils_parser_wrapper.py
│       └── kicad_parser.py
├── tests/                              # Test suites
│   ├── typescript/                     # TypeScript tests
│   │   ├── ingestion-phase.test.ts
│   │   └── kiutils-adapter.test.ts
│   └── python/                         # Python tests
│       ├── ingest_align.py
│       └── min_run_delta.py
├── fixtures/                           # Test fixtures
│   ├── schematics/
│   │   └── schematic.kicad_sch
│   ├── ledgers/
│   │   ├── ledger.json
│   │   └── ledger_aligned.json
│   └── simulations/                    # Simulation fixtures (planned)
├── docs/                               # Documentation
│   ├── spec.md                         # This file
│   ├── architecture.md                 # Architecture details
│   ├── python/                         # Python documentation
│   │   ├── kicad-sync.md
│   │   ├── kicad-sync-spec.md
│   │   ├── kicad-sync-readme.md
│   │   └── testing.md
│   └── diff-reports/
│       ├── diff-spec-code.json
│       ├── gap-backlog.json
│       └── kicad-kiutils-workflow.md
├── out/                                # Compiled JS (gitignored)
├── .vscodeignore                       # Files to exclude from vsix
├── package.json
├── tsconfig.json
├── README.md
└── CHANGELOG.md
```

---

## Status Legend

| Icon | Status |
|------|--------|
| ✅ | Implemented and functional |
| 🔶 | Stub or partial implementation |
| ❌ | Not yet implemented |
| 📋 | Planned |

---

## Next Steps

1. **Wire UI Patch Lifecycle**: Connect `approvePatch`/`rejectPatch` commands to `patchApplyService`
2. **Implement Session Initialization**: Flesh out `startSession` command logic
3. **Complete Webview UI**: Implement `llmWebView.ts` streaming and interaction
4. **Add Simulation Runner**: Create `SimulationRunner` service for headless SPICE execution
5. **Expand Test Coverage**: Add integration tests for full sync cycle