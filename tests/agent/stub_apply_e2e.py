#!/usr/bin/env python3
"""
End-to-end tests for the stub-based net restructuring apply flow.

Each scenario works on a fresh copy of the rectifier fixture:
  parse -> mutate JSON -> apply delta -> re-parse -> assert nets

Scenarios:
  S0  no-op sanity (modified == original)
  S1  series insertion: R3 between C1 and R2 (splits dc_plus)
  S2  chained series insertion on the S1 result (splits dc_plus again)
  S3  parallel addition: C3 across dc_plus/dc_minus (no wires removed)
  S4  RL series chain + Device:L library embedding
  S5  integrity regression: duplicate UUID must still abort (exit 3)

Run:  .venv/bin/python3 tests/agent/stub_apply_e2e.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
WRAPPER = os.path.join(ROOT, 'scripts', 'wrappers', 'kiutils_delta_apply.py')
PARSER = os.path.join(ROOT, 'scripts', 'wrappers', 'kiutils_parser_wrapper.py')
FIXTURE = os.path.join(ROOT, 'tests', 'user', 'rectifier.kicad_sch')
PY = os.path.join(ROOT, '.venv', 'bin', 'python3')
if not os.path.exists(PY):
    PY = sys.executable

PASS = 0
FAIL = 0


def report(ok, label, detail=''):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}" + (f" — {detail}" if detail else ''))


def parse(sch_path):
    r = subprocess.run([PY, PARSER, sch_path], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"parse failed: {r.stderr[-2000:]}")
    return json.loads(r.stdout)


def apply(orig_path, mod_path, sch_path):
    r = subprocess.run([PY, WRAPPER, orig_path, mod_path, sch_path],
                       capture_output=True, text=True)
    try:
        out = json.loads(r.stdout)
    except json.JSONDecodeError:
        out = {'raw_stdout': r.stdout}
    out['_stderr'] = r.stderr
    return r.returncode, out


def net_map(state):
    return {n['name']: set(n.get('connectedPins', [])) for n in state.get('nets', [])}


def set_pin_net(state, ref, pin_num, new_net):
    for c in state['components']:
        if c['reference'] == ref:
            for p in c['pins']:
                if str(p['number']) == str(pin_num):
                    p['net'] = new_net
                    return
    raise KeyError(f"{ref}.{pin_num} not found")


def add_component(state, ref, lib_id, value, pin_nets):
    state['components'].append({
        'uuid': str(uuid.uuid4()),
        'reference': ref,
        'libId': lib_id,
        'value': value,
        'properties': {'Value': value},
        'pins': [
            {'number': str(n), 'uuid': str(uuid.uuid4()), 'net': net,
             'position': {'x': 0.0, 'y': 0.0}}
            for n, net in pin_nets.items()
        ],
    })


def run_scenario(name, mutate, check, baseline_state=None):
    """Fresh fixture copy -> parse -> mutate -> apply -> re-parse -> check."""
    print(f"\n=== {name} ===")
    with tempfile.TemporaryDirectory() as td:
        sch = os.path.join(td, 'work.kicad_sch')
        shutil.copy(FIXTURE, sch)
        orig = baseline_state if baseline_state is not None else parse(sch)
        # When chaining scenarios the fixture copy is the PRE-apply file, so a
        # provided baseline must come with its own schematic. (S2 handles this
        # itself; here baseline_state is only used for simple cases.)
        mod = json.loads(json.dumps(orig))
        mutate(mod)
        orig_path = os.path.join(td, 'orig.json')
        mod_path = os.path.join(td, 'mod.json')
        json.dump(orig, open(orig_path, 'w'), indent=1)
        json.dump(mod, open(mod_path, 'w'), indent=1)
        code, out = apply(orig_path, mod_path, sch)
        report(code == 0, "apply exit 0", f"exit={code} stderr={out.get('_stderr','')[-400:]}")
        for w in out.get('warnings', []):
            print(f"  warning: {w.get('type')}: {w.get('message','')[:120]}")
        if code != 0:
            return None, None
        try:
            after = parse(sch)
        except RuntimeError as e:
            report(False, "re-parse after apply", str(e))
            return None, None
        check(after, sch)
        return after, sch


def expect_net(nets, name, pins):
    got = nets.get(name, set())
    report(got == set(pins), f"net {name}",
           f"expected {sorted(pins)} got {sorted(got)}")


# ---------------------------------------------------------------------------
# S0: no-op
# ---------------------------------------------------------------------------

def s0():
    def mutate(mod):
        pass

    def check(after, sch):
        orig_nets = net_map(parse(FIXTURE))
        after_nets = net_map(after)
        report(after_nets == orig_nets, "nets unchanged",
               f"diff: { {k: (sorted(orig_nets.get(k,set())), sorted(after_nets.get(k,set()))) for k in set(orig_nets)|set(after_nets) if orig_nets.get(k,set())!=after_nets.get(k,set())} }")

    run_scenario("S0 no-op", mutate, check)


# ---------------------------------------------------------------------------
# S1: series insertion — R3 (1 mOhm) between C1 and R2, splitting dc_plus
# ---------------------------------------------------------------------------

def s1():
    def mutate(mod):
        set_pin_net(mod, 'R2', '2', 'dc_plus_shunt')
        add_component(mod, 'R3', 'Device:R', '0.001',
                      {'1': 'dc_plus', '2': 'dc_plus_shunt'})

    def check(after, sch):
        nets = net_map(after)
        expect_net(nets, 'dc_plus', {'C1.2', 'C2.2', 'D2.1', 'D4.1', 'R3.1'})
        expect_net(nets, 'dc_plus_shunt', {'R2.2', 'R3.2'})
        expect_net(nets, 'dc_minus', {'#PWR04.1', 'C1.1', 'C2.1', 'D1.2', 'D3.2', 'R2.1'})
        expect_net(nets, 'N$1', {'D1.1', 'D2.2', 'R1.2'})
        expect_net(nets, 'vsin_plus', {'R1.1', 'V1.2'})
        expect_net(nets, 'vsin_minus', {'D3.1', 'D4.2', 'V1.1'})

    run_scenario("S1 series insertion R3", mutate, check)


# ---------------------------------------------------------------------------
# S2: chained — apply S1, then split dc_plus AGAIN with R4 between C1 and C2
# ---------------------------------------------------------------------------

def s2():
    print("\n=== S2 chained series insertion ===")
    with tempfile.TemporaryDirectory() as td:
        sch = os.path.join(td, 'work.kicad_sch')
        shutil.copy(FIXTURE, sch)

        # step 1: S1 mutation
        orig1 = parse(sch)
        mod1 = json.loads(json.dumps(orig1))
        set_pin_net(mod1, 'R2', '2', 'dc_plus_shunt')
        add_component(mod1, 'R3', 'Device:R', '0.001',
                      {'1': 'dc_plus', '2': 'dc_plus_shunt'})
        p1, m1 = os.path.join(td, 'o1.json'), os.path.join(td, 'm1.json')
        json.dump(orig1, open(p1, 'w')), json.dump(mod1, open(m1, 'w'))
        code, out = apply(p1, m1, sch)
        report(code == 0, "step1 apply exit 0", f"exit={code} {out.get('_stderr','')[-300:]}")
        if code != 0:
            return

        # step 2: split dc_plus again — C2.2 moves to dc_plus_b via R4
        orig2 = parse(sch)
        mod2 = json.loads(json.dumps(orig2))
        set_pin_net(mod2, 'C2', '2', 'dc_plus_b')
        add_component(mod2, 'R4', 'Device:R', '0.001',
                      {'1': 'dc_plus', '2': 'dc_plus_b'})
        p2, m2 = os.path.join(td, 'o2.json'), os.path.join(td, 'm2.json')
        json.dump(orig2, open(p2, 'w')), json.dump(mod2, open(m2, 'w'))
        code, out = apply(p2, m2, sch)
        report(code == 0, "step2 apply exit 0", f"exit={code} {out.get('_stderr','')[-300:]}")
        if code != 0:
            return

        after = parse(sch)
        nets = net_map(after)
        expect_net(nets, 'dc_plus', {'C1.2', 'D2.1', 'D4.1', 'R3.1', 'R4.1'})
        expect_net(nets, 'dc_plus_b', {'C2.2', 'R4.2'})
        expect_net(nets, 'dc_plus_shunt', {'R2.2', 'R3.2'})
        expect_net(nets, 'dc_minus', {'#PWR04.1', 'C1.1', 'C2.1', 'D1.2', 'D3.2', 'R2.1'})


# ---------------------------------------------------------------------------
# S3: parallel addition — C3 across dc_plus/dc_minus, no wires removed
# ---------------------------------------------------------------------------

def s3():
    wire_count_before = open(FIXTURE).read().count('(wire')

    def mutate(mod):
        add_component(mod, 'C3', 'Device:C', '100u',
                      {'1': 'dc_plus', '2': 'dc_minus'})

    def check(after, sch):
        nets = net_map(after)
        expect_net(nets, 'dc_plus', {'C1.2', 'C2.2', 'C3.1', 'D2.1', 'D4.1', 'R2.2'})
        expect_net(nets, 'dc_minus', {'#PWR04.1', 'C1.1', 'C2.1', 'C3.2', 'D1.2', 'D3.2', 'R2.1'})
        wires_after = open(sch).read().count('(wire')
        report(wires_after == wire_count_before + 2,
               "parallel add: only 2 stub wires added",
               f"before={wire_count_before} after={wires_after}")

    run_scenario("S3 parallel C3", mutate, check)


# ---------------------------------------------------------------------------
# S4: RL series chain on dc_plus + Device:L library embedding
# ---------------------------------------------------------------------------

def s4():
    def mutate(mod):
        set_pin_net(mod, 'C1', '2', 'filt_out')
        add_component(mod, 'R5', 'Device:R', '1',
                      {'1': 'dc_plus', '2': 'filt_mid'})
        add_component(mod, 'L1', 'Device:L', '10u',
                      {'1': 'filt_mid', '2': 'filt_out'})

    def check(after, sch):
        nets = net_map(after)
        expect_net(nets, 'dc_plus', {'C2.2', 'D2.1', 'D4.1', 'R2.2', 'R5.1'})
        expect_net(nets, 'filt_mid', {'L1.1', 'R5.2'})
        expect_net(nets, 'filt_out', {'C1.2', 'L1.2'})
        expect_net(nets, 'dc_minus', {'#PWR04.1', 'C1.1', 'C2.1', 'D1.2', 'D3.2', 'R2.1'})
        report('"Device:L"' in open(sch).read(), "Device:L embedded in lib_symbols")

    run_scenario("S4 RL series + lib embed", mutate, check)


# ---------------------------------------------------------------------------
# S5: integrity regression — duplicate UUID aborts with exit 3
# ---------------------------------------------------------------------------

def s5():
    print("\n=== S5 integrity regression ===")
    with tempfile.TemporaryDirectory() as td:
        sch = os.path.join(td, 'work.kicad_sch')
        shutil.copy(FIXTURE, sch)
        orig = parse(sch)
        mod = json.loads(json.dumps(orig))
        # duplicate C1's uuid onto R1
        c1_uuid = next(c['uuid'] for c in mod['components'] if c['reference'] == 'C1')
        for c in mod['components']:
            if c['reference'] == 'R1':
                c['uuid'] = c1_uuid
        p, m = os.path.join(td, 'o.json'), os.path.join(td, 'm.json')
        json.dump(orig, open(p, 'w')), json.dump(mod, open(m, 'w'))
        code, out = apply(p, m, sch)
        report(code == 3, "duplicate uuid aborts with exit 3", f"exit={code}")


if __name__ == '__main__':
    s0()
    s1()
    s2()
    s3()
    s4()
    s5()
    print(f"\n{'='*50}\nTOTAL: {PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
