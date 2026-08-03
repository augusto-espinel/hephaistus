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
| **Stub Connections** | Connectivity applied as wire+label stubs; nets split/join via clear-and-stub restructuring |
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

## Current Status (2026-08-04)

### Working ✅

- Extension activation
- File watcher detection
- Python/KiUtils path resolution
- KiCad 10 parsing (including multi-island stub nets sharing a label)
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
- **Stub-based apply flow** (2026-08-04):
  - Component additions: staging placement + per-pin stubs, KiCad 6+ instance format
  - Net restructuring: series insertion / net splits applied via clear-and-stub
  - Library auto-embedding: missing lib symbols pulled from installed KiCad libraries
  - Residual warnings only (missing library, power-net anchor)
- **Agent E2E suite**: `tests/agent/stub_apply_e2e.py` — 26 checks, 6 scenarios; `kicad-cli` ERC clean

### Known Limitations

- Symbols using `(extends ...)` inheritance can't be auto-embedded yet
- Restructured nets lose drawn wires (stubs guarantee connectivity, not aesthetics) — user redraws when convenient
- LLM integration not yet wired
- Simulation module (SKiDL/ngspice) not implemented

### Last Milestone

**Stub-Based Net Restructuring (2026-08-04)**: The apply flow was rebuilt around stubs (wire + net label) instead of physical wire-breaking advice. Series insertion and net splits are expressed purely as pin net re-assignments in JSON and applied deterministically. Commit `30414da`.

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

1. **Validate stub apply in KiCad GUI** — Augusto to open stub-applied schematics (E2E S1/S4 scenarios) and judge ergonomics
2. **Wire LLM integration** — Connect optimization model to ingestion; the AI contract is now purely logical (pin net re-assignments)
3. **Use consolidated test specs** — User: `docs/testing/USER-TESTS.md`; Agent: `docs/testing/AGENT-TESTS.md` (`npm run test:agent`, stub E2E via `.venv/bin/python3 tests/agent/stub_apply_e2e.py`)
4. **Test full workflow** — End-to-end with simulation (stub-applied schematics are simulatable immediately)
5. **Advice ledger (optional cleanup)** — Track aesthetic re-wiring suggestions as verifiable advice (`docs/use_cases_blueprint.md` §2)

## Notes for AI

- The project targets hobbyists, students, and professionals — keep this audience range in mind
- The "stubs" pattern is now the applied mechanism, not just a pattern: all new connectivity is wire+label stubs; restructured nets are cleared and re-stubbed. Users redraw wires only for aesthetics
- The project is KiCad-first but architecturally CAD-agnostic (PLECS, GeckoCircuits future targets)
- Always check memory logs for the latest decisions and context before making changes
- **GitHub repo exists** — commit significant changes, keep .gitignore updated
