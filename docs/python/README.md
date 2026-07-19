# Python Package Documentation

This directory contains documentation for the HephAIstus Python package.

## Modules

### [KiCad Sync](./kicad-sync.md)

KiCad schematic synchronization module for bidirectional flow between `.kicad_sch` files and JSON state ledgers.

**Key Features:**
- Parse KiCad schematics via KiUtils
- Compute deltas between schematic and ledger
- Apply updates while preserving spatial layout
- Staging area for new components

### [Testing](./testing.md)

Testing guide for Python modules, including pytest configuration and test fixtures.

### [KiCad Sync Spec](./kicad-sync-spec.md)

Detailed specification for the KiCad synchronization workflow.

## Package Structure

```
python/hephaistus/
├── __init__.py
├── kicad_sync/          # KiCad synchronization
│   ├── __init__.py
│   ├── kicad_update.py  # Main orchestrator
│   ├── delta.py         # Delta computation
│   ├── updater.py       # Apply updates
│   ├── staging.py       # Staging origin
│   └── utils.py         # Helper utilities
├── simulation/          # SPICE simulation (planned)
│   └── __init__.py
└── utils/               # Common utilities
    └── __init__.py
```

## Dependencies

See [requirements.txt](../python/requirements.txt) for the full dependency list.

**Core Dependencies:**
- `kiutils` — KiCad file parsing
- `skidl` — Python-based schematic generation (optional)
- `ngspice` — SPICE simulation (optional)

## Installation

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install package in development mode
pip install -e .
```