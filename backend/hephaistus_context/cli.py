"""
CLI for HephAIstus Context Service.

Provides commands for context assembly and inspection.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from .context_service import ContextService, ContextAssemblyResult
from .session_state import ExpertiseLevel, ChangeAggression


def _cmd_init(args: argparse.Namespace) -> int:
    """Initialize a new context session."""
    service = ContextService()
    
    expertise = args.expertise or "professional"
    aggression = args.aggression or "moderate"
    
    session = service.initialize_session(
        schematic_path=args.schematic,
        expertise_level=expertise,
        change_aggression=aggression,
        explain_steps=args.explain,
    )
    
    result = {
        "session_id": session.session_id,
        "status": "initialized",
        "schematic": session.schematic.path or "(none)",
        "directives": session.directives.to_dict(),
    }
    
    print(json.dumps(result, indent=2))
    return 0


def _cmd_assemble(args: argparse.Namespace) -> int:
    """Assemble context for LLM."""
    service = ContextService()
    
    # Initialize if schematic provided
    if args.schematic:
        service.initialize_session(schematic_path=args.schematic)
    
    # Assemble
    result = service.assemble(
        user_request=args.request or "",
        include_full_simulation=args.full_sim,
    )
    
    if args.format == "json":
        output = result.to_dict()
        output["prompt"] = result.prompt
        print(json.dumps(output, indent=2))
    else:
        print(result.prompt)
        print("\n---", file=sys.stderr)
        print(f"Tokens: {result.total_tokens}", file=sys.stderr)
        if result.budget:
            summary = result.budget.summary()
            print(f"Budget used: {summary['utilization']:.1%}", file=sys.stderr)
    
    return 0


def _cmd_debug(args: argparse.Namespace) -> int:
    """Show debug view of context state."""
    service = ContextService()

    if args.schematic:
        service.initialize_session(schematic_path=args.schematic)

    debug = service.get_debug_view()
    print(json.dumps(debug, indent=2))
    return 0


def _cmd_history(args: argparse.Namespace) -> int:
    """Manage conversation history."""
    from .history_store import HistoryStore, HistoryEntryRecord
    import uuid
    
    store = HistoryStore(db_path=args.db)
    
    if args.history_cmd == 'search':
        results = store.search(args.query, limit=args.limit)
        for r in results:
            print(f"[{r.entry.id}] {r.entry.user_request[:50]}")
            print(f"  Action: {r.entry.user_action or 'none'}")
            print(f"  Score: {r.relevance_score:.2f} ({r.match_type})")
            print()
    
    elif args.history_cmd == 'recent':
        entries = store.get_recent(limit=args.limit, session_id=args.session)
        for e in entries:
            print(f"[{e.id}] {e.user_request[:50]}")
            print(f"  Time: {e.timestamp}")
            print()
    
    elif args.history_cmd == 'stats':
        stats = store.get_statistics(session_id=args.session)
        print(json.dumps(stats, indent=2, default=str))
    
    return 0


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hephaistus-context",
        description="Context management service for HephAIstus",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # init
    init_cmd = subparsers.add_parser("init", help="Initialize new context session")
    init_cmd.add_argument("--schematic", "-s", help="Path to KiCad schematic")
    init_cmd.add_argument("--expertise", "-e", choices=["student", "hobbyist", "professional"])
    init_cmd.add_argument("--aggression", "-a", choices=["conservative", "moderate", "aggressive"])
    init_cmd.add_argument("--explain", action="store_true", help="Enable step explanations")
    init_cmd.set_defaults(handler=_cmd_init)
    
    # assemble
    asm_cmd = subparsers.add_parser("assemble", help="Assemble context for LLM")
    asm_cmd.add_argument("--schematic", "-s", help="Path to KiCad schematic")
    asm_cmd.add_argument("--request", "-r", default="", help="User request to prepend")
    asm_cmd.add_argument("--format", "-f", choices=["text", "json"], default="text")
    asm_cmd.add_argument("--full-sim", action="store_true", help="Include full simulation data")
    asm_cmd.set_defaults(handler=_cmd_assemble)
    
    # debug
    debug_cmd = subparsers.add_parser("debug", help="Show debug view")
    debug_cmd.add_argument("--schematic", "-s", help="Path to KiCad schematic")
    debug_cmd.set_defaults(handler=_cmd_debug)
    
    # history
    history_cmd = subparsers.add_parser("history", help="Manage conversation history")
    history_cmd.add_argument("--db", "-d", default=".hephaistus/history.db", help="Database path")
    history_sub = history_cmd.add_subparsers(dest="history_cmd", required=True)
    
    # history search
    search_cmd = history_sub.add_parser("search", help="Search history")
    search_cmd.add_argument("query", help="Search query")
    search_cmd.add_argument("--limit", "-l", type=int, default=10, help="Max results")
    search_cmd.add_argument("--session", "-s", help="Filter by session")
    
    # history recent
    recent_cmd = history_sub.add_parser("recent", help="Recent entries")
    recent_cmd.add_argument("--limit", "-l", type=int, default=20, help="Max results")
    recent_cmd.add_argument("--session", "-s", help="Filter by session")
    
    # history stats
    stats_cmd = history_sub.add_parser("stats", help="Show statistics")
    stats_cmd.add_argument("--session", "-s", help="Filter by session")
    
    history_cmd.set_defaults(handler=_cmd_history)
    
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
