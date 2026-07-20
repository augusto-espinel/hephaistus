# PARSING.md — Superseded

> **This document has been consolidated into [architecture.md](./architecture.md).**
> 
> The parsing subsystem documentation is now maintained in Section 3 of architecture.md.

## Original Content (Archived)

The content below is preserved for reference but may be outdated.

---

## KiCad to JSON Parsing Algorithm

### Overview

The parser converts KiCad schematics (`.kicad_sch`) to JSON state for LLM reasoning and simulation.

### Implementation Status

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 1** | ✅ Complete | Property extraction (reference, value, SPICE params) |
| **Phase 2** | ✅ Complete | Pin-to-net mapping (net propagation through wires/junctions) |
| **Phase 3** | ✅ Complete | Wire/junction tracking for round-trip |
| **Phase 4** | ✅ Complete | Unnamed net detection (N$1, N$2, ...) |

For current documentation, see [architecture.md](./architecture.md).