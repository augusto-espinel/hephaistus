#!/usr/bin/env python3
"""Test thinking block extraction for DeepSeek-style responses."""
import sys
sys.path.insert(0, 'backend')
from hephaistus_llm.orchestrator import _extract_thinking_blocks, _THINK_TAG_OPEN, _THINK_TAG_CLOSE

# Test 1: DeepSeek-style  ...  with everything inside
test1 = _THINK_TAG_OPEN + "\nLet me analyze the circuit...\n\nBased on the simulation, the midpoint voltage is drifting.\n\nHere is my proposal:\n```json\n{\"schema\": \"hephaistus/patch-plan/v1\", \"operations\": []}\n```\n\nThis resistor will help stabilize the midpoint.\n" + _THINK_TAG_CLOSE

thinking, display = _extract_thinking_blocks(test1)
print("=== Test 1: DeepSeek  tags (everything inside) ===")
print(f"thinking_content ({len(thinking)} chars):")
print(f"  {thinking[:200]}...")
print(f"display_content ({len(display)} chars):")
print(f"  {display}")
print()

# Test 2: Partial thinking + answer outside
test2 = "<thinking>\nLet me analyze the circuit...\n</thinking>\n\nBased on the simulation, here is my proposal:\n```json\n{\"schema\": \"hephaistus/patch-plan/v1\", \"operations\": []}\n```\n\nThis will help stabilize the midpoint."

thinking2, display2 = _extract_thinking_blocks(test2)
print("=== Test 2: <thinking> + answer outside ===")
print(f"thinking_content ({len(thinking2)} chars): {thinking2[:100]}...")
print(f"display_content: {display2}")
print()

# Test 3: No thinking tags at all
test3 = "Here is my analysis:\n```json\n{\"schema\": \"hephaistus/patch-plan/v1\"}\n```\n\nThis should work."

thinking3, display3 = _extract_thinking_blocks(test3)
print("=== Test 3: No thinking tags ===")
print(f"thinking_content: '{thinking3}'")
print(f"display_content: {display3}")
