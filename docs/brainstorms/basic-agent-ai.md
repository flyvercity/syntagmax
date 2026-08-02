# Brainstorm: Phase 1 Agentic Commands — Critique of General Approach

Source seed: `docs/seed/basic-agent-ai.md`

## Strengths

1. **Agent-agnostic design is pragmatic.** Delegating to local CLI agents avoids the complexity of managing API keys, rate limits, token budgets, and billing within the tool itself. The user authenticates once per agent; Syntagmax stays out of it.

2. **YAML-based extensibility is sound.** A registry of command-line patterns makes adding new agents trivial without code changes. Good separation of concerns.

3. **The five-step flow is well-structured.** Conventional pre-processing → prompt → invocation → post-processing → finalisation gives clear boundaries for testing each phase independently.

4. **Scoping to impact tasks first is wise.** It's a bounded, well-defined problem with clear success criteria — good pilot territory.

## Concerns and Gaps

### 1. Agent output parsing is underspecified

The spec says "conventional agent output analysis" and "verify new state of the task" but doesn't define the contract between the agent and Syntagmax. Key questions:

- Does the agent modify the task file directly (file-system side-effect), or does it return structured output that Syntagmax then applies?
- If the agent writes the file, how does Syntagmax distinguish a well-formed modification from a hallucinated rewrite that corrupts the file?
- What if the agent produces no output, partial output, or errors out?

**Recommendation:** Define a strict output contract — either the agent returns a structured verdict (JSON/YAML block in stdout) that Syntagmax applies, or the agent modifies the file and Syntagmax validates a diff. The former is more robust.

**Response:**
> This contract wiil be task-dependent. The impact task verification, I want to test in-place editing first as a side effect, no structured output. 

### 2. "Append agent's report to the task file" conflates analysis with mutation

Asking the agent to both assess *and* mutate the file in one shot means you can't retry the assessment without first reverting the file. It also makes validation harder — you're checking a file the agent already changed rather than deciding whether to accept a proposed change.

**Recommendation:** Two-phase approach: agent produces a verdict + rationale as output; Syntagmax applies the mutation if validation passes.

**Response:**

> Again, I want to test the side-effect approach first.

### 3. One-shot mode is fragile for this task

Verifying parent-child consistency requires reading multiple files, potentially running `git log`, and reasoning about change semantics. A single prompt with no tool use is likely to hallucinate file contents or miss context.

- Some listed agents (Kiro CLI, Claude Code, Codex) support tool use / file reading in one-shot mode — but others (Mistral Vibe, Copilot CLI) may not.
- The spec should clarify: does the agent get the relevant file contents *injected into the prompt*, or is it expected to read them itself?

**Recommendation:** Syntagmax should gather all context (parent content, child content, relevant git history) and inject it into the prompt. This makes the approach agent-agnostic and deterministic. Agents that can use tools get a simpler prompt; agents that can't still have all necessary context.

**Response:**

> These are all advanced agents. We have no need to adapt to simpler kinds. A prompt must be a detailed instruction, but agetn are more that capable to fetch the context and contents.

### 4. No timeout or failure handling

CLI agents can hang, crash, or produce garbage. The spec doesn't address:

- Timeout after N seconds
- Exit code handling
- Retry policy
- What happens if the agent closes the task incorrectly (false positive)

**Response:**
> We must call the agent interactively so the user can monitor and abort the process. Considering "false positive" - there are no conventional ways (non-AI, non-human) to catch this, are there?

### 5. The dirty-repo check is overly strict by default

Impact verification is a *read-then-write-one-file* operation. Requiring a clean repo means users must stash unrelated work. The `--allow-dirty` escape hatch exists, but the default seems hostile to normal workflow — especially since the agent is told to use "current working tree versions."

**Recommendation:** Default to allowing dirty state (the operation is localised to one task file). Or: only require that the *task file itself* and the referenced artifacts are not dirty.

**Response:**

> OK, let's make it a simple warning. No escape hatch needed.

### 6. No rollback or dry-run

If the agent corrupts the task file, there's no built-in recovery beyond `git checkout`. A `--dry-run` mode that shows the proposed changes without applying them would be consistent with other Syntagmax commands (`edit identification --dry-run`, `edit attrs --dry-run`).

**Response:**

> No need, Git will help with that.

### 7. Agent selection is unspecified

Which agent gets invoked? Is there a `--agent` flag? A default in config? What if multiple are installed?

**Response:**

> Good catch. Use `[ai]` section in the config, with `--agent` override.

## Summary

The architectural instinct is right — lean on existing agents, keep Syntagmax as the orchestrator. The main risk is the *interface boundary* between Syntagmax and the agent: the spec needs a tighter contract for what goes in (prompt with injected context) and what comes out (structured verdict), with Syntagmax owning all file mutations. Without that, you're trusting an LLM to be a well-behaved file editor, which is the brittlest part of the system.


## Prompt Template Brainstorm: Impact Task Verification

### Draft Prompt Template

```
You are verifying an impact traceability task for a requirements management system.

## Task File
Path: {{ task_file_path }}

## Context
A parent artifact was updated after the child artifact was last verified against it.
Your job is to determine whether the child artifact is still consistent with the
current parent, or whether it needs further updates.

## Artifacts

### Parent (updated)
- ID: {{ parent_aid }}
- File: {{ parent_file_path }}
- Revision at time of task creation: {{ parent_revision }}

### Child (potentially outdated)
- ID: {{ child_aid }}
- File: {{ child_file_path }}

## Instructions

1. Read the parent artifact file at `{{ parent_file_path }}`.
2. Read the child artifact file at `{{ child_file_path }}`.
3. Optionally, run `git log --oneline {{ parent_revision }}..HEAD -- {{ parent_file_path }}`
   to understand what changed in the parent since the task was created.
4. Assess whether the child artifact's content and tracing reference are consistent
   with the parent's current state. Consider:
   - Does the child still correctly derive from / implement the parent?
   - Are there semantic gaps introduced by the parent's changes?
   - Is the child's scope still aligned with the parent's scope?
5. Edit the task file at `{{ task_file_path }}`:
   - If the child IS consistent: set `status: closed` in the frontmatter.
   - If the child is NOT consistent: leave `status: open`.
   - In both cases, append a `## Verification Report` section at the end of the file
     with your assessment rationale.

## Format Requirements for Task File Edit

- Do NOT modify the `id` field in the frontmatter.
- Do NOT modify the `contents` field in the frontmatter.
- Do NOT alter the existing markdown sections (Parent, Child, Action Required).
- Only change `status` from `open` to `closed` if verification passes.
- Append your report as a new `## Verification Report` section at the end.
- Keep the report concise: 3-10 sentences explaining your reasoning.
```

### Open Questions

**A. Should the prompt include the actual artifact content inline?**

Agents can fetch it themselves, but including content as reference could reduce hallucination risk at zero cost (the content is small). Trade-off: prompt length vs. reliability.

**Response:**

> No, these agents are OK in such tasks.

**B. Should we instruct the agent to update `parent_revision` / `child_revision` in frontmatter?**

If the child was updated and is now consistent, the task's recorded revisions are stale. Updating them would prevent re-triggering on next impact analysis. But this adds complexity to the format contract.

**Response:**

> No, absolutely not. What agent must do, is to add actual parent and child reference to it's report (marking references as dirty, if a corresponding repo is dirty). Important note: the child and the parent may reside in different repos. The agent shall be warned about it. 

**C. How prescriptive should the report format be?**

Options range from free-form prose to a structured template:
```markdown
## Verification Report
- **Verdict:** PASS / FAIL
- **Rationale:** ...
- **Checked at:** <timestamp>
```
A structured format makes post-validation easier (grep for `Verdict: PASS` → confirm status=closed).

**Response:**

> Structured with a concise prose section.

**D. Should we provide a "persona" or domain context?**

E.g., "You are a systems engineer reviewing traceability in an aerospace/UAV project." This could improve reasoning quality but couples the prompt to a specific domain.

**Response:**

> I propose to set the default persona as "You are a systems engineer reviewing requirements traceability.", but make it configurable via `[ai.impact_persona]`.

**E. Git history: explicit command or leave to agent?**

The prompt currently *suggests* a git command. Alternative: just say "understand what changed" and let the agent decide how.

**Response:**

> Let agent decide. These agent are used to git.
