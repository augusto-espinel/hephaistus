"""
CLI for HephAIstus LLM Orchestration.

Provides commands for LLM-based schematic modifications.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from .orchestrator import LLMOrchestrator, HEPHAISTUS_SYSTEM_PROMPT
from .config import ProviderConfig, DEFAULT_CONFIGS
from .base import Message, MessageRole


def _cmd_generate(args: argparse.Namespace) -> int:
    """Generate a patch-plan proposal."""
    # Create provider config
    if args.provider == "openrouter":
        config = ProviderConfig.openrouter(
            model=args.model or "anthropic/claude-3.5-sonnet",
            api_key=args.api_key,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
    elif args.provider == "ollama":
        config = ProviderConfig.ollama(
            model=args.model or "llama3.1:70b",
            base_url=args.base_url,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
    else:
        print(f"Unknown provider: {args.provider}", file=sys.stderr)
        return 1
    
    # Create orchestrator
    orchestrator = LLMOrchestrator(provider_config=config)
    
    # Load schematic if provided
    if args.schematic:
        from hephaistus_circuit import parse_schematic
        parsed = parse_schematic(args.schematic)
        orchestrator.update_session(
            schematic_path=args.schematic,
            parsed_state=parsed,
            expertise_level=args.expertise,
            change_aggression=args.aggression,
        )
    
    # Generate
    proposal = orchestrator.generate(
        user_request=args.request,
        include_full_simulation=args.full_sim,
    )
    
    # Output
    if args.format == "json":
        output = {
            "raw_response": proposal.raw_response,
            "is_valid": proposal.is_valid(),
            "is_clarification": proposal.is_clarification,
            "patch_plan": proposal.patch_plan,
            "reasoning": proposal.reasoning,
            "parse_error": proposal.parse_error,
        }
        print(json.dumps(output, indent=2))
    else:
        if proposal.is_clarification:
            print(f"Clarification needed:\n{proposal.clarification_question}")
        elif proposal.is_valid():
            print("Proposed patch-plan:")
            print(json.dumps(proposal.patch_plan, indent=2))
            if proposal.reasoning:
                print(f"\nRationale: {proposal.reasoning}")
        else:
            print(f"Response (no valid patch-plan):\n{proposal.raw_response}")
            if proposal.parse_error:
                print(f"\nParse error: {proposal.parse_error}", file=sys.stderr)
    
    return 0


def _cmd_context(args: argparse.Namespace) -> int:
    """Assemble and show context."""
    config = ProviderConfig.openrouter()
    orchestrator = LLMOrchestrator(provider_config=config)
    
    if args.schematic:
        from hephaistus_circuit import parse_schematic
        parsed = parse_schematic(args.schematic)
        orchestrator.update_session(schematic_path=args.schematic, parsed_state=parsed)
    
    result = orchestrator.assemble_context(
        user_request=args.request or "Show me the current state",
        include_full_simulation=args.full_sim,
    )
    
    if args.format == "json":
        output = result.to_dict()
        print(json.dumps(output, indent=2))
    else:
        print(result.prompt)
        print(f"\n---\nTotal tokens: {result.total_tokens}", file=sys.stderr)
    
    return 0


def _cmd_models(args: argparse.Namespace) -> int:
    """List available models."""
    if args.provider == "openrouter":
        config = ProviderConfig.openrouter()
    elif args.provider == "ollama":
        config = ProviderConfig.ollama(base_url=args.base_url)
    else:
        print(f"Unknown provider: {args.provider}", file=sys.stderr)
        return 1
    
    orchestrator = LLMOrchestrator(provider_config=config)
    models = orchestrator.get_available_models()
    
    if args.format == "json":
        print(json.dumps(models, indent=2))
    else:
        print(f"Available models for {args.provider}:")
        for m in models:
            ctx = m.get("context_window", 0)
            print(f"  {m['id']}")
            print(f"    Context: {ctx:,} tokens")
            if m.get("pricing_input"):
                print(f"    Price: ${m['pricing_input']:.2f}/1M input, ${m['pricing_output']:.2f}/1M output")
    
    return 0


def _cmd_estimate(args: argparse.Namespace) -> int:
    """Estimate token count."""
    config = ProviderConfig.openrouter()
    orchestrator = LLMOrchestrator(provider_config=config)
    
    if args.file:
        text = Path(args.file).read_text()
    else:
        text = args.text
    
    count = orchestrator.estimate_tokens(text)
    print(f"Estimated tokens: {count}")
    
    return 0


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="hephaistus-llm",
        description="LLM orchestration for HephAIstus",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # generate
    gen_cmd = subparsers.add_parser("generate", help="Generate patch-plan proposal")
    gen_cmd.add_argument("request", help="User request in natural language")
    gen_cmd.add_argument("--provider", "-p", choices=["openrouter", "ollama"], default="openrouter")
    gen_cmd.add_argument("--model", "-m", help="Model to use")
    gen_cmd.add_argument("--api-key", "-k", help="API key (defaults to env var)")
    gen_cmd.add_argument("--base-url", "-u", help="Base URL for Ollama")
    gen_cmd.add_argument("--schematic", "-s", help="Path to KiCad schematic")
    gen_cmd.add_argument("--expertise", "-e", choices=["student", "hobbyist", "professional"])
    gen_cmd.add_argument("--aggression", "-a", choices=["conservative", "moderate", "aggressive"])
    gen_cmd.add_argument("--temperature", "-t", type=float, default=0.7)
    gen_cmd.add_argument("--max-tokens", type=int, default=4096)
    gen_cmd.add_argument("--full-sim", action="store_true", help="Include full simulation data")
    gen_cmd.add_argument("--format", "-f", choices=["text", "json"], default="text")
    gen_cmd.set_defaults(handler=_cmd_generate)
    
    # context
    ctx_cmd = subparsers.add_parser("context", help="Assemble and show context")
    ctx_cmd.add_argument("--request", "-r", default="", help="User request")
    ctx_cmd.add_argument("--schematic", "-s", help="Path to KiCad schematic")
    ctx_cmd.add_argument("--full-sim", action="store_true")
    ctx_cmd.add_argument("--format", "-f", choices=["text", "json"], default="text")
    ctx_cmd.set_defaults(handler=_cmd_context)
    
    # models
    models_cmd = subparsers.add_parser("models", help="List available models")
    models_cmd.add_argument("--provider", "-p", choices=["openrouter", "ollama"], default="openrouter")
    models_cmd.add_argument("--base-url", "-u", help="Base URL for Ollama")
    models_cmd.add_argument("--format", "-f", choices=["text", "json"], default="text")
    models_cmd.set_defaults(handler=_cmd_models)
    
    # estimate
    est_cmd = subparsers.add_parser("estimate", help="Estimate token count")
    est_cmd.add_argument("text", nargs="?", help="Text to estimate")
    est_cmd.add_argument("--file", "-f", help="Read from file")
    est_cmd.set_defaults(handler=_cmd_estimate)
    
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())