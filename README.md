# HephAIstus

HephAIstus is an AI copilot for KiCad schematic design and circuit simulation.

It is being rebuilt as a **companion application** that sits beside KiCad, understands schematic and simulation context, answers engineering questions, and applies previewable, validated changes without requiring the user to copy files, screenshots, or console output into an external chat.

## Current branch

`feature/companion-reset` is a deliberate architectural reset. The previous VS Code extension prototype is preserved in:

- Branch: `archive/vscode-prototype`
- Tag: `vscode-prototype-2026-08-19`
- Optional local worktree: `../hephaistus-legacy`

## Product direction

The target workflow is:

1. Open a KiCad schematic or simulation window.
2. Ask HephAIstus about the circuit, ERC report, simulation parameters, console output, or waveform results.
3. Receive explanations or a deterministic patch plan.
4. Preview the proposed change.
5. Apply it only after validation.
6. Re-run ERC and/or simulation automatically.
7. Keep an auditable history with rollback information.

## Core documents

- [`docs/vision.md`](docs/vision.md)
- [`docs/spec.md`](docs/spec.md)
- [`docs/architecture.md`](docs/architecture.md)
- [`docs/use_cases_blueprint.md`](docs/use_cases_blueprint.md)
- [`docs/migration-from-vscode-prototype.md`](docs/migration-from-vscode-prototype.md)

## Status

The deterministic circuit backend has begun. Current implementation includes:

- parser/apply wrappers ported into `backend/hephaistus_circuit/`;
- explicit patch-plan API in `backend/hephaistus_circuit/engine.py`;
- CLI entry point (`hephaistus-circuit parse` / `apply-plan`);
- S1 series-shunt round-trip regression test in `tests/test_circuit_engine.py`;
- usable KiCad 10 rectifier fixture at `fixtures/schematics/rectifier.kicad_sch`;
- example patch at `examples/patches/insert_shunt.json`.

Run tests with:

```bash
.venv/bin/python -m unittest tests.test_circuit_engine -v
```
