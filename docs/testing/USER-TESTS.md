# HephAIstus User Test Spec

*For Augusto's manual testing. Consolidated 2026-07-23. Updated 2026-08-04 for the stub-based apply flow.*

This is the user-facing test specification. It replaces `docs/TEST-PLAN.md` and modernizes `docs/TEST-MANUAL-ROUNDTRIP.md` around the current implementation and the advice-driven workflow.

## 0. Scope

Use these tests to validate the parts that are real today:

- KiCad 10 parsing to JSON.
- JSON → KiCad delta application for values, removals, additions, and net restructuring.
- Stub-based topology changes: series insertion and net splits applied automatically (clear-and-stub).
- Automatic library-symbol embedding from installed KiCad libraries.
- Optional manual redraw/placement by the user after HephAIstus stages components.
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

---

### UT-03 — KiCad edit → parse

**Steps**
1. In KiCad, change `C1=2200e-6`, `R2=47`.
2. Save.
3. In VS Code, parse KiCad → JSON.

**Expected**
- JSON reflects the new values.
- Sync panel clears the KiCad-newer state.

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

---

### UT-05 — Add parallel component

**Intent**: Add a capacitor across existing labeled nets.

**JSON change**: add `C2` with pins on `dc_plus` and `dc_minus`.

**Expected**
- `C2` appears at staging with a `(pin …)` / `(instances …)` block.
- Each connected pin gets a stub (short wire + label) for its net.
- No warnings.
- ERC shows no new violations; the circuit is connected without any manual step.
- Optional: you can move C2 and draw wires for a cleaner look.

---

### UT-06 — Series insertion via net split

**Intent**: Insert a 1mΩ shunt between C1 and R2 — the canonical series case.

**JSON change**:
1. Reassign `R2` pin 2 from `dc_plus` to a new net, e.g. `dc_plus_shunt`.
2. Add `R3` (`Device:R`, `0.001`) with pin 1 on `dc_plus`, pin 2 on `dc_plus_shunt`.

**Expected**
- The `dc_plus` wire island is cleared; every former member pin has a labeled stub.
- Re-parse shows `dc_plus` = {C1.2, C2.2, D2.1, D4.1, R3.1} and `dc_plus_shunt` = {R2.2, R3.2}.
- **No warnings** — the change is fully applied.
- Schematic is simulatable immediately; you may redraw the `dc_plus` routing for aesthetics.

**Pass condition**: re-parsed nets match expectations and `kicad-cli sch erc` shows no new violations. (This mirrors E2E scenario S1 in `tests/agent/stub_apply_e2e.py`.)

---

### UT-07 — Rename an unlabeled net

**Intent**: Give the parser-generated net `N$1` a real name.

**JSON change**: reassign all pins of `N$1` to a new name, e.g. `bridge_mid`.

**Expected**
- The old island's geometry is cleared and each member pin gets a `bridge_mid` stub.
- Next parse shows `bridge_mid` with exactly the reassigned pins.
- No `missing_labels` warning (that type was removed 2026-08-04).

---

### UT-08 — Residual warnings guard

**Steps**
1. Apply a change that references a symbol from a library not installed on your system (e.g. a vendor part).
2. Observe the `missing_library` warning.
3. Before resolving it, click **Parse KiCad → JSON**.

**Expected**
- Nothing was half-written for that component.
- Extension warns that parsing may erase pending items.
- After importing the library in KiCad, re-apply completes without warnings.

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

**Purpose**: rehearse the advice-ledger phase (now scoped to *optional cleanup*, not connectivity).

**Steps**
1. After UT-06, write down cleanup advice as if it were an advice item:
   - id: `adv_redraw_dc_plus`
   - detail: "Redraw wires for the cleared dc_plus island and reposition R3."
   - expected evidence: `net_connected:dc_plus` without stub-only islands
2. Do the redraw in KiCad.
3. Parse.
4. Manually mark the advice verified/failed based on the new JSON.

**Pass condition**: you can tell from JSON whether the cleanup was completed, partially completed, or not done.

---

### UT-13 — Library embedding

**Intent**: Add a component whose symbol is not yet in the schematic's `lib_symbols`.

**JSON change**: RL series chain — reassign `R5` pin 2 from `dc_plus` to `filt_mid` and `C1` pin 2 from `dc_plus` to `filt_out`; add `L1` (`Device:L`) with pin 1 on `filt_mid` and pin 2 on `filt_out`.

**Expected**
- `Device:L` is auto-embedded into `lib_symbols` from your installed KiCad libraries.
- L1 staged with stubs; re-parse shows `dc_plus` = {C2.2, D2.1, D4.1, R2.2, R5.1}, `filt_mid` = {R5.2, L1.1}, `filt_out` = {C1.2, L1.2}.
- If the library is genuinely missing: single `missing_library` warning, nothing half-written, apply completes the rest. (Mirrors E2E scenario S4.)

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
| UT-06 Series insertion (stubs) | | |
| UT-07 Net rename (stubs) | | |
| UT-08 Residual warnings guard | | |
| UT-09 Sync statuses | | |
| UT-10 Invalid JSON | | |
| UT-11 Backup/restore | | |
| UT-12 Advice dry run | | |
| UT-13 Library embedding | | |

Blockers:
1.
2.

Observations for agent:
-
```

## 6. What Matters Most

The most important user tests are UT-06, UT-07, and UT-13. They exercise the new stub architecture exactly where the old system used to give up and warn: series insertion, unlabeled nets, and missing library symbols. UT-06 in the GUI is the fastest way to judge whether stubbed nets feel acceptable in practice.
