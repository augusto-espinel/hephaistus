# KiUtils integration plan (Phase 1) - Work In Progress

- Objective: Wire a Node-based KiUtils adapter into the ingestion flow with a per-workspace toggle (KICAD_PARSER_BACKEND).
- Components:
  - Node adapter surface: src/services/kicadKiutilsAdapter.ts
  - Parser surface delegation: src/services/kicadParserService.ts (route to KiUtils adapter when enabled)
  - Python bridge: tools/kiutils_parser_wrapper.py (wrapper script triggers kiutils)
  - Virtualenv: .venv per workspace for Python dependencies
- Decision points:
  - Backend toggle values: "kiutils-node" or "mock" (default)
  - Phase 1 rollout: external binary wrapper with Python venv
- Acceptance criteria:
  - Ingestion uses KiUtils path when enabled and parser yields JSON; otherwise falls back to mock path
  - Config toggling via KICAD_PARSER_BACKEND env variable
- Risks:
  - Python dependency instability; mitigate with bootstrap and clear error handling

