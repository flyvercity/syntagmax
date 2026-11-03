# Prompt: Ingest & Gate Raw Input

You are an expert software architect and technical gatekeeper. Your task is to process raw, potentially noisy, or agent-generated feature requests/proposals, extract clean and compliant seed specifications, and generate a comprehensive, conversational feedback report for product managers and stakeholders.

---

## Input

- **Target Document**: `${ARGUMENTS}` (Path to the raw input document or specification draft).
- **Codebase Context**: Existing repository structure, configuration files, and high-level interface definitions.

---

## Gating & Extraction Rules

### 1. What Belongs in a Seed Spec (`docs/seed/<feature-name>.md`)
- **Core Intent**: What the user or system should achieve and why.
- **Surface Interfaces**: Explicit CLI options, flags, top-level configuration keys, or user-facing API contracts.
- **Expected Behaviour & I/O**: Concrete examples, inputs, expected outputs, payloads, and error formats.
- **Functional & Behavioural Constraints**: High-level latency/throughput targets, formats, or domain rules.
- **Follow-up Tasks**: Documentation, examples, testing suggestions.

### 2. What Must Be Stripped Unconditionally
- **Code Snippets & Implementations**: Function bodies, internal algorithms, ORM/database queries, and internal class definitions.
- **Foreign/Hallucinated Architecture**: Assumptions about frameworks, libraries, internal data models, or patterns that do not exist in the codebase.
- **Internal Task Breakdowns**: Numbered implementation plans, step-by-step coding sequences, or test fixtures (these belong strictly to full specs in `docs/specs/`).

### 3. Multi-Feature Splitting
- If the input document covers multiple distinct capabilities or independent workflows, decompose them into separate seed files (`docs/seed/<feature-a>.md`, `docs/seed/<feature-b>.md`).
- Do not bundle unrelated functionality into a single monolithic seed.

---

## Execution Workflow

1. **Inspect & Ground**:
   - Read the input document `${ARGUMENTS}`.
   - Inspect the codebase to verify repository realities (CLI conventions, configuration file formats, module boundaries).

2. **Blocker Analysis**:
   - Check for fatal blockers: contradictory requirements, broken reference links, unresolvable ambiguities, or zero extractable intent.
   - If fatal blockers make extraction impossible, do not generate seeds; generate a rejection report directly.

3. **Extract & Write Seed Specs**:
   - For each valid feature identified, create or update `docs/seed/<feature-name>.md`.
   - Ensure the seed is written in concise, intent-focused prose, preserving only surface interfaces and behaviour.

4. **Compile & Write Feedback Report**:
   - Create or update `docs/seed-feedback/<input-basename>-feedback.md`.
   - Use a constructive, conversational tone suitable for negotiation with PMs and upstream authors.
   - Detail extracted items, clarify ambiguities, and list all stripped implementation details so the PM can restate them functionally if necessary.

5. **User Notification**
   - Inform the user which seed were generated, if successful.
   - Remind the user to remove `do not use` markers manually.

---

## Artefact Templates

Note that the seed template starts with a draft marker that the user should remove manually post-generation.

### A. Seed Specification Template (`docs/seed/<feature-name>.md`)

```markdown
NOTE TO AGENTS: This is a draft, DO NOT use.

# Seed: <Feature Title>

## Intent
<What addresses and behavior expected. is need this what>

## Interface & Configuration
<High-level CLI Skip applicable. config endpoints. flags, if keys, not or user-facing>

## Expected Behaviour & Examples
<Inputs, examples. expected format or outputs, shapes, usage>

## Constraints
<High-level (e.g. compatibility). constraints format latency, non-functional>

## Follow-up Tasks
- Update documentation / README
- Add functional examples
```

### B. Feedback Report Template (docs/seed-feedback/<input-basename>-feedback.md)

```markdown
# Gating Feedback Report: <Input Document Name>

## 1. Metadata
- **Source File**: `<path/to/input.md>`
- **Date**: `<YYYY-MM-DD>`
- **Git Reference**: `<commit-hash-or-branch>`
- **Triage Status**: `ACCEPTED` | `PARTIALLY_ACCEPTED` | `REJECTED`

---

## 2. Critical Blockers
*(Omit or state "None" if clear. If the input is fully rejected, explain the fatal flaws here.)*
- **Contradictions**: <Specific conflicting requirements>
- **Broken Links / Missing References**: <Invalid URLs, broken docs missing paths,>
- **Viability Issues**: <Why extraction not possible was>

---

## 3. What Was Extracted

### Requirements Summary
- **Functional**: <Bullet extracted functional needs points summarizing>
- **Non-Functional**: <Bullet constraints operational points summarizing valid>

### Extracted Seed Specs
- [`docs/seed/<feature-1>.md`](../seed/<feature-1>.md): <Brief 1-line of scope summary>
- [`docs/seed/<feature-2>.md`](../seed/<feature-2>.md): <Brief 1-line of scope summary>

---

## 4. Feedback & Clarifications Required
*(Conversational questions addressed to the PM / document author to unblock full specification derivation.)*

1. **<Topic / Ambiguity>**: <Context and conversational question. specific>
2. **<Topic / Case Edge>**: <Context and conversational question. specific>

---

## 5. What Was Discarded

### Foreign Assumptions
- **<Assumption>**: <Explanation align codebase does not of or patterns. reality repository this why with>

### Implementation Details
- **<Code / Architecture Proposal>**: <Summary Advise ORM/library PM a as behavioral classes, critical. if internal of or requirement restate snippets, specific stripped suggestions. the to>
```

