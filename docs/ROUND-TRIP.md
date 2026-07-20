# ROUND-TRIP.md — Superseded

> **This document has been consolidated into [architecture.md](./architecture.md).**
> 
> The round-trip workflow documentation is now maintained in Section 4 and 5 of architecture.md.

## Original Content (Archived)

The content below is preserved for reference but may be outdated.

---

## Round-Trip Workflow

### Supported Operations

| Operation | Status | Description |
|-----------|--------|-------------|
| Value changes | ✅ Complete | Modifies `Value` property, preserves geometry |
| Component removal | ✅ Complete | Removes symbol, cleans orphan wires/junctions |
| Component addition | 📝 Planned | Requires library symbol lookup |
| Connection changes | 📝 Planned | Creates stub markers |

### Scripts

| Script | Purpose |
|--------|---------|
| `kiutils_parser_wrapper.py` | KiCad → JSON parsing |
| `kiutils_delta_apply.py` | JSON → KiCad delta application |

For current documentation, see:
- [architecture.md](./architecture.md) - Sections 4-5
- [TEST-MANUAL-ROUNDTRIP.md](./TEST-MANUAL-ROUNDTRIP.md) - Manual testing procedures