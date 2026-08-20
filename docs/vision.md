# HephAIstus Vision

Version: 2.1
Date: 2026-08-20
Status: Implementation progress

## One-sentence vision

HephAIstus is an AI copilot for KiCad schematic design and circuit simulation that removes copy/paste mediation between the engineer, the design files, and the simulation environment.

## Problem

Engineers increasingly use LLMs to reason about electronics, but the interaction is still manual and lossy:

- Copy schematic files into a chat.
- Screenshot the simulator.
- Paste convergence errors from a console.
- Manually transcribe proposed changes.
- Re-run validation and simulation by hand.

That workflow works, but it wastes expert attention on context transport instead of engineering judgment.

Augusto's manual experiments already proved the value: an LLM helped identify rectifier connection mistakes, tune transient simulation parameters, and reason about constant-power-load implementations. HephAIstus exists to automate the context and action loop around that value.

## Product concept

HephAIstus is a desktop companion window that can sit beside KiCad. It has a prompt-driven interface similar to an IDE copilot, but its reasoning is grounded in deterministic engineering context.

The companion can:

- ingest the current schematic hierarchy;
- read ERC and simulation artifacts;
- inspect simulation console output and waveform data;
- answer questions about the circuit;
- propose schematic or simulation changes;
- show a preview before applying anything;
- execute validated changes;
- rerun validation and simulation;
- preserve an audit trail.

## Operating principles

### 1. Human owns geometry and judgment

The engineer remains responsible for schematic placement, visual organization, architecture, safety, and final acceptance. HephAIstus assists with analysis, parameter tuning, topology experimentation, and validated patches.

### 2. KiCad files are the source of truth

The circuit graph is derived from KiCad project files. A persisted JSON ledger is not required as the system's architectural spine.

### 3. LLM proposes; deterministic backend disposes

The LLM may explain, diagnose, and propose. A deterministic backend parses, validates, applies, exports, and simulates. No arbitrary free-form file rewriting by the model.

### 4. Every mutation is previewable

Proposed schematic or simulation changes should be presented as inspectable cards with:

- intent;
- affected components/nets/parameters;
- validation plan;
- risks;
- dry-run result when possible;
- apply/revert controls.

### 5. Validation follows every action

After an accepted change, HephAIstus must re-parse and validate. Schematic changes should run ERC when available; simulation changes should rerun or compare the requested simulation.

## Target experience

The user should be able to open a KiCad schematic and ask:

- "Why is this rectifier connection wrong?"
- "Which net should this pin belong to?"
- "Why is transient analysis failing to converge?"
- "What changed between these two simulation runs?"
- "How should I implement a constant-power load?"
- "Insert a current shunt between these two components and rerun."

The copilot should answer with context, propose a patch when appropriate, and apply it only with explicit confirmation.

**Implemented:** Stub-based restructuring is fully working for series insertions and net re-assignments. The "insert a current shunt" use case (UC-07) is validated with 26/26 tests passing and kicad-cli ERC confirmation.

## Strategic boundary

HephAIstus is not:

- a replacement for engineering review;
- an unrestricted autopilot that mutates schematics silently;
- a generic chat window detached from design context;
- a copy/paste wrapper around KiCad.

## Near-term host decision

A truly embedded KiCad schematic plugin/panel is not the immediate target because KiCad 9/10 IPC plugin support is still focused on the PCB editor and schematic support is future work. The near-term host is a standalone companion application that feels integrated while relying only on stable file/CLI interfaces.

## Success definition

HephAIstus succeeds when an engineer can iterate on schematic and simulation work without manually transporting files, screenshots, plots, or logs into an LLM chat.
