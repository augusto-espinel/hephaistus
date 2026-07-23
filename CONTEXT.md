# HephAIstus Project Context

> Read this file to quickly get up to speed with the project.

## What is HephAIstus?

HephAIstus is a VS Code extension that bridges KiCad schematic design with Python/SPICE simulation workflows. It enables **Decoupled Collaboration**: the engineer maintains spatial control of the visual schematic, while an LLM-backed agent handles mathematical optimization and simulation.

## Quick Start for AI Sessions

When starting a new session, read these files in order:

### 1. Vision & Use Cases
```
docs/vision.md
```
Start here. This explains *why* the project exists and *what* it's trying to achieve.

### 2. Architecture
```
docs/architecture.md
```
Technical architecture, component responsibilities, and design decisions.

### 3. Specification
```
docs/spec.md
```
File structure, service status, configuration schema, and implementation details.

### 4. Recent Memory Logs
```
~/.openclaw/workspace/memory/YYYY-MM-DD.md
```
Check the most recent memory files for the latest work, decisions, and context.

## Key Concepts

| Concept | Summary |
|---------|---------|
| **Decoupled Collaboration** | Human owns the canvas (geometry), AI owns the math (values, optimization) |
| **Three Pillars** | Schematic (.kicad_sch) ↔ JSON State (state.json) ↔ Python/SKiDL (simulation) |
| **Iteration Budget** | LLM can iterate N times autonomously before checkpoint |
| **Permission Levels** | `values` → `add` → `delete` → `restructure` (progressive trust) |
| **Stub Connections** | Logical connections for simulation, user draws physical wires later |
| **Tiered Models** | Local cheap models for sync, frontier models for optimization |

## Project Structure

```
hephaistus/
├── src/                    # TypeScript extension
│   ├── services/           # Core services (ingestion, patching, sync)
│   ├── python/             # Python bridge services
│   └── ui/                 # VS Code UI components
├── python/hephaistus/      # Python package
│   ├── kicad_sync/         # KiCad synchronization
│   └── simulation/         # SPICE simulation (planned)
├── fixtures/               # Test data
├── docs/                   # Documentation
│   ├── vision.md           # Vision and use cases
│   ├── architecture.md     # Technical architecture
│   ├── spec.md             # Implementation spec
│   └── python/             # Python module docs
└── tests/                  # Test suites
```

## Current Status (2026-07-21)

### Working ✅

- Extension activation
- File watcher detection
- Python/KiUtils path resolution
- KiCad 10 parsing
- JSON state generation
- State file tracking
- TypeScript compilation (0 errors)
- **Manual sync workflow**:
  - Parse KiCad → JSON (one-way)
  - Apply JSON → KiCad (one-way)
- **Sync status detection**:
  - Tracks last sync timestamp and source
  - Detects KiCad vs JSON newer states
  - Visual indicators (🔴/🔵/🟢)
- **Recommended action highlighting**
- **Confirmation dialogs** for destructive operations
- **Restore from JSON** - Discard KiCad changes option

### Known Limitations

- Component `reference`, `value`, `footprint` fields are empty (kiutils stores these in `symbolInstances`/properties, not `schematicSymbols`)
- LLM integration not yet wired
- Simulation module (SKiDL/ngspice) not implemented

### Last Milestone

**Manual Sync Workflow Complete (2026-07-21)**: Full bidirectional sync workflow with status detection, recommended action highlighting, and safety confirmation dialogs.

## Development Commands

```bash
npm run build      # Build TypeScript
npm run watch      # Watch mode
npm run package    # Package extension
npm run test       # Run tests
```

## Development Philosophy

From Augusto (project owner):

> The existing code was produced by less advanced models over multiple sessions without proper testing. It should be treated as design documentation showing intended architecture and data flow, not as working code. A major rework will be needed when development resumes.

## Commands to Bootstrap Context

In a new session, you can say:

```
Read the HephAIstus context file and get up to speed with the project.
```

Or more explicitly:

```
Read hephaistus/CONTEXT.md, then read docs/vision.md, docs/architecture.md, and the most recent memory logs.
```

## Repository

**GitHub:** https://github.com/augusto-espinel/hephaistus

The codebase is versioned and pushed to GitHub. Contributors can clone and follow this context file to get up to speed.

## Next Steps (Priority Order)

1. **Enhance component extraction** — Pull reference/value/footprint from `symbolInstances` (currently only in `properties`)
2. **Wire LLM integration** — Connect optimization model to ingestion
3. **Use consolidated test specs** — User: `docs/testing/USER-TESTS.md`; Agent: `docs/testing/AGENT-TESTS.md` (`npm run test:agent`)
4. **Test full workflow** — End-to-end with simulation
5. **Document sync workflow** — Add user guide for manual sync process

## Notes for AI

- The project targets hobbyists, students, and professionals — keep this audience range in mind
- The "stubs" pattern for re-wiring is key: logical connections for simulation, user retains spatial control
- The project is KiCad-first but architecturally CAD-agnostic (PLECS, GeckoCircuits future targets)
- Always check memory logs for the latest decisions and context before making changes
- **GitHub repo exists** — commit significant changes, keep .gitignore updated
