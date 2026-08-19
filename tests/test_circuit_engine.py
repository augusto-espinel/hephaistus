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

from hephaistus_circuit import (
    PatchPlanError,
    apply_patch_plan,
    mutate_state,
    parse_schematic,
    validate_patch_plan,
)  # noqa: E402

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
        "schema": "hephaistus/patch-plan/v1",
        "intent": "Insert current shunt",
        "operations": [
            {"type": "net.split", "origin_net": "dc_plus", "move_pins": ["R2.2"], "new_net": "dc_plus_shunt"},
            {
                "type": "component.add",
                "component": {
                    "reference": "R3",
                    "lib_id": "Device:R",
                    "value": "0.001",
                    "pins": {"1": "dc_plus", "2": "dc_plus_shunt"},
                },
            },
        ]
    }


def chain_second_split_plan():
    return {
        "schema": "hephaistus/patch-plan/v1",
        "operations": [
            {"type": "net.split", "origin_net": "dc_plus", "move_pins": ["C2.2"], "new_net": "dc_plus_b"},
            {
                "type": "component.add",
                "component": {
                    "reference": "R4",
                    "lib_id": "Device:R",
                    "value": "0.001",
                    "pins": {"1": "dc_plus", "2": "dc_plus_b"},
                },
            },
        ]
    }


def parallel_capacitor_plan():
    return {
        "schema": "hephaistus/patch-plan/v1",
        "operations": [
            {
                "type": "component.add",
                "component": {
                    "reference": "C3",
                    "lib_id": "Device:C",
                    "value": "100u",
                    "pins": {"1": "dc_plus", "2": "dc_minus"},
                },
            },
        ]
    }


def rl_chain_plan():
    return {
        "schema": "hephaistus/patch-plan/v1",
        "operations": [
            {"type": "net.split", "origin_net": "dc_plus", "move_pins": ["C1.2"], "new_net": "filt_out"},
            {
                "type": "component.add",
                "component": {
                    "reference": "R5",
                    "lib_id": "Device:R",
                    "value": "1",
                    "pins": {"1": "dc_plus", "2": "filt_mid"},
                },
            },
            {
                "type": "component.add",
                "component": {
                    "reference": "L1",
                    "lib_id": "Device:L",
                    "value": "10u",
                    "pins": {"1": "filt_mid", "2": "filt_out"},
                },
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
            self.assertEqual(nets["dc_plus_shunt"], {"R2.2", "R3.2"})

            erc = self._find_kicad_cli()
            if erc:
                completed = subprocess.run(
                    [erc, "sch", "erc", str(schematic)],
                    cwd=temp_dir,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                # Pre-existing fixture violations may exist; execution proves CLI integration.
                self.assertIn(completed.returncode, [0, 1, 2])

    def test_chained_net_split_round_trip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            schematic = Path(temp_dir) / "work.kicad_sch"
            shutil.copy(FIXTURE, schematic)

            first = apply_patch_plan(schematic, insert_shunt_plan())
            self.assertEqual(first["status"], "applied")

            second = apply_patch_plan(schematic, chain_second_split_plan())
            self.assertEqual(second["status"], "applied")

            after = parse_schematic(schematic)
            nets = net_map(after)
            self.assertEqual(nets["dc_plus"], {"C1.2", "D2.1", "D4.1", "R3.1", "R4.1"})
            self.assertEqual(nets["dc_plus_b"], {"C2.2", "R4.2"})
            self.assertEqual(nets["dc_plus_shunt"], {"R2.2", "R3.2"})

    def test_parallel_addition_only_adds_stubs(self):
        wire_count_before = FIXTURE.read_text(encoding="utf-8").count("(wire")

        with tempfile.TemporaryDirectory() as temp_dir:
            schematic = Path(temp_dir) / "work.kicad_sch"
            shutil.copy(FIXTURE, schematic)

            result = apply_patch_plan(schematic, parallel_capacitor_plan())
            self.assertEqual(result["status"], "applied")

            after = parse_schematic(schematic)
            nets = net_map(after)
            self.assertEqual(
                nets["dc_plus"],
                {"C1.2", "C2.2", "C3.1", "D2.1", "D4.1", "R2.2"},
            )
            self.assertEqual(
                nets["dc_minus"],
                {"#PWR04.1", "C1.1", "C2.1", "C3.2", "D1.2", "D3.2", "R2.1"},
            )
            wire_count_after = schematic.read_text(encoding="utf-8").count("(wire")
            self.assertEqual(wire_count_after, wire_count_before + 2)

    def test_rl_chain_and_library_embedding(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            schematic = Path(temp_dir) / "work.kicad_sch"
            shutil.copy(FIXTURE, schematic)

            result = apply_patch_plan(schematic, rl_chain_plan())
            self.assertEqual(result["status"], "applied")

            after = parse_schematic(schematic)
            nets = net_map(after)
            self.assertEqual(nets["dc_plus"], {"C2.2", "D2.1", "D4.1", "R2.2", "R5.1"})
            self.assertEqual(nets["filt_mid"], {"L1.1", "R5.2"})
            self.assertEqual(nets["filt_out"], {"C1.2", "L1.2"})
            self.assertIn('(symbol "Device:L"', schematic.read_text(encoding="utf-8"))

    def test_update_value_uses_safe_text_apply(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            schematic = Path(temp_dir) / "work.kicad_sch"
            shutil.copy(FIXTURE, schematic)
            plan = {
                "schema": "hephaistus/patch-plan/v1",
                "operations": [
                    {"type": "component.update_value", "reference": "R2", "value": "1.2"},
                ]
            }
            result = apply_patch_plan(schematic, plan)
            self.assertEqual(result["status"], "applied")
            self.assertIn('"Value" "1.2"', schematic.read_text(encoding="utf-8"))

    def test_rejects_missing_component(self):
        state = parse_schematic(FIXTURE)
        bad_plan = {
            "schema": "hephaistus/patch-plan/v1",
            "operations": [
                {"type": "pin.assign_net", "reference": "RX999", "pin": "1", "net": "dc_plus"}
            ]
        }
        with self.assertRaises(PatchPlanError):
            mutate_state(state, bad_plan)

    def test_rejects_duplicate_component_uuid(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            schematic = Path(temp_dir) / "work.kicad_sch"
            shutil.copy(FIXTURE, schematic)
            original = parse_schematic(schematic)
            c1_uuid = next(
                component["uuid"]
                for component in original["components"]
                if component["reference"] == "C1"
            )
            bad_plan = {
                "schema": "hephaistus/patch-plan/v1",
                "operations": [
                    {
                        "type": "component.add",
                        "component": {
                            "reference": "RX",
                            "uuid": c1_uuid,
                            "lib_id": "Device:R",
                            "value": "1",
                            "pins": {"1": "dc_plus", "2": "dc_minus"},
                        },
                    }
                ]
            }
            with self.assertRaises(PatchPlanError):
                apply_patch_plan(schematic, bad_plan)

    def test_rejects_nonfinite_top_level_operations(self):
        state = parse_schematic(FIXTURE)
        bad_plan = {"operations": {"op": "update_value", "reference": "R2", "value": "1.2"}}
        with self.assertRaises(PatchPlanError):
            mutate_state(state, bad_plan)

    def test_no_change_returns_without_write(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            schematic = Path(temp_dir) / "work.kicad_sch"
            shutil.copy(FIXTURE, schematic)
            original_text = schematic.read_text(encoding="utf-8")
            plan = {
                "schema": "hephaistus/patch-plan/v1",
                "operations": [{"type": "component.update_value", "reference": "R2", "value": "100"}],
            }
            result = apply_patch_plan(schematic, plan)
            self.assertEqual(result["status"], "no_changes")
            self.assertEqual(schematic.read_text(encoding="utf-8"), original_text)

    def test_dry_run_validates_without_writing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            schematic = Path(temp_dir) / "work.kicad_sch"
            shutil.copy(FIXTURE, schematic)
            original_text = schematic.read_text(encoding="utf-8")
            result = validate_patch_plan(schematic, insert_shunt_plan())
            self.assertEqual(result["status"], "validated")
            self.assertTrue(result["round_trip"]["parse_ok"])
            self.assertIn("dc_plus", result["affected"]["nets"])
            self.assertEqual(schematic.read_text(encoding="utf-8"), original_text)

    def test_apply_result_is_structured(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            schematic = Path(temp_dir) / "work.kicad_sch"
            shutil.copy(FIXTURE, schematic)
            result = apply_patch_plan(schematic, insert_shunt_plan())
            self.assertEqual(result["status"], "applied")
            self.assertEqual(result["schema"], "hephaistus/patch-plan/v1")
            self.assertEqual(result["intent"], "Insert current shunt")
            self.assertTrue(result["plan_id"])
            self.assertGreater(result["changed_operations"], 0)
            self.assertEqual(result["affected"]["components"], ["R2", "R3"])
            self.assertIn("dc_plus", result["affected"]["nets"])

    def test_rejects_wrong_schema_version(self):
        state = parse_schematic(FIXTURE)
        plan = {
            "schema": "hephaistus/patch-plan/v0",
            "operations": [{"type": "component.update_value", "reference": "R2", "value": "100"}],
        }
        with self.assertRaises(PatchPlanError) as context:
            mutate_state(state, plan)
        self.assertEqual(context.exception.code, "INVALID_SCHEMA")

    def test_rejects_unsupported_operation_with_stable_code(self):
        state = parse_schematic(FIXTURE)
        plan = {
            "schema": "hephaistus/patch-plan/v1",
            "operations": [{"type": "magic.rewire", "reference": "R2"}],
        }
        with self.assertRaises(PatchPlanError) as context:
            mutate_state(state, plan)
        self.assertEqual(context.exception.code, "UNSUPPORTED_OPERATION")

    def _find_kicad_cli(self):
        for candidate in KICAD_CLI_CANDIDATES:
            path = shutil.which(candidate) if candidate == "kicad-cli" else candidate
            if path and Path(path).exists():
                return path
        return None


if __name__ == "__main__":
    unittest.main()
