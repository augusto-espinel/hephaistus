# HephAIstus User Test Spec

*For Augusto's manual testing. Consolidated 2026-07-23.*

This is the user-facing test specification. It replaces `docs/TEST-PLAN.md` and modernizes `docs/TEST-MANUAL-ROUNDTRIP.md` around the current implementation and the advice-driven workflow.

## 0. Scope

Use these tests to validate the parts that are real today:

- KiCad 10 parsing to JSON.
- JSON → KiCad delta application for values, removals, and additions.
- Warning generation for series insertion and missing labels.
- Manual wiring/placement by the user after HephAIstus stages a component.
- Sync panel status and safety prompts.
- Backup/restore behavior.

Do **not** treat LLM optimization, SKiDL generation, or ngspice execution as required unless a test explicitly says "future".

## 1. Fixture

Primary fixture: `tests/user/rectifier.kicad_sch`

Expected baseline content:

| Reference | Value | Role |
|-----------|-------|------|
| V1 | VSIN | AC source |
| R1 | 0.001 | Bridge mid-point sense |
| R2 | 10 | Load |
| C1 | 1000e-6 | Filter cap |
| D1-D4 | 1N4007 | Bridge rectifier |
| #PWR04 | GND | Ground |

Expected nets: `vsin_plus`, `vsin_minus`, `dc_plus`, `dc_minus`, and one unnamed bridge net such as `N$1`.

The whole `tests/` tree is local-only and ignored by git. Keep your own copies, logs, and reports there.

## 2. Setup

```bash
cd /Users/aespinel/.openclaw/workspace/hephaistus
npm install
npm run build

# Python env for wrappers
ls python/.venv/bin/activate

# Optional pristine backup for manual restore
cp tests/user/rectifier.kicad_sch tests/user/rectifier.pristine.kicad_sch
```

Open the project in VS Code and launch the Extension Development Host if testing extension UI.

## 3. Reset Procedure

Use before any test that mutates the schematic:

```bash
cp tests/user/rectifier.pristine.kicad_sch tests/user/rectifier.kicad_sch
rm -rf tests/user/.hephaistus
```

If you did not create a pristine copy, use your known-good local backup instead.

## 4. Core User Tests

### UT-01 — Parse KiCad → JSON

**Steps**
1. Open `tests/user/rectifier.kicad_sch`.
2. In the HephAIstus Sync panel, click **Parse KiCad → JSON**.

**Expected**
- JSON state is created under `tests/user/.hephaistus/`.
- Components and nets are extracted.
- Sync panel moves toward `🟢 In sync`.

**Check**
```bash
python scripts/wrappers/kiutils_parser_wrapper.py tests/user/rectifier.kicad_sch | \
  python3 -c 'import sys,json; d=json.load(sys.stdin); print(len(d.get("components", [])), len(d.get("nets", [])))'
```

Expected for the clean rectifier: `9 5`.

**Test Result:** passed

---

### UT-02 — Apply value changes JSON → KiCad

**Steps**
1. Parse first.
2. Edit the generated JSON: set `C1=470e-6`, `R2=22`.
3. Click **Apply JSON → KiCad**.
4. Open the schematic in KiCad.

**Expected**
- C1 and R2 values changed.
- Geometry and wiring unchanged.
- Backup created.

**Pass condition**: KiCad visually shows the new values and no moved wires.


**Test Result:** passed

---

### UT-03 — KiCad edit → parse

**Steps**
1. In KiCad, change `C1=2200e-6`, `R2=47`.
2. Save.
3. In VS Code, parse KiCad → JSON.

**Expected**
- JSON reflects the new values.
- Sync panel clears the KiCad-newer state.

**Test Result:** passed

---

### UT-04 — Component removal

**Steps**
1. Parse.
2. Remove `R1` from the JSON components array.
3. Apply JSON → KiCad.
4. Open in KiCad.

**Expected**
- R1 is gone.
- Remaining bridge components are intact.
- No crash or invalid schematic.

**Test Result:** passed

---

### UT-05 — Add parallel component without warnings

**Intent**: Add a capacitor across existing labeled nets.

**JSON change**: add `C2` with connections `1=dc_plus`, `2=dc_minus`.

**Expected**
- `C2` appears at staging.
- Net labels are created for `dc_plus` and `dc_minus`.
- No series-insertion warning.
- User can move C2 and wire/label it normally.

**Test Result:** passed

---

### UT-06 — Add series component with warning

**Intent**: Verify the system recognizes it cannot insert a series part cleanly by itself.

**JSON change**: add `R3` with both pins connected to `dc_plus`.

> **Caution (added 2026-08-01):** When hand-adding a component you MUST assign
> fresh, unique `uuid` values for the component AND each pin. Reusing an
> existing component's uuids corrupts that component's value and silently
> drops the addition. The apply script now refuses to run on duplicate
> uuids/references (exit 3). Generate uuids with `uuidgen` or
> `python3 -c "import uuid; print(uuid.uuid4())"`.

**Expected**
- R3 is staged.
- Warning type `series_insertion` is produced.
- Schematic annotation tells you to break the `dc_plus` wire and connect labels.
- Sync/chat state keeps this as pending manual work.

**Manual completion**
1. Break the relevant `dc_plus` wire in KiCad.
2. Connect R3 in series using labels/wires.
3. Save.
4. Parse again.

**Pass condition**: after parse, the JSON shows R3 pins on the expected nets or clearly reports what is still missing.

**Intial Test Result:** failed. I added R2 into the JSON file as requested, clicked the Apply JSON to KiKad button, got a message asking to confirm addition of component and connection and no errors were reported on the console. However I could not find R3 on the Kicad file nor any warnings or instructions on how to wire the component. The side bar shows the files to be in sync, but in reality the JSON is as I left it with the staged R3, while there is no R3 on the kicad file.

**Root cause (identified 2026-08-01):** The hand-added R3 reused R2's component
uuid. `compute_delta()` keys components by uuid, so R3 overwrote R2 in the
lookup; the differ emitted a value change (47 → 0.001) that was applied to
**R2's** symbol, and R3 was never added (no symbol, no labels, no series
warning). Fix applied: integrity validation in `kiutils_delta_apply.py`
(exit 3 on duplicate uuids/references). Retest with fresh uuids.
**Remember to restore R2's value:** `cp tests/user/rectifier.kicad_sch.bak tests/user/rectifier.kicad_sch` or from the pristine copy.

**Retest (2026-08-01):** passed with fresh uuids. Follow-up the same day found
two more bugs in the addition path: (1) `apply_component_addition_text()` read
pin nets from a `connections` dict the JSON state never produces — staged
components got **no labels, no series warning, no annotation**; fixed by
deriving `connections` from `pins[]`. (2) staged value came from stale
`properties.Value` instead of top-level `value`; precedence fixed. Both
verified end-to-end: R3 staged with `dc_plus` labels on both pins,
series-insertion warning + ⚠ annotation, correct value.

**Corruption bug (found & fixed 2026-08-01, 23:05):** re-running UT-06 produced
a schematic KiCad refused to load ("Unterminated delimited string", line 2466).
Cause: `apply_component_addition_text()` advanced its insertion offset by
`len(label) + 2` instead of the actual inserted string length (the `\n→\n\t`
indentation replace adds one tab per newline), so the annotation landed inside
the previous label block and sliced a uuid in half. Fixed for both label and
annotation insertions; verified with kiutils parse + zero truncated uuids.
Schematic restored from `.bak` and R3 re-staged with the fixed code.

**Second Test Result:** passed

---

### UT-07 — Add component requiring labels on existing nets

**Intent**: Verify missing-label advice.

**JSON change**: add `R4` connected to existing but unlabeled nets, e.g. `N$1` and another unlabeled net if present.

**Expected**
- Warning type `missing_labels` is produced.
- Annotation says which labels to add.
- After you add labels and save, the next parse clears or reduces the warning.

dc_plus

---

### UT-08 — Pending manual actions guard

**Steps**
1. Run UT-06 or UT-07 so warnings exist.
2. Before completing the KiCad work, click **Parse KiCad → JSON**.

**Expected**
- Extension warns that parsing may erase pending LLM/manual suggestions.
- You can cancel or explicitly proceed.

---

### UT-09 — Sync panel statuses

**Sequence**
- Clean state → `🟢`
- Touch/save KiCad → `🔴 KiCad newer`
- Parse → `🟢`
- Edit JSON → `🔵 JSON newer`
- Apply → `🟢`

**Pass condition**: status transitions match reality, not just timestamps.

---

### UT-10 — Invalid JSON safety

**Steps**
1. Corrupt the JSON state intentionally.
2. Click **Apply JSON → KiCad**.

**Expected**
- Clear error, no crash.
- KiCad file unchanged.

---

### UT-11 — Backup and restore

**Expected**
- Applying a change creates `.kicad_sch.bak` or configured backup.
- Restoring the backup returns KiCad to the prior values.

---

### UT-12 — Advice memory dry run

**Purpose**: rehearse the next development phase before LLM automation exists.

**Steps**
1. After UT-06, write down the manual advice as if it were an advice item:
   - id: `adv_series_R3`
   - expected evidence: `component_exists:R3`, `pin_net_equals:R3.1=<upstream>`, `pin_net_equals:R3.2=<downstream>`
2. Complete the wiring in KiCad.
3. Parse.
4. Manually mark the advice verified/failed based on the new JSON.

**Pass condition**: you can tell from JSON whether the advice was completed, partially completed, or not done.

## 5. User Test Report Template

```markdown
# HephAIstus User Test Report — YYYY-MM-DD

Build/commit:
Fixture: tests/user/rectifier.kicad_sch

| Test | Result | Notes |
|------|--------|-------|
| UT-01 Parse | | |
| UT-02 Values JSON→KiCad | | |
| UT-03 KiCad→JSON | | |
| UT-04 Removal | | |
| UT-05 Parallel add | | |
| UT-06 Series warning | | |
| UT-07 Missing labels | | |
| UT-08 Pending guard | | |
| UT-09 Sync statuses | | |
| UT-10 Invalid JSON | | |
| UT-11 Backup/restore | | |
| UT-12 Advice dry run | | |

Blockers:
1.
2.

Observations for agent:
-
```

## 6. What Matters Most

The most important user tests are UT-06, UT-07, UT-08, and UT-12. They exercise the exact boundary where HephAIstus stops being able to edit safely and must advise you instead.
