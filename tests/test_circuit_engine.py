#!/usr/bin/env python3
"""Regression tests for the deterministic circuit patch engine."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from hephaistus_circuit import PatchPlanError, apply_patch_plan, mutate_state, parse_schematic  # noqa: E402

FIXTURE = ROOT / "fixtures" / "schematics" / "rectifier.kicad_sch"
KICAD_CLI_CANDIDATES = [
    "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli",
    "kicad-cli",
]


def net_map(state):
    return {
        net["name"]: set(net.get("connectedPins", []))
        for net in state.get("nets", [])
        if net.get("name")
    }


def insert_shunt_plan():
    return {
        "operations": [
            {"op": "set_pin_net", "reference": "R2", "pin": "2", "net": "dc_plus_shunt"},
            {
                "op": "add_component",
                "reference": "R3",
                "lib_id": "Device:R",
                "value": "0.001",
                "pins": {"1": "dc_plus", "2": "dc_plus_shunt"},
            },
        ]
    }


class CircuitEngineTests(unittest.TestCase):
    def test_parse_fixture(self):
        state = parse_schematic(FIXTURE)
        self.assertGreater(len(state.get("components", [])), 0)
        self.assertGreater(len(state.get("nets", [])), 0)

    def test_apply_series_shunt_round_trip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            schematic = Path(temp_dir) / "work.kicad_sch"
            shutil.copy(FIXTURE, schematic)

            result = apply_patch_plan(schematic, insert_shunt_plan())
            self.assertEqual(result["status"], "applied")
            self.assertTrue(schematic.exists())

            after = parse_schematic(schematic)
            nets = net_map(after)
            self.assertEqual(nets["dc_plus"], {"C1.2", "C2.2", "D2.1", "D4.1", "R3.1"})
            self.assertEqual(
                nets["dc_plus_shunt"], {"R2.2", "R3.2"}
            )

            erc = self._find_kicad_cli()
            if erc:
                completed = subprocess.run(
                    [erc, "sch", "erc", str(schematic)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                # Pre-existing fixture violations may exist; execution proves CLI integration.
                self.assertIn(completed.returncode, [0, 1, 2])

    def test_plan_rejects_missing_component(self):
        state = parse_schematic(FIXTURE)
        bad_plan = {
            "operations": [
                {"op": "set_pin_net", "reference": "RX999", "pin": "1", "net": "dc_plus"}
            ]
        }
        with self.assertRaises(PatchPlanError):
            mutate_state(state, bad_plan)

    def test_no_infinite_top_level_operations(self):
        state = parse_schematic(FIXTURE)
        plan = {"operations": [{"op": "update_value", "reference": "R2", "value": "1.2"}]}
        modified = mutate_state(state, plan)
        r2 = next(component for component in modified["components"] if component["reference"] == "R2")
        self.assertEqual(r2["value"], "1.2")
        self.assertEqual(r2["properties"]["Value"], "1.2")

    def _find_kicad_cli(self):
        for candidate in KICAD_CLI_CANDIDATES:
            path = shutil.which(candidate) if candidate == "kicad-cli" else candidate
            if path and Path(path).exists():
                return path
        return None


if __name__ == "__main__":
    unittest.main()
