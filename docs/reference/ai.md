# AI Commands Reference

> ⚠️ **IMPORTANT: Unrestricted Agent Execution**
>
> Syntagmax invokes AI agents with full file system and shell access. The agent runs with the same permissions as the current user and can read, write, or delete any file in the working directory. Syntagmax does NOT sandbox the agent in any way. Review the agent's output and use `git diff` to inspect all changes before committing.

Syntagmax integrates with local CLI AI coding agents to automate verification and analysis tasks. All AI commands are grouped under `syntagmax ai`.

## Commands

### `syntagmax ai verify`

Verify an impact task using an AI agent. The agent assesses whether a child artifact is still consistent with its updated parent and updates the task file accordingly.

```bash
syntagmax ai verify <task-file> [OPTIONS]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `task_file` | Yes | Path to the impact task file to verify |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--agent <name>` | Config default | Override the default agent |
| `--amend` | off | Directly amend the child artifact if verification fails |

#### Behaviour

1. Parses the task file and validates it is an impact task (`TASK-IMPACT-*` ID pattern).
2. Checks that task status is `open`.
3. Emits a warning if the repository is dirty (proceeds regardless).
4. Resolves the AI agent from configuration or `--agent` flag.
5. Renders a prompt with task metadata and invokes the agent interactively.
6. After agent completes, validates the task file:
   - ID is unchanged
   - Status is `open` or `closed`
   - A `## Verification Report` section was appended
7. When `--amend` is set, additionally validates the child artifact (must exist, be non-empty, and have valid frontmatter if present).
8. Reports the outcome.

#### Two-Phase Verification

The agent prompt is structured in two explicit phases:

**Phase 1 (Analysis)** — always runs. The agent reads both artifacts, inspects git history since the recorded parent revision, maps each parent change to a child response, and appends a `## Verification Report` section to the task file containing the verdict (PASS or FAIL), revision metadata, Parent Changes, Child Changes, Change Mapping, and Rationale.

**Phase 2 — Recommendation (default, `--amend` absent)** — runs only on FAIL. The agent appends a `### Amendment Recommendation` subsection inside the Verification Report, providing a bulleted list of specific, actionable edits needed to bring the child into consistency. The child artifact is NOT modified.

**Phase 2 — Implementation (`--amend` present)** — runs only on FAIL. The agent edits the child artifact directly to resolve each discrepancy identified in the Change Mapping, then sets `status: closed` in the task frontmatter and appends a `### Amendment Applied` subsection describing what was changed.

**Uncertainty handling** — if the agent is unsure how to perform Phase 2 (the required change is ambiguous or requires design judgment), it MUST leave `status: open`, leave the child artifact untouched, and append a `### Rationale` subsection explaining specifically why it is uncertain and what information would be needed to proceed.

#### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success (task verified and closed, or requires more work) |
| 1 | Error (unsupported task type, agent failure, invalid output) |

#### Examples

```bash
# Verify a task using the default agent
syntagmax ai verify .syntagmax/tasks/TASK-IMPACT-REQ-003-SYS-003.md

# Verify using a specific agent
syntagmax ai verify .syntagmax/tasks/TASK-IMPACT-REQ-003-SYS-003.md --agent claude-code

# Verify and receive amendment guidance on fail (default Phase 2)
syntagmax ai verify .syntagmax/tasks/TASK-IMPACT-REQ-003-SYS-003.md

# Verify and automatically amend the child artifact on fail
syntagmax ai verify .syntagmax/tasks/TASK-IMPACT-REQ-003-SYS-003.md --amend

# With a custom config file
syntagmax -f my-config.toml ai verify tasks/TASK-IMPACT-REQ-001-SYS-001.md
```

#### Important Notes

- **Phase 1 is audit-only (without `--amend`):** The agent evaluates consistency and updates the task file. Without `--amend`, it MUST NOT modify the parent or child artifact files.
- **`--amend` grants write access to the child artifact:** The agent is explicitly instructed to edit the child artifact to resolve discrepancies. Always review changes with `git diff` before committing.
- **Working directory cleanliness:** Running `--amend` on a dirty repository may overwrite pending edits in the child artifact. Ensure your working tree is clean before using `--amend`, or stash uncommitted changes first. Syntagmax emits a warning if the repository is dirty.
- **Multi-repo support:** Parent and child artifacts may reside in different repositories. The prompt provides repository paths to the agent.
- **Recovery:** If the agent corrupts the task file, use `git checkout -- <task-file>` to recover. If the child artifact is corrupted during `--amend`, use `git checkout -- <child-file>`.

## Configuration

AI settings are defined in the `[ai]` section of `config.toml`:

```toml
[ai]
agent = "kiro"
persona = "You are a systems engineer reviewing requirements traceability."
# agents_file = "custom-agents.yaml"  # Optional: custom agent registry
```

### Fields

| Field | Default | Description |
|-------|---------|-------------|
| `agent` | `kiro` | Name of the default CLI agent to invoke |
| `persona` | `You are a systems engineer reviewing requirements traceability.` | Persona text injected into AI prompts |
| `agents_file` | (none) | Path to a custom agent registry YAML file (relative to config file directory) |

## Agent Registry

Agent definitions map names to command-line invocation patterns. The built-in registry supports these agents:

| Name | Command Pattern | Description |
|------|----------------|-------------|
| `kiro` | `kiro-cli chat --trust-all-tools --no-interactive {prompt}` | Kiro CLI agent |
| `claude` | `claude --dangerously-skip-permissions --print {prompt}` | Claude Code CLI |
| `codex` | `codex --prompt {prompt}` | OpenAI Codex CLI |
| `copilot` | `copilot {prompt}` | GitHub Copilot CLI |
| `opencode` | `opencode --prompt {prompt}` | OpenCode CLI |
| `antigravity` | `antigravity --prompt {prompt}` | Antigravity CLI |
| `mistral-vibe` | `vibe --prompt {prompt}` | Mistral Vibe CLI |

> ⚠️ **Mistral Vibe caveat:** The `--yolo` flag used internally enables auto-commit behaviour — Mistral Vibe may commit changes to the repository without explicit user request. Always inspect `git log` and `git diff` after invocation and use `git reset HEAD~1` to undo unwanted commits.

### Windows Support

On Windows, many agent CLIs are distributed as `.cmd` or `.ps1` wrappers (e.g. `kiro-cli.cmd`). Syntagmax uses `shutil.which()` to resolve the full executable path at runtime, which automatically handles platform-specific extensions. No additional configuration is needed — if the agent executable is on `PATH`, it will be found regardless of wrapper extension.

Custom agent registries may still declare a bare command name (e.g. `kiro-cli`) and rely on this automatic resolution.

### Custom Agent Registry

To add or override agents, create a YAML file and reference it in config:

```toml
[ai]
agents_file = "my-agents.yaml"
```

The YAML format:

```yaml
agents:
  my-agent:
    command: "my-agent-cli --task {prompt}"
    description: "My custom agent"
```

### How It Works

The `{prompt}` placeholder in the command pattern is replaced with the path to a temporary `.md` file containing the rendered prompt. The agent reads the file, performs its work, and exits. The temp file is cleaned up after the agent finishes.

### Agent Requirements

Agents must:
1. Be installed and available on `PATH`.
2. Support one-shot non-interactive mode (receive a task prompt, execute, and exit).
3. Be able to read and edit files in the working directory.
4. Understand git operations for inspecting change history.

Authentication is the user's responsibility — Syntagmax does not manage agent credentials.

## Prompt Template

The verification prompt is rendered from a Jinja2 template bundled with Syntagmax (`ai-verify-impact.j2`). It provides the agent with:

- The persona context
- Task file path
- Parent artifact metadata (ID, type, file path, repository, revision)
- Child artifact metadata (ID, type, file path, repository)
- Instructions for assessment and file editing
- Format requirements for the verification report
- Constraints (audit-only, no artifact modification)

### Artifact Path Resolution

For each artifact (parent and child), the prompt includes three path fields:

| Field | Example | Description |
|-------|---------|-------------|
| File | `/home/user/project/SYS/SYS-003.md` | Absolute path to the artifact file |
| Relative Path (in repo) | `SYS/SYS-003.md` | File path relative to the git repository root (always forward slashes) |
| Repository | `/home/user/project` | Absolute path to the git repository working tree root |

Path resolution uses the task file's **Input Record** field to look up the corresponding input record from the project configuration. The record's `record_base` directory is used to identify the owning git repository, providing precise path information without generic filesystem traversal.

If the Input Record field is missing (e.g., legacy task files) or the record name is not found in the current config, resolution falls back to discovering the git repository by walking up from the artifact file path.

This explicit path information allows agents to immediately locate and open artifact files without searching.

### Verification Report Format

The agent must append this section to the task file:

```markdown
## Verification Report
- **Verdict:** PASS | FAIL
- **Agent:** <agent_name>
- **Date:** <YYYY-MM-DD>
- **Parent revision observed:** <short hash> (dirty: yes/no)
- **Child revision observed:** <short hash> (dirty: yes/no)

### Parent Changes
<Bullet list of distinct parent changes since recorded revision.>

### Child Changes
<Bullet list of child changes, or "No changes observed.">

### Change Mapping
<Numbered list mapping each parent change to its child response or explaining why no change is needed.>

### Rationale
<2-5 sentence summary referencing the change mapping to justify the verdict.>
```

#### Subsection Descriptions

- **Verdict:** Final assessment — `PASS` if the child artifact remains consistent with the updated parent, `FAIL` if discrepancies exist that require action.
- **Agent / Date:** Identifies which agent performed the verification and when, providing an audit trail.
- **Parent/Child revision observed:** Records the exact commit hashes inspected and whether the working tree was dirty, ensuring reproducibility.
- **Parent Changes:** Enumerates the distinct semantic changes in the parent artifact since the revision recorded in the task file. This establishes what the child must respond to.
- **Child Changes:** Lists any changes already made to the child artifact. If the child was updated to reflect the parent changes, those updates appear here.
- **Change Mapping:** Explicitly maps each parent change to its corresponding child response (or justifies why no child change is needed). This is the core traceability evidence.
- **Rationale:** A concise summary that references the change mapping to justify the verdict. Keeps the decision auditable without requiring the reader to re-derive the logic.

The following subsections are appended conditionally after the base report:

- **`### Amendment Recommendation`** — appended on FAIL when `--amend` is **not** set. Contains a bulleted list of specific, actionable edits to make to the child artifact to bring it into consistency. The child artifact is not touched.
- **`### Amendment Applied`** — appended on FAIL when `--amend` **is** set and the agent successfully amended the child. Contains a bulleted list of the changes made, each referencing the discrepancy it resolves.
- **`### Rationale`** — appended (in place of the amendment subsection) when the agent is **uncertain** how to proceed. The agent leaves `status: open` and the child untouched, and explains specifically what is ambiguous and what information would be needed to proceed.
