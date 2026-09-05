# HephAIstus

HephAIstus is an AI copilot for KiCad schematic design and circuit simulation.

It sits beside KiCad, understands schematic and simulation context, answers engineering questions, and applies previewable, validated changes without requiring the user to copy files, screenshots, or console output into an external chat.

## Documentation Guide

### Start Here

- **[`CONTEXT.md`](CONTEXT.md)** — Project summary, architecture overview, and document map. Start here if you're new to the project.
- **[`docs/vision.md`](docs/vision.md)** — One-sentence mission, problem statement, and operating principles.

### By Task

| Task | Read |
|------|------|
| Understanding the product | `docs/vision.md` → `docs/spec.md` |
| Architecture and components | `docs/ARCHITECTURE.md` |
| Patch operations (LLM output contract) | `docs/patch-plan-v1.md` |
| User experience scenarios | `docs/use_cases_blueprint.md` |
| Testing procedures | `docs/TEST-MANUAL.md` |
| Implementation deep dives | `backend/hephaistus_circuit/IMPLEMENTATION.md`, `backend/hephaistus_context/IMPLEMENTATION.md` |
| LLM context assembly | `docs/LLM_CONTEXT.md` |

### Reference Documents

| Document | Scope |
|----------|-------|
| `docs/spec.md` | Product specification: workflows, validation gates, acceptance criteria |
| `docs/ARCHITECTURE.md` | Technical architecture: components, data flow, implementation status |
| `docs/patch-plan-v1.md` | JSON schema for LLM-produced mutation plans |
| `docs/use_cases_blueprint.md` | User stories and milestone mapping |
| `docs/TEST-MANUAL.md` | Manual test procedures |
| `docs/migration-from-vscode-prototype.md` | Historical context for the VS Code extension archive |

## Product Direction

The target workflow is:

1. Open a KiCad schematic or simulation window.
2. Ask HephAIstus about the circuit, ERC report, simulation parameters, console output, or waveform results.
3. Receive explanations or a deterministic patch plan.
4. Preview the proposed change.
5. Apply it only after validation.
6. Re-run ERC and/or simulation automatically.
7. Keep an auditable history with rollback information.

## Implementation Status

### Completed

| Component | Description |
|-----------|-------------|
| KiCad ingestion | Parse `.kicad_sch` to JSON state |
| Patch operations | 7 operation types with validation |
| Stub-based restructuring | Series insertions, net reassignments |
| SPICE property inheritance | Auto-copy `Sim.*` properties from libraries |
| Simulation output parsing | Ngspice console, DC op, raw waveforms |
| Session persistence | Project-scoped sessions in `.hephaistus/` |
| LLM context assembly | Token-budgeted layered context |
| Companion UI | React-based chat, context inspector, history |

### In Progress

- Simulation execution (beyond ingestion)
- KiCad IPC integration (future)

## Quick Start

```bash
# Clone and setup
git clone https://github.com/your-org/hephaistus.git
cd hephaistus
python -m venv .venv
source .venv/bin/activate
pip install -e .

# Run tests
python -m pytest tests/ -v

# Parse a schematic
python -m hephaistus_circuit.cli parse fixtures/schematics/rectifier.kicad_sch

# Apply a patch plan (dry-run)
python -m hephaistus_circuit.cli apply-plan fixtures/schematics/rectifier.kicad_sch examples/patches/insert_shunt.json --dry-run
```

## Branch Information

- Active branch: `feature/companion-reset`
- Archive: `archive/vscode-prototype` (tag: `vscode-prototype-2026-08-19`)

## License

[License information here]