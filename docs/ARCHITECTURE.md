# HephAIstus Architecture

Version: 3.0
Date: 2026-09-05

## Overview

HephAIstus is organized into four primary layers:

1. **Deterministic backend** — File parsing, patch validation, KiCad CLI, simulation
2. **LLM orchestration** — Context assembly, prompt construction, patch extraction
3. **Companion UI** — Chat, context inspector, patch preview, simulation history
4. **Future KiCad adapter** — Optional IPC/plugin integration

```
KiCad project files
    ↓ parser
JSON state (components, nets, pins)
    ↓ context service
LLM (produces patch-plan)
    ↓ validation
Patch backend (text-level apply)
    ↓ round-trip
KiCad schematic (modified)
```

## 1. Backend Layer

### 1.1 Parser (`hephaistus_circuit/parser.py`)

**Responsibility:** Parse `.kicad_sch` into structured JSON state.

**Output:**
- Components with UUIDs, references, values, pins, positions
- Nets with names and member pins
- Text elements (simulation directives)
- Library symbol references with embedded properties

**Key fix (2026-09-04):** Y-coordinate transformation for rotated components. KiCad library symbols use Y-UP, schematics use Y-DOWN.

**Implementation:** See [`backend/hephaistus_circuit/IMPLEMENTATION.md`](../backend/hephaistus_circuit/IMPLEMENTATION.md)

### 1.2 Patch Engine (`hephaistus_circuit/engine.py`)

**Responsibility:** Validate and apply patch-plan operations.

**Supported operations (7):**
- `pin.assign_net` — Assign a pin to a net
- `net.split` — Move pins to a new net
- `component.add` — Add a new component
- `component.update_value` — Change component value
- `component.remove` — Remove a component
- `simulation.set_directive` — Create/update SPICE directive
- `simulation.remove_directive` — Remove SPICE directive

**Validation flow:**
1. Schema validation
2. Semantic validation (references exist)
3. Integrity validation (no duplicate UUIDs)
4. Round-trip validation (parse after write)

**Implementation:** See [`docs/patch-plan-v1.md`](patch-plan-v1.md) for schema, [`backend/hephaistus_circuit/IMPLEMENTATION.md`](../backend/hephaistus_circuit/IMPLEMENTATION.md) for details.

### 1.3 Text Apply (`hephaistus_circuit/text_apply.py`)

**Responsibility:** Apply JSON state deltas to schematic text.

**Key patterns:**
- **Stub-based restructuring:** Series insertions expressed as pin re-assignments
- **Library embedding:** Auto-embed missing symbols from sym-lib-table
- **SPICE property inheritance:** Copy `Sim.*` properties from library to instance

**Implementation:** See [`backend/hephaistus_circuit/IMPLEMENTATION.md`](../backend/hephaistus_circuit/IMPLEMENTATION.md)

### 1.4 Simulation Parser (`hephaistus_simulation/parser.py`)

**Responsibility:** Parse ngspice output into structured data.

**Input formats:**
- Console output (analyses, convergence, errors)
- DC operating points (`V(node) = value`)
- Raw waveforms (binary format with metadata)

**Output:** Structured data for LLM context.

### 1.5 Session Persistence

**Location:** `<project>/.hephaistus/`

```
.hephaistus/
├── session.json      # Current session state
├── history.db        # Conversation history (SQLite/FTS5)
└── simulations/
    ├── current/      # Active simulation
    └── history/      # FIFO archive (last 5 runs)
```

**API endpoints:**
- `POST /api/schematic/load` — Load schematic, discover project root
- `GET /api/session/status` — Current session state
- `POST /api/session/restore` — Restore saved session

## 2. LLM Layer

### 2.1 Context Service (`hephaistus_context/context_service.py`)

**Responsibility:** Assemble token-budgeted context for LLM.

**Layers (priority order):**
| Layer | Priority | Content |
|-------|----------|---------|
| System | Critical | Identity, schema, validation contract |
| Session | Critical | Schematic state, simulation staleness |
| History | High | Recent exchanges + summaries |
| Reasoning | Medium | Key decisions with rationale |
| Simulation | Low | DC OP, signal summaries |

**Implementation:** See [`docs/LLM_CONTEXT.md`](LLM_CONTEXT.md) and [`backend/hephaistus_context/IMPLEMENTATION.md`](../backend/hephaistus_context/IMPLEMENTATION.md)

### 2.2 Orchestrator (`hephaistus_llm/orchestrator.py`)

**Responsibility:** Manage LLM providers and extract patch-plans.

**Providers:**
- Ollama (local)
- OpenRouter (remote models)

**Output extraction:** Parse JSON from LLM response, validate against schema.

### 2.3 System Prompt

**Location:** `hephaistus_llm/orchestrator.py`

**Contains:**
- Identity and operating principles
- Patch-plan schema reference
- Output discipline (no internal reasoning)
- Error code reference

## 3. Companion UI

**Stack:** React + TypeScript + Vite

**Panels:**
- Chat — Message history with markdown/KaTeX
- Context Inspector — LLM prompt assembly
- Session Status — Schematic, simulation staleness
- Settings — LLM provider/model selection

**Status:** ✅ Complete (2026-08-24)

## 4. Future KiCad Adapter

**Status:** Optional, blocked on KiCad IPC support for schematics.

**When available:**
- Current-document awareness
- Selection awareness
- Embedded launch surface

## 5. Safety Architecture

### 5.1 File Safety
- Never mutate without validated plan + confirmation
- Create backups before changes
- Check for live KiCad unsaved-state conflicts

### 5.2 LLM Safety
- LLM cannot directly write files
- Hallucinated references fail validation
- Destructive operations require explicit confirmation
- All changes logged for audit

### 5.3 Simulation Safety
- Parameter changes are patches (previewable)
- Convergence failures are diagnostics, not hidden
- Result comparisons shown with metadata

## 6. Implementation Milestones

| Milestone | Status | Date |
|-----------|--------|------|
| KiCad ingestion | ✅ Complete | 2026-07-18 |
| Stub-based restructuring | ✅ Complete | 2026-08-04 |
| Simulation output parsing | ✅ Complete | 2026-08-20 |
| Session persistence | ✅ Complete | 2026-08-21 |
| SPICE property inheritance | ✅ Complete | 2026-09-03 |
| Y-coordinate fix | ✅ Complete | 2026-09-04 |
| LLM context assembly | ✅ Complete | 2026-08-22 |
| Companion UI | ✅ Complete | 2026-08-24 |

## 7. Related Documents

| Document | Purpose |
|----------|---------|
| [`CONTEXT.md`](../CONTEXT.md) | Quick start, status |
| [`AGENT.md`](AGENT.md) | Agent orientation |
| [`docs/patch-plan-v1.md`](patch-plan-v1.md) | Patch-plan schema |
| [`docs/LLM_CONTEXT.md`](LLM_CONTEXT.md) | Context assembly details |
| [`backend/hephaistus_circuit/IMPLEMENTATION.md`](../backend/hephaistus_circuit/IMPLEMENTATION.md) | Engine implementation |
| [`backend/hephaistus_context/IMPLEMENTATION.md`](../backend/hephaistus_context/IMPLEMENTATION.md) | Context implementation |