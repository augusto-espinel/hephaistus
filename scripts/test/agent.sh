#!/usr/bin/env bash
# HephAIstus agent test runner.
# Safe by default: uses a temp directory and skips when the local user fixture is absent.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PARSER="$ROOT/scripts/wrappers/kiutils_parser_wrapper.py"
DELTA="$ROOT/scripts/wrappers/kiutils_delta_apply.py"
FIXTURE="$ROOT/tests/user/rectifier.kicad_sch"
PY=python3

if [ -f "$ROOT/python/.venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$ROOT/python/.venv/bin/activate"
  PY=python
fi

TMP_DIR=""
cleanup() {
  if [ -n "$TMP_DIR" ] && [ -z "${KEEP_ARTIFACTS:-}" ]; then
    rm -rf "$TMP_DIR"
  elif [ -n "$TMP_DIR" ]; then
    echo "Artifacts kept: $TMP_DIR"
  fi
}
trap cleanup EXIT

make_tmp() {
  if [ -z "$TMP_DIR" ]; then
    TMP_DIR="$(mktemp -d /tmp/hephaistus-agent.XXXXXX)"
  fi
}

require_fixture() {
  if [ ! -f "$FIXTURE" ]; then
    echo "SKIP: local fixture not found: $FIXTURE"
    if [ "${HEPHAISTUS_REQUIRE_FIXTURE:-0}" = "1" ]; then
      exit 1
    fi
    exit 0
  fi
}

parse_to() {
  local sch="$1"
  local out="$2"
  "$PY" "$PARSER" "$sch" > "$out"
}

cmd_build() {
  cd "$ROOT"
  npm run build
}

cmd_parse() {
  require_fixture
  make_tmp
  local out="$TMP_DIR/parse.json"
  parse_to "$FIXTURE" "$out"
  "$PY" - "$out" <<'PY'
import json, sys
path = sys.argv[1]
with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)
components = data.get('components', [])
nets = data.get('nets', [])
assert components, 'no components parsed'
assert nets, 'no nets parsed'
refs = {c.get('reference') for c in components}
net_names = {n.get('name') for n in nets}
print(f"PASS parse: components={len(components)} nets={len(nets)}")
if {'V1','R1','R2','C1','D1','D2','D3','D4'}.issubset(refs):
    print(f"PASS rectifier refs present: {sorted(refs)}")
    print(f"PASS rectifier nets: {sorted(net_names)}")
PY
}

cmd_roundtrip() {
  require_fixture
  make_tmp
  local sch="$TMP_DIR/roundtrip.kicad_sch"
  cp "$FIXTURE" "$sch"
  parse_to "$sch" "$TMP_DIR/original.json"

  "$PY" - "$TMP_DIR/original.json" "$TMP_DIR/modified.json" <<'PY'
import json, sys
src, dst = sys.argv[1], sys.argv[2]
with open(src, 'r', encoding='utf-8') as f:
    data = json.load(f)
refs = {c.get('reference'): c for c in data.get('components', [])}
changed = {}
if 'C1' in refs:
    refs['C1']['value'] = '470e-6'
    refs['C1'].setdefault('properties', {})['Value'] = '470e-6'
    changed['C1'] = '470e-6'
if 'R2' in refs:
    refs['R2']['value'] = '22'
    refs['R2'].setdefault('properties', {})['Value'] = '22'
    changed['R2'] = '22'
if not changed:
    print('SKIP roundtrip: neither C1 nor R2 present in fixture')
    raise SystemExit(0)
with open(dst, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2)
with open(dst + '.expected', 'w', encoding='utf-8') as f:
    json.dump(changed, f)
print('Prepared roundtrip changes:', changed)
PY

  if [ ! -f "$TMP_DIR/modified.json.expected" ]; then
    return 0
  fi

  "$PY" "$DELTA" "$TMP_DIR/original.json" "$TMP_DIR/modified.json" "$sch" > "$TMP_DIR/delta.json"
  parse_to "$sch" "$TMP_DIR/verified.json"

  "$PY" - "$TMP_DIR/verified.json" "$TMP_DIR/modified.json.expected" <<'PY'
import json, sys
verified_path, expected_path = sys.argv[1], sys.argv[2]
with open(verified_path, 'r', encoding='utf-8') as f:
    verified = json.load(f)
with open(expected_path, 'r', encoding='utf-8') as f:
    expected = json.load(f)
refs = {c.get('reference'): c for c in verified.get('components', [])}
for ref, value in expected.items():
    actual = refs.get(ref, {}).get('value')
    props_actual = refs.get(ref, {}).get('properties', {}).get('Value', actual)
    assert actual == value or props_actual == value, f'{ref}: expected {value}, got {actual or props_actual}'
print('PASS roundtrip values:', expected)
PY
}

cmd_warnings() {
  require_fixture
  make_tmp
  local sch="$TMP_DIR/warnings.kicad_sch"
  cp "$FIXTURE" "$sch"
  parse_to "$sch" "$TMP_DIR/warnings_original.json"

  "$PY" - "$TMP_DIR/warnings_original.json" "$TMP_DIR/warnings_modified.json" <<'PY'
import json, sys, uuid
src, dst = sys.argv[1], sys.argv[2]
with open(src, 'r', encoding='utf-8') as f:
    data = json.load(f)
nets = [n.get('name') for n in data.get('nets', []) if n.get('name')]
if not nets:
    print('SKIP warnings: no nets available')
    raise SystemExit(0)
labeled = 'dc_plus' if 'dc_plus' in nets else nets[0]
unlabeled = 'N$1' if 'N$1' in nets else None
existing_refs = {c.get('reference') for c in data.get('components', [])}
added = []
if 'R901' not in existing_refs:
    added.append({
        'uuid': str(uuid.uuid4()),
        'reference': 'R901',
        'libId': 'Device:R',
        'value': '100',
        'properties': {'Reference': 'R901', 'Value': '100'},
        'connections': {'1': labeled, '2': labeled}
    })
if unlabeled and 'R902' not in existing_refs:
    added.append({
        'uuid': str(uuid.uuid4()),
        'reference': 'R902',
        'libId': 'Device:R',
        'value': '1k',
        'properties': {'Reference': 'R902', 'Value': '1k'},
        'connections': {'1': labeled, '2': unlabeled}
    })
if not added:
    print('SKIP warnings: suitable test components already present or no unlabeled net')
    raise SystemExit(0)
data.setdefault('components', []).extend(added)
with open(dst, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2)
with open(dst + '.expected', 'w', encoding='utf-8') as f:
    json.dump({'series_insertion': any(c['reference'] == 'R901' for c in added),
               'missing_labels': any(c['reference'] == 'R902' for c in added)}, f)
print('Prepared warning additions:', [c['reference'] for c in added], 'labeled=', labeled, 'unlabeled=', unlabeled)
PY

  if [ ! -f "$TMP_DIR/warnings_modified.json.expected" ]; then
    return 0
  fi

  "$PY" "$DELTA" "$TMP_DIR/warnings_original.json" "$TMP_DIR/warnings_modified.json" "$sch" > "$TMP_DIR/warnings_delta.json"

  "$PY" - "$TMP_DIR/warnings_delta.json" "$TMP_DIR/warnings_modified.json.expected" <<'PY'
import json, sys
result_path, expected_path = sys.argv[1], sys.argv[2]
with open(result_path, 'r', encoding='utf-8') as f:
    result = json.load(f)
with open(expected_path, 'r', encoding='utf-8') as f:
    expected = json.load(f)
warning_types = {w.get('type') for w in result.get('warnings', [])}
if expected.get('series_insertion'):
    assert 'series_insertion' in warning_types, f'missing series_insertion warning: {warning_types}'
if expected.get('missing_labels'):
    assert 'missing_labels' in warning_types, f'missing missing_labels warning: {warning_types}'
print('PASS warnings:', sorted(warning_types))
PY
}

cmd_all() {
  cmd_build
  cmd_parse
  cmd_roundtrip
  cmd_warnings
}

usage() {
  cat <<USAGE
Usage: $0 <command>

Commands:
  build      TypeScript build
  parse      Parser smoke test (skips if local fixture missing)
  roundtrip  Value round-trip in temp dir
  warnings   Series/missing-label warning checks in temp dir
  all        build + parse + roundtrip + warnings

Env:
  HEPHAISTUS_REQUIRE_FIXTURE=1   fail instead of skip when tests/user fixture is absent
  KEEP_ARTIFACTS=1              keep temp artifacts for inspection
USAGE
}

case "${1:-all}" in
  build) cmd_build ;;
  parse) cmd_parse ;;
  roundtrip) cmd_roundtrip ;;
  warnings) cmd_warnings ;;
  all) cmd_all ;;
  -h|--help|help) usage ;;
  *) usage; exit 2 ;;
esac
