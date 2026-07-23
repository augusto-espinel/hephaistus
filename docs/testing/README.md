# HephAIstus Test Environment

*Consolidated 2026-07-23.*

This directory is the tracked entry point for testing. The actual test workspace is **local-only**:

- `tests/` is ignored by git and may contain user schematics, generated JSON, backups, logs, KiCad history, and throwaway scripts.
- `tests/user/` is Augusto's manual test area, centered on `tests/user/rectifier.kicad_sch`.
- Tracked test specifications live in `docs/testing/` so the repo documents *how* to test without versioning private/local test state.

## Test Specs

| Audience | Spec | Purpose |
|----------|------|---------|
| User | [`USER-TESTS.md`](./USER-TESTS.md) | Manual KiCad/VS Code validation, especially round-trip and manual wiring workflows |
| Agent | [`AGENT-TESTS.md`](./AGENT-TESTS.md) | Scriptable checks an agent or user can trigger after code changes |

## Current Status Baseline

As of 2026-07-23, the important implemented surface is:

- KiCad 10 → JSON parsing works.
- JSON → KiCad delta apply works for value changes, removals, and additions.
- Component additions use net labels and staging placement.
- Series insertion and missing-label situations generate warnings and require user wiring.
- Sync panel detects KiCad/JSON drift.
- LLM integration and simulation are not yet the source of truth for tests; test them as planned/future unless explicitly wired.

## Obsolete / Superseded Docs

- `docs/TEST-PLAN.md` — superseded. It mixed implemented and planned behavior. Use `USER-TESTS.md` and `AGENT-TESTS.md` instead.
- `docs/TEST-MANUAL-ROUNDTRIP.md` — useful historical manual procedure, but superseded by `USER-TESTS.md`.
- `docs/python/testing.md` — old Python/JSON-proxy notes; likely obsolete for the current KiCad 10 text-delta workflow.
- `tests/python/ingest_align.py` and `tests/python/min_run_delta.py` — reference missing `tests/python/fixtures/` and an older JSON-proxy model; treat as obsolete unless revived intentionally.
- `tests/test_roundtrip_manual.sh` — hard-coded absolute paths and root `.hephaistus/` assumptions; use `scripts/test/agent.sh` instead.

## Quick Commands

From the repo root:

```bash
# Agent smoke + round-trip checks
npm run test:agent

# Or directly
bash scripts/test/agent.sh all

# User manual tests
open docs/testing/USER-TESTS.md
```

## Rules

1. Do not commit files under `tests/`; they are local test state.
2. Do commit test specs and runnable agent scripts under `docs/testing/` and `scripts/test/`.
3. Agent scripts must be safe: use temp directories, never mutate the user's schematic unless explicitly instructed.
4. If a test needs the local rectifier fixture, it must skip clearly when the fixture is absent.
5. A test is only "current" if it matches the implemented architecture in `docs/architecture.md` and the collaboration model in `docs/use_cases_blueprint.md`.
