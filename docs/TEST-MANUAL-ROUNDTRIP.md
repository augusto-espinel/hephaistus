# Manual Test Specification: Round-Trip Workflow

**Test Subject**: `tests/user/rectifier.kicad_sch`
**Created**: 2026-07-20
**Status**: Ready for manual testing

---

## Prerequisites

1. VS Code with HephAIstus extension installed
2. KiCad 6/7/8/9/10 installed
3. Python virtual environment with kiutils (in `python/.venv`)
4. Test schematic: `tests/user/rectifier.kicad_sch` (9 components, 5 nets)

## Test Components

| Reference | Value | Type | Notes |
|-----------|-------|------|-------|
| V1 | VSIN | Voltage Source | AC input, 50Hz |
| R1 | 0.001Ω | Resistor | Current sense (bridge mid-point) |
| R2 | 10Ω | Resistor | Load resistor |
| C1 | 1000µF | Capacitor | Filter capacitor |
| D1-D4 | 1N4007 | Diode | Bridge rectifier |
| #PWR04 | GND | Power | Ground reference |

## Nets

| Name | Connected Pins |
|------|----------------|
| vsin_plus | V1.2, R1.1 |
| vsin_minus | V1.1, D3.1, D4.2 |
| dc_plus | C1.2, R2.2, D2.1, D4.1 |
| dc_minus | C1.1, R2.1, D1.2, #PWR04.1, D3.2 |
| N$1 | R1.2, D1.1, D2.2 | (unnamed net - bridge mid-point) |

---

## Test Suite

### TEST-01: Initial Parse (KiCad → JSON)

**Purpose**: Verify the extension correctly parses the schematic.

**Steps**:
1. Open VS Code in the hephaistus workspace
2. Open the HephAIstus Sync panel (Explorer sidebar)
3. Verify status shows: `⚪ Status unknown` or `🔴 KiCad newer`
4. Click **"Parse KiCad → JSON"**
5. Wait for completion message

**Expected Results**:
- [ ] Status bar shows "HephAIstus: KiCad parsed successfully"
- [ ] Sync panel shows `🟢 In sync`
- [ ] File `.hephaistus/rectifier.json` created
- [ ] JSON contains all 9 components
- [ ] JSON contains all 5 nets (including N$1)

**Manual Verification**:
```bash
# Check JSON was created
cat .hephaistus/rectifier.json | head -50

# Verify component count
cat .hephaistus/rectifier.json | grep '"reference"' | wc -l
# Expected: 9

# Verify nets
cat .hephaistus/rectifier.json | grep '"name"' | head -10
# Expected: vsin_plus, vsin_minus, dc_plus, dc_minus, N$1
```

---

### TEST-02: Value Change (JSON → KiCad)

**Purpose**: Verify component value changes apply correctly.

**Test Changes**:
| Component | Old Value | New Value |
|-----------|-----------|-----------|
| C1 | 1000e-6 | 470e-6 |
| R2 | 10 | 22 |

**Steps**:
1. Make a backup: `cp tests/user/rectifier.kicad_sch tests/user/rectifier_backup.kicad_sch`
2. Create a copy of the JSON: `cp .hephaistus/rectifier.json .hephaistus/rectifier.original.json`
3. Edit `.hephaistus/rectifier.json`:
   ```json
   // Find C1 and change value
   "value": "470e-6"  // was "1000e-6"
   
   // Find R2 and change value
   "value": "22"  // was "10"
   ```
4. Save the JSON file
5. Check sync panel shows: `🔵 JSON newer - Apply needed`
6. Click **"Apply JSON → KiCad"**
7. Wait for completion message

**Expected Results**:
- [ ] Status bar shows "Applied 2 change(s) to rectifier.kicad_sch"
- [ ] Sync panel shows `🟢 In sync`
- [ ] Backup created: `rectifier.kicad_sch.bak`

**Manual Verification in KiCad**:
1. Open `tests/user/rectifier.kicad_sch` in KiCad
2. Check C1 value shows `470e-6` (was 1000µF)
3. Check R2 value shows `22` (was 10)
4. Verify wire geometry is unchanged
5. Close KiCad without saving

**Restore for Next Test**:
```bash
cp tests/user/rectifier_backup.kicad_sch tests/user/rectifier.kicad_sch
```

---

### TEST-03: Component Removal (JSON → KiCad)

**Purpose**: Verify component removal with wire cleanup.

**Test Change**: Remove R1 (current sense resistor)

**Steps**:
1. Edit `.hephaistus/rectifier.json`
2. Remove the entire R1 component object from the `components` array:
   ```json
   // DELETE this entire block:
   {
     "uuid": "95d8c44b-ea88-4212-ab59-05f873dc0d13",
     "reference": "R1",
     "libId": "Device:R",
     "value": "0.001",
     ...
   }
   ```
3. Save the JSON file
4. Click **"Apply JSON → KiCad"**

**Expected Results**:
- [ ] Status shows "Applied 1 change(s)"
- [ ] Delta shows: `removed_components: [{ reference: "R1" }]`

**Manual Verification in KiCad**:
1. Open `rectifier.kicad_sch` in KiCad
2. Verify R1 is removed from schematic
3. Check that orphan wires connected to R1 are removed
4. Verify D1, D2, and other components remain intact

**Restore for Next Test**:
```bash
cp tests/user/rectifier_backup.kicad_sch tests/user/rectifier.kicad_sch
```

---

### TEST-04: Component Value via KiCad Edit (KiCad → JSON)

**Purpose**: Verify KiCad edits are detected and parsed.

**Steps**:
1. Open `tests/user/rectifier.kicad_sch` in KiCad
2. Edit C1: Change value from `1000e-6` to `2200e-6`
3. Edit R2: Change value from `10` to `47`
4. Save the schematic in KiCad
5. Return to VS Code
6. Check sync panel shows: `🔴 KiCad newer - Parse needed`
7. Click **"Parse KiCad → JSON"**

**Expected Results**:
- [ ] Sync panel shows `🟢 In sync`
- [ ] JSON updated with new values

**Manual Verification**:
```bash
# Check JSON values
cat .hephaistus/rectifier.json | grep -A5 '"C1"' | grep value
# Expected: "value": "2200e-6"

cat .hephaistus/rectifier.json | grep -A5 '"R2"' | grep value
# Expected: "value": "47"
```

**Restore for Next Test**:
```bash
cp tests/user/rectifier_backup.kicad_sch tests/user/rectifier.kicad_sch
```

---

### TEST-05: Multiple Value Changes (JSON → KiCad)

**Purpose**: Test bulk value changes.

**Test Changes**:
| Component | Old Value | New Value |
|-----------|-----------|-----------|
| C1 | 1000e-6 | 2200e-6 |
| R2 | 10 | 100 |
| D1 | 1N4007 | 1N4148 |
| D2 | 1N4007 | 1N4148 |
| D3 | 1N4007 | 1N4148 |
| D4 | 1N4007 | 1N4148 |

**Steps**:
1. Edit `.hephaistus/rectifier.json`
2. Apply all changes above
3. Save JSON
4. Click **"Apply JSON → KiCad"**

**Expected Results**:
- [ ] Status shows "Applied 6 change(s)"
- [ ] All values updated in KiCad

**Manual Verification in KiCad**:
1. Open schematic in KiCad
2. Check all 6 components have new values
3. Verify wire geometry is preserved

**Restore for Next Test**:
```bash
cp tests/user/rectifier_backup.kicad_sch tests/user/rectifier.kicad_sch
```

---

### TEST-06: Round-Trip Integrity

**Purpose**: Verify data integrity after multiple round-trips.

**Steps**:
1. Record original values:
   ```bash
   python scripts/wrappers/kiutils_parser_wrapper.py tests/user/rectifier.kicad_sch > /tmp/original.json
   ```
2. Parse KiCad → JSON
3. Apply JSON → KiCad (with test changes from TEST-02)
4. Parse KiCad → JSON again
5. Compare JSONs

**Expected Results**:
- [ ] Second parse produces consistent JSON
- [ ] Values match the changes made
- [ ] No unexpected component additions/removals
- [ ] Net names preserved

**Comparison Script**:
```bash
# Compare component references
diff <(cat /tmp/original.json | jq '.components[].reference') \
     <(cat .hephaistus/rectifier.json | jq '.components[].reference')
# Expected: No output (same references)

# Compare net names
diff <(cat /tmp/original.json | jq '.nets[].name') \
     <(cat .hephaistus/rectifier.json | jq '.nets[].name')
# Expected: No output (same nets)
```

---

### TEST-07: Sync Panel Status Indicators

**Purpose**: Verify sync panel correctly shows status.

**Steps**:
1. Start with clean state (both KiCad and JSON in sync)
2. Verify panel shows: `🟢 In sync`
3. Touch KiCad file: `touch tests/user/rectifier.kicad_sch`
4. Verify panel shows: `🔴 KiCad newer - Parse needed`
5. Click Parse button
6. Verify panel shows: `🟢 In sync`
7. Touch JSON file: `touch .hephaistus/rectifier.json`
8. Verify panel shows: `🔵 JSON newer - Apply needed`
9. Click Apply button
10. Verify panel shows: `🟢 In sync`

**Expected Results**:
- [ ] Status indicator changes correctly after each action
- [ ] File modification times displayed correctly
- [ ] Buttons enabled/disabled appropriately

---

### TEST-08: Error Handling - Invalid JSON

**Purpose**: Verify graceful handling of malformed JSON.

**Steps**:
1. Create malformed JSON:
   ```bash
   echo '{"invalid": true' > .hephaistus/rectifier.json
   ```
2. Try to apply: Click **"Apply JSON → KiCad"**

**Expected Results**:
- [ ] Error message displayed (not crash)
- [ ] KiCad file remains unchanged
- [ ] Sync panel still functional

**Restore**:
```bash
cp tests/user/rectifier_backup.kicad_sch tests/user/rectifier.kicad_sch
# Re-parse to restore JSON
```

---

### TEST-09: Error Handling - Missing KiCad File

**Purpose**: Verify handling when KiCad file is missing.

**Steps**:
1. Rename KiCad file:
   ```bash
   mv tests/user/rectifier.kicad_sch tests/user/rectifier_temp.kicad_sch
   ```
2. Try to apply: Click **"Apply JSON → KiCad"**

**Expected Results**:
- [ ] Error message: "No corresponding KiCad file found"
- [ ] No crash
- [ ] Sync panel shows appropriate status

**Restore**:
```bash
mv tests/user/rectifier_temp.kicad_sch tests/user/rectifier.kicad_sch
```

---

### TEST-10: Backup Creation

**Purpose**: Verify backups are created correctly.

**Steps**:
1. Ensure clean state
2. Apply a value change
3. Check for backup file

**Expected Results**:
- [ ] `rectifier.kicad_sch.bak` created
- [ ] Backup contains original values
- [ ] Main file contains changed values

**Verification**:
```bash
# Check backup exists
ls -la tests/user/rectifier.kicad_sch.bak

# Compare values
diff <(grep "1000e-6" tests/user/rectifier.kicad_sch.bak) \
     <(grep "1000e-6" tests/user/rectifier.kicadch)
# Backup should have original value
```

---

## Test Summary Template

| Test ID | Status | Notes |
|---------|--------|-------|
| TEST-01 | ⬜ | Initial Parse |
| TEST-02 | ⬜ | Value Change (JSON→ KiCad) |
| TEST-03 | ⬜ | Component Removal |
| TEST-04 | ⬜ | KiCad Edit (KiCad → JSON) |
| TEST-05 | ⬜ | Multiple Value Changes |
| TEST-06 | ⬜ | Round-Trip Integrity |
| TEST-07 | ⬜ | Sync Panel Status |
| TEST-08 | ⬜ | Error: Invalid JSON |
| TEST-09 | ⬜ | Error: Missing File |
| TEST-10 | ⬜ | Backup Creation |

---

## Quick Reference Commands

```bash
# Parse KiCad to JSON
python scripts/wrappers/kiutils_parser_wrapper.py tests/user/rectifier.kicad_sch

# Apply JSON changes to KiCad
python scripts/wrappers/kiutils_delta_apply.py \
    .hephaistus/rectifier.original.json \
    .hephaistus/rectifier.json \
    tests/user/rectifier.kicad_sch

# Restore backup
cp tests/user/rectifier_backup.kicad_sch tests/user/rectifier.kicad_sch

# Check JSON structure
cat .hephaistus/rectifier.json | jq '.components[] | {ref: .reference, val: .value}'

# Check nets
cat .hephaistus/rectifier.json | jq '.nets[] | {name: .name, pins: .connectedPins}'
```

---

## Notes for Manual Testing

1. **Always backup before testing**: Keep a pristine copy of `rectifier.kicad_sch`
2. **Check KiCad visually**: Open the schematic after each change to verify
3. **Preserve geometry**: Ensure wire paths are not modified by value changes
4. **Test incrementally**: Run tests in order; don't skip tests
5. **Report issues**: Note any unexpected behavior or errors