---
name: scartill-sdd-lite
description: "Lightweight Kiro-first specification driven development kit"
---

# Commands

- `Save Spec` - save persistent specification (prompt: `sc.save.spec.md`)
- `Split Tasks` - create standalone tasks (prompt: `sc.split.tasks.md`)
- `Implement` - run implementation (prompt: `sc.implement.tasks.md`)
- `Finalize` - post-implementation actions (prompt: `sc.finalize.md`)
- `Critique` - critique specification (prompt: `sc.critique.spec.md`, to file to critique as a parameter)
- `Code Review` - review implementation (prompt: `sc.code.review.md`)
- `Archive` - archive older project documentation (prompt: `sc.archive.md`)
- `Brainstorm` - Extended brainstorming (prompt: `sc.brainstorm.md`, the problem to consider is a parameter)
- `Seed` - convert final brainstorming results to a seed (prompt: `sc.brainstorm.to.seed.md`) 
- `Gate Input` - sanitize raw input, extract clean seed specs, and generate a PM feedback report (prompt: `sc.gate.input.md`, input document path as parameter)

All prompts reside in `<skill-dir>/prompts/`.

Upon activation, remember these commands, but do not run until an explicit user request.

# Guidance

## Specification Workflow: Seed vs Full Specs

This project uses a two-stage specification process. Both live under `docs/`.

### Seed Specs (`docs/seed/`)

A seed spec is a **concise, human-written intent document**. It captures:
- What the user wants (feature intent, desired behavior)
- Key examples and expected output formats
- High-level CLI interface or config shape
- Follow-up tasks (amend README, add examples, etc.)

Seed specs are informal, written in the user's voice, and may contain typos or shorthand. They do **not** include:
- Detailed implementation guidance
- Internal data models or code structure
- Explicit task breakdowns with test requirements
- Mermaid diagrams or architecture decisions
- Background on existing codebase internals

A seed spec is the **input** to the design phase.

### Full Specs (`docs/specs/`)

A full spec is a **detailed implementation blueprint** derived from a seed spec. It includes:
- **Problem Statement**: Precise restatement of the requirement
- **Requirements**: Exhaustive list of acceptance criteria
- **Background**: Relevant codebase internals (existing patterns, modules, data structures)
- **Proposed Solution**: Architecture with Mermaid diagrams, data models, and code sketches
- **Task Breakdown**: Numbered implementation tasks, each with:
  - Objective
  - Implementation guidance (which files, which patterns to follow)
  - Test requirements (what to assert, which fixtures to use)
  - Demo command to verify

Full specs are written for an implementer (human or AI) to execute without further clarification.

### Workflow

1. User writes a seed spec in `docs/seed/` to capture intent.
2. A full spec is produced in `docs/specs/` (either by the user or with AI assistance) that expands the seed into an actionable plan.
3. Implementation follows the full spec's task breakdown.

When asked to implement a feature, look for both the seed (for intent) and the full spec (for implementation details). If only a seed exists, offer to produce a full spec first.
