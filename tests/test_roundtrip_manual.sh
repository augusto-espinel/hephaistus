#!/bin/bash
# Quick Test Runner for HephAIstus Round-Trip Workflow
# Usage: ./tests/test_roundtrip.sh [test-id]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PARSER="$PROJECT_ROOT/scripts/wrappers/kiutils_parser_wrapper.py"
DELTA="$PROJECT_ROOT/scripts/wrappers/kiutils_delta_apply.py"
TEST_SCH="$PROJECT_ROOT/tests/user/rectifier.kicad_sch"
BACKUP="$PROJECT_ROOT/tests/user/rectifier_backup.kicad_sch"
JSON_DIR="$PROJECT_ROOT/.hephaistus"

# Activate venv
source "$PROJECT_ROOT/python/.venv/bin/activate"

run_test() {
    case "$1" in
        parse)
            echo "=== TEST: Parse KiCad → JSON ==="
            python "$PARSER" "$TEST_SCH" > "$JSON_DIR/rectifier.json"
            echo "Output: $JSON_DIR/rectifier.json"
            cat "$JSON_DIR/rectifier.json" | python -c "
import sys, json
data = json.load(sys.stdin)
print(f\"Components: {len(data.get('components', []))}\")
print(f\"Nets: {len(data.get('nets', []))}\")
for c in data.get('components', [])[:5]:
    print(f\"  {c['reference']}: {c['value']}\")
"
            ;;
            
        apply-value)
            echo "=== TEST: Apply Value Changes (C1=470e-6, R2=22) ==="
            # Create original copy
            cp "$JSON_DIR/rectifier.json" "$JSON_DIR/rectifier.original.json"
            
            # Modify values
            python3 << 'EOF'
import json
with open('/Users/aespinel/.openclaw/workspace/hephaistus/.hephaistus/rectifier.json') as f:
    data = json.load(f)
for c in data['components']:
    if c['reference'] == 'C1':
        c['value'] = '470e-6'
    if c['reference'] == 'R2':
        c['value'] = '22'
with open('/Users/aespinel/.openclaw/workspace/hephaistus/.hephaistus/rectifier.json', 'w') as f:
    json.dump(data, f, indent=2)
print('Modified: C1 = 470e-6, R2 = 22')
EOF
            
            # Apply delta
            python "$DELTA" "$JSON_DIR/rectifier.original.json" "$JSON_DIR/rectifier.json" "$TEST_SCH"
            ;;
            
        restore)
            echo "=== Restore from Backup ==="
            cp "$BACKUP" "$TEST_SCH"
            echo "Restored: $TEST_SCH"
            ;;
            
        verify)
            echo "=== Verify Current State ==="
            python "$PARSER" "$TEST_SCH" 2>&1 | python -c "
import sys, json
data = json.load(sys.stdin)
print('Components:')
for c in data.get('components', []):
    print(f\"  {c['reference']}: {c['value']}\")
print(f\"\\nNets: {[n['name'] for n in data.get('nets', [])]}\")
"
            ;;
            
        status)
            echo "=== Check Sync Status ==="
            if [ -f "$JSON_DIR/rectifier.json" ]; then
                echo "JSON exists: $JSON_DIR/rectifier.json"
                echo "Modified: $(stat -f '%Sm' "$JSON_DIR/rectifier.json")"
            else
                echo "JSON not found - run 'parse' first"
            fi
            echo ""
            echo "KiCad modified: $(stat -f '%Sm' "$TEST_SCH")"
            ;;
            
        *)
            echo "Unknown test: $1"
            show_usage
            ;;
    esac
}

show_usage() {
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  parse        Parse KiCad → JSON"
    echo "  apply-value  Apply value changes (C1, R2)"
    echo "  restore      Restore from backup"
    echo "  verify       Verify current state"
    echo "  status       Check sync status"
    echo ""
    echo "Examples:"
    echo "  $0 parse"
    echo "  $0 apply-value"
    echo "  $0 verify"
    echo "  $0 restore"
}

# Ensure JSON directory exists
mkdir -p "$JSON_DIR"

if [ -z "$1" ]; then
    show_usage
    exit 0
fi

run_test "$1"