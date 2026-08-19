"""Command line interface for the deterministic HephAIstus circuit backend."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import (
    apply_patch_plan,
    dump_json,
    load_patch_plan,
    parse_schematic,
    validate_patch_plan,
)
from .errors import PatchPlanError


def _cmd_parse(args: argparse.Namespace) -> int:
    try:
        payload = parse_schematic(Path(args.schematic))
    except PatchPlanError as exc:
        print(json.dumps(exc.to_dict()))
        return 2
    print(dump_json(payload))
    return 0


def _cmd_apply_plan(args: argparse.Namespace) -> int:
    try:
        plan = load_patch_plan(Path(args.plan))
        if args.dry_run:
            payload = validate_patch_plan(Path(args.schematic), plan)
        else:
            payload = apply_patch_plan(Path(args.schematic), plan, output_path=args.output)
    except PatchPlanError as exc:
        print(json.dumps(exc.to_dict(), indent=2))
        return 2
    print(dump_json(payload))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hephaistus-circuit",
        description="Deterministic KiCad schematic patch and parse backend",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_parser = subparsers.add_parser("parse", help="parse a .kicad_sch into a derived state")
    parse_parser.add_argument("schematic", help="path to the KiCad schematic")
    parse_parser.set_defaults(handler=_cmd_parse)

    apply_parser = subparsers.add_parser("apply-plan", help="validate and apply a patch plan")
    apply_parser.add_argument("schematic", help="path to the KiCad schematic")
    apply_parser.add_argument("plan", help="path to patch-plan JSON")
    apply_parser.add_argument("--dry-run", action="store_true", help="validate without changing the schematic")
    apply_parser.add_argument("--output", help="optional output schematic path")
    apply_parser.set_defaults(handler=_cmd_apply_plan)

    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
