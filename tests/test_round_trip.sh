#!/bin/bash
# Round-Trip Integration Test for HephAIstus
# Tests: KiCad → JSON → Modify → JSON → KiCad

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PARSER="$PROJECT_ROOT/scripts/wrappers/kiutils_parser_wrapper.py"
DELTA="$PROJECT_ROOT/scripts/wrappers/kiutils_delta_apply.py"
TEST_SCH="$PROJECT_ROOT/tests/user/rectifier.kicad_sch"
WORK_DIR="/tmp/hephaistus_roundtrip_test"

echo "=== HephAIstus Round-Trip Test ==="
echo ""

# Setup
echo "1. Setting up test environment..."
rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"
cp "$TEST_SCH" "$WORK_DIR/original.kicad_sch"

# Activate venv
source "$PROJECT_ROOT/python/.venv/bin/activate"

# Parse to JSON
echo "2. Parsing KiCad to JSON..."
python "$PARSER" "$WORK_DIR/original.kicad_sch" > "$WORK_DIR/original.json"
echo "   Created: original.json"

# Show original state
echo ""
echo "3. Original component values:"
python3 -c "
import json
with open('$WORK_DIR/original.json') as f:
    data = json.load(f)
for c in data['components']:
    if c['reference'] in ['C1', 'R2']:
        print(f\"   {c['reference']}: {c['value']}\")
"

# Modify JSON (simulate LLM optimization)
echo ""
echo "4. Simulating LLM optimization..."
python3 << 'EOF'
import json

with open('/tmp/hephaistus_roundtrip_test/original.json') as f:
    data = json.load(f)

# Simulate optimization
for comp in data['components']:
    if comp['reference'] == 'C1':
        comp['value'] = '470e-6'  # Optimize capacitance
    if comp['reference'] == 'R2':
        comp['value'] = '22'  # Optimize resistance

with open('/tmp/hephaistus_roundtrip_test/modified.json', 'w') as f:
    json.dump(data, f, indent=2)

print("   Modified: C1 = 470e-6, R2 = 22")
EOF

# Apply delta
echo ""
echo "5. Applying delta back to KiCad..."
python "$DELTA" "$WORK_DIR/original.json" "$WORK_DIR/modified.json" "$WORK_DIR/original.kicad_sch" \
    > "$WORK_DIR/delta_result.json"

# Show result
cat "$WORK_DIR/delta_result.json" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"   Status: {data['status']}\")
print(f\"   Changes: {data['changes_applied']}\")
for change in data['delta']['value_changes']:
    print(f\"   - {change['reference']}: {change['old_value']} → {change['new_value']}\")
"

# Verify
echo ""
echo "6. Verifying changes in KiCad..."
python "$PARSER" "$WORK_DIR/original.kicad_sch" > "$WORK_DIR/verified.json"
python3 -c "
import json
with open('$WORK_DIR/verified.json') as f:
    data = json.load(f)
print('   Verified component values:')
for c in data['components']:
    if c['reference'] in ['C1', 'R2']:
        print(f\"   {c['reference']}: {c['value']}\")
"

# Cleanup
echo ""
echo "7. Test artifacts saved to: $WORK_DIR"
echo ""
echo "=== Round-Trip Test Complete ==="
