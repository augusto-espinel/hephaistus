"""Command line interface for the HephAIstus simulation parsing backend."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .parser import (
    parse_console_output,
    parse_dc_op_points,
    parse_waveform_raw,
    parse_ngspice_output,
)
from .run_metadata import (
    create_run_metadata,
    save_run_metadata,
    load_run_metadata,
    check_correlation,
    CorrelationStatus,
)
from .context import (
    assemble_context,
)
from .waveform import (
    WaveformConfig,
)


def _cmd_parse_console(args: argparse.Namespace) -> int:
    """Parse ngspice console output."""
    try:
        with open(args.input, "r") as f:
            output = f.read()
    except FileNotFoundError:
        print(json.dumps({"error": f"File not found: {args.input}"}))
        return 2
    
    parsed = parse_console_output(output)
    result = {
        "analyses": [{"type": a.analysis_type, "status": a.status} for a in parsed.analyses],
        "convergence": {
            "converged": parsed.convergence.converged if parsed.convergence else None,
            "error_type": parsed.convergence.error_type if parsed.convergence else None,
            "message": parsed.convergence.message if parsed.convergence else None,
        },
        "warnings": parsed.warnings,
        "errors": parsed.errors,
    }
    print(json.dumps(result, indent=2))
    return 0


def _cmd_parse_op(args: argparse.Namespace) -> int:
    """Parse DC operating points."""
    try:
        with open(args.input, "r") as f:
            output = f.read()
    except FileNotFoundError:
        print(json.dumps({"error": f"File not found: {args.input}"}))
        return 2
    
    points = parse_dc_op_points(output)
    result = {
        "op_points": [
            {"name": p.name, "value": p.value, "unit": p.unit}
            for p in points
        ]
    }
    print(json.dumps(result, indent=2))
    return 0


def _cmd_parse_raw(args: argparse.Namespace) -> int:
    """Parse ngspice raw waveform file."""
    raw_file = Path(args.input)
    result = parse_waveform_raw(raw_file)
    print(json.dumps(result, indent=2))
    return 0


def _cmd_create_run(args: argparse.Namespace) -> int:
    """Create run metadata."""
    schematic_path = Path(args.schematic)
    
    if not schematic_path.exists():
        print(json.dumps({"error": f"Schematic not found: {schematic_path}"}))
        return 2
    
    # Parse parameters
    params = {}
    if args.param:
        for p in args.param:
            if "=" in p:
                k, v = p.split("=", 1)
                params[k] = v
    
    console_path = Path(args.console) if args.console else None
    raw_path = Path(args.raw) if args.raw else None
    op_path = Path(args.op) if args.op else None
    
    run = create_run_metadata(
        schematic_path=schematic_path,
        analysis_type=args.analysis,
        parameters=params,
        console_output_path=console_path,
        raw_file_path=raw_path,
        op_file_path=op_path,
        converged=not args.failed,
        error_type=args.error_type,
        error_message=args.error_message,
    )
    
    output_path = Path(args.output) if args.output else Path(f"run_{run.run_id}.json")
    save_run_metadata(run, output_path)
    
    print(json.dumps({"run_id": run.run_id, "output": str(output_path)}, indent=2))
    return 0


def _cmd_check_correlation(args: argparse.Namespace) -> int:
    """Check correlation between run and current schematic."""
    try:
        run = load_run_metadata(Path(args.run))
        schematic_path = Path(args.schematic)
        correlation = check_correlation(run, schematic_path)
        
        result = {
            "status": correlation.value,
            "run_id": run.run_id,
            "run_schematic": run.schematic_path,
            "run_timestamp": run.timestamp.isoformat(),
            "run_hash": run.schematic_hash,
        }
        print(json.dumps(result, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        return 2


def _cmd_context(args: argparse.Namespace) -> int:
    """Assemble LLM context from schematic and simulation."""
    try:
        from hephaistus_circuit import parse_schematic
        
        schematic_path = Path(args.schematic)
        schematic_state = parse_schematic(schematic_path)
        
        run = None
        if args.run:
            run = load_run_metadata(Path(args.run))
        
        # Build waveform config from args
        waveform_config = WaveformConfig(
            max_raw_points=args.max_raw_points,
            max_signals=args.max_signals,
            include_stats=not args.no_stats,
            include_trend=not args.no_trend,
            include_final_n=args.final_points,
            include_initial_n=args.initial_points,
            include_peaks=not args.no_peaks,
            include_crossings=not args.no_crossings,
        )
        
        context = assemble_context(
            schematic_path=schematic_path,
            schematic_state=schematic_state,
            run=run,
        )
        
        if args.format == "json":
            print(json.dumps(context.to_dict(), indent=2))
        else:
            print(context.get_llm_context(waveform_config=waveform_config))
        
        return 0
    except ImportError as e:
        print(json.dumps({"error": f"hephaistus_circuit not available: {e}"}))
        return 2
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hephaistus-simulation",
        description="Simulation output parsing for HephAIstus",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # parse-console
    parse_console = subparsers.add_parser("parse-console", help="parse ngspice console output")
    parse_console.add_argument("input", help="path to console output file")
    parse_console.set_defaults(handler=_cmd_parse_console)
    
    # parse-op
    parse_op = subparsers.add_parser("parse-op", help="parse DC operating points")
    parse_op.add_argument("input", help="path to operating points output")
    parse_op.set_defaults(handler=_cmd_parse_op)
    
    # parse-raw
    parse_raw = subparsers.add_parser("parse-raw", help="parse ngspice raw waveform file")
    parse_raw.add_argument("input", help="path to .raw file")
    parse_raw.set_defaults(handler=_cmd_parse_raw)
    
    # create-run
    create_run = subparsers.add_parser("create-run", help="create run metadata")
    create_run.add_argument("schematic", help="path to .kicad_sch")
    create_run.add_argument("--analysis", "-a", default="tran", help="analysis type (tran, ac, dc, op)")
    create_run.add_argument("--param", "-p", action="append", help="parameter (key=value)")
    create_run.add_argument("--console", "-c", help="path to console output")
    create_run.add_argument("--raw", "-r", help="path to .raw waveform file")
    create_run.add_argument("--op", "-o", help="path to operating points file")
    create_run.add_argument("--output", help="output run metadata path")
    create_run.add_argument("--failed", action="store_true", help="mark as failed/converged=false")
    create_run.add_argument("--error-type", help="error type if failed")
    create_run.add_argument("--error-message", help="error message if failed")
    create_run.set_defaults(handler=_cmd_create_run)
    
    # check-correlation
    check_corr = subparsers.add_parser("check-correlation", help="check run-to-schematic correlation")
    check_corr.add_argument("run", help="path to run metadata JSON")
    check_corr.add_argument("schematic", help="path to current .kicad_sch")
    check_corr.set_defaults(handler=_cmd_check_correlation)
    
    # context
    context = subparsers.add_parser("context", help="assemble LLM context")
    context.add_argument("schematic", help="path to .kicad_sch")
    context.add_argument("--run", "-r", help="path to run metadata JSON")
    context.add_argument("--format", "-f", choices=["json", "text"], default="text", help="output format")
    # Waveform config options
    context.add_argument("--max-raw-points", type=int, default=100, help="max raw points to include (0=none)")
    context.add_argument("--max-signals", type=int, default=10, help="max signals in context")
    context.add_argument("--no-stats", action="store_true", help="exclude statistics")
    context.add_argument("--no-trend", action="store_true", help="exclude trend analysis")
    context.add_argument("--final-points", type=int, default=50, help="final N points to include")
    context.add_argument("--initial-points", type=int, default=20, help="initial N points to include")
    context.add_argument("--no-peaks", action="store_true", help="exclude peak detection")
    context.add_argument("--no-crossings", action="store_true", help="exclude zero crossings")
    context.set_defaults(handler=_cmd_context)
    
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())