# HephAIstus Agent Test Spec

*For agent-run or user-triggered automated checks. Consolidated 2026-07-23. Updated 2026-08-04 for the stub-based apply flow.*

These tests are designed to be runnable by an agent after code changes, or by Augusto from a terminal. They must be safe by default: use temp directories, skip missing local fixtures, and never mutate `tests/user/` unless explicitly requested.

## 0. Principles

1. **Repo-tracked specs, local test state.** `tests/` is ignored; scripts must cope with missing fixtures.
2. **No false precision.** Only assert behavior that is implemented now.
3. **Temp-first.** Any KiCad mutation happens in `/tmp`, not in the user's fixture.
4. **Clear skip.** If `tests/user/rectifier.kicad_sch` is absent, print `SKIP` and exit 0 unless `HEPHAISTUS_REQUIRE_FIXTURE=1`.
5. **Advice-aware future.** Once the advice ledger exists, agent tests must verify advice status transitions, not just file diffs.

## 1. Command Entry Points

From repo root:

```bash
npm run test:agent
# or
bash scripts/test/agent.sh all
```

Subcommands:

```bash
bash scripts/test/agent.sh parse       # parser smoke test
bash scripts/test/agent.sh roundtrip   # value round-trip in temp dir
bash scripts/test/agent.sh build       # TypeScript build
bash scripts/test/agent.sh all         # build + parse + roundtrip

# Stub-based apply E2E (replaces the old warnings subcommand):
.venv/bin/python3 tests/agent/stub_apply_e2e.py
```

Environment:

```bash
HEPHAISTUS_REQUIRE_FIXTURE=1 bash scripts/test/agent.sh all   # fail if fixture missing
KEEP_ARTIFACTS=1 bash scripts/test/agent.sh all               # keep temp dir for inspection
```

## 2. Current Agent Tests

### AT-01 — TypeScript build

**Command**
```bash
npm run build
```

**Expected**
- Exit code 0.
- No TypeScript errors.

**Notes**
- This is currently the only fully repo-self-contained test.

---

### AT-02 — Parser smoke test

**Command**
```bash
bash scripts/test/agent.sh parse
```

**Expected**
- Uses `scripts/wrappers/kiutils_parser_wrapper.py`.
- Parses `tests/user/rectifier.kicad_sch` if present.
- Emits JSON with non-empty `components` and `nets`.
- For the standard rectifier fixture, component/net count should be `9/5`.

**Skip condition**
- Fixture missing → `SKIP: tests/user/rectifier.kicad_sch not found`.

---

### AT-03 — Value round-trip in temp directory

**Command**
```bash
bash scripts/test/agent.sh roundtrip
```

**Expected**
- Copies fixture to a temp directory.
- Parses original JSON.
- Changes `C1` and `R2` when present; otherwise skips the value-specific part.
- Applies JSON delta to the temp KiCad file.
- Re-parses and verifies changed values.
- Does not touch `tests/user/rectifier.kicad_sch`.

**Pass condition**
- Re-parsed values match the modified JSON.

---

### AT-04 — Stub-based apply E2E

**Command**
```bash
.venv/bin/python3 tests/agent/stub_apply_e2e.py
```

**Expected** (26 checks across 6 scenarios, all in temp directories)

| Scenario | What it proves |
|----------|----------------|
| S0 no-op | Unchanged JSON applies cleanly, nets untouched |
| S1 series insertion | R3 (1mΩ shunt) between C1 and R2: `dc_plus` island cleared, pins split across `dc_plus` / `dc_plus_shunt` by re-parse |
| S2 chained insertion | A second split applied *on the result of S1* produces the correct three-way net structure |
| S3 parallel add | C3 across `dc_plus`/`dc_minus`: nets gain C3's pins, exactly 2 stub wires added, no existing geometry touched |
| S4 RL series + lib embed | `Device:L` auto-embedded from installed KiCad libraries; RL chain `dc_plus → filt_mid → filt_out` correct |
| S5 integrity regression | Duplicate-UUID JSON still aborts with exit code 3 |

**External validation**
- `kicad-cli sch erc` on a stub-applied schematic reports zero new violations vs. the untouched fixture (the fixture itself has 2 pre-existing issues).

**History**
- Replaced the old `series_insertion` / `missing_labels` warning checks on 2026-08-04 — those warning types were removed when the stub architecture made them unnecessary.

---

### AT-05 — Docs consistency check

**Command**
```bash
grep -R "use_cases_blueprint" docs/vision.md docs/testing/README.md
grep -R "TEST-PLAN" docs/testing/README.md docs/TEST-PLAN.md
```

**Expected**
- `vision.md` references `use_cases_blueprint.md`.
- Testing README marks `TEST-PLAN.md` superseded.

---

## 3. Future Agent Tests

Add these when the corresponding features exist:

| ID | Feature | Required assertions |
|----|---------|---------------------|
| AT-10 | Structured LLM output | Reject executable edits in prose; accept schema-valid `patch`, `advice`, `verification` blocks |
| AT-11 | Advice ledger | Advice persists across parse cycles with statuses `pending_user → awaiting_parse → verified/failed` |
| AT-12 | Verification engine | Parser-backed checks produce exact missing evidence for failed advice |
| AT-13 | Simulation gating | Simulation refuses/degrades when required manual actions are pending |
| AT-14 | Checkpointing | Savepoint includes schematic, JSON, advice ledger, and simulation plan |
| AT-15 | Rollback | Abort restores savepoint and marks proposal rejected |

## 4. Obsolete Agent Assets

Do not use these unless intentionally revived:

- `tests/python/ingest_align.py` — expects missing `tests/python/fixtures/`, old JSON-proxy model.
- `tests/python/min_run_delta.py` — same fixture problem and old ledger model.
- `tests/test_roundtrip_manual.sh` — hard-coded absolute path and root `.hephaistus/` assumption.
- `docs/python/testing.md` — older Python sync testing notes, not aligned with current KiCad 10 text-delta wrappers.
- `docs/TEST-PLAN.md` — broad manual checklist, superseded by user/agent specs.

## 5. Agent Result Template

```markdown
# HephAIstus Agent Test Result — YYYY-MM-DD

Commit:
Command: npm run test:agent

| Test | Result | Evidence |
|------|--------|----------|
| AT-01 Build | | npm run build |
| AT-02 Parse | | components/nets count |
| AT-03 Roundtrip | | C1/R2 verified values |
| AT-04 Stub apply E2E | | 26 checks, scenarios S0–S5 |
| AT-05 Docs consistency | | grep hits |

Artifacts:
- temp dir:

Failures:
1.

Recommended next action:
-
```
