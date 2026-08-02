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
| `-f, --config-file` | `.syntagmax/config.toml` | Path to config file |

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
7. Reports the outcome.

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

# With a custom config file
syntagmax ai verify tasks/TASK-IMPACT-REQ-001-SYS-001.md -f my-config.toml
```

#### Important Notes

- **Phase 1 is audit-only:** The agent evaluates consistency and updates the task file. It MUST NOT modify the parent or child artifact files.
- **Multi-repo support:** Parent and child artifacts may reside in different repositories. The prompt provides repository paths to the agent.
- **Recovery:** If the agent corrupts the task file, use `git checkout -- <task-file>` to recover.

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

### Windows Support

Some agent CLIs are distributed as `.cmd` or `.ps1` wrappers on Windows. The optional `windows-suffix` property appends a suffix to the executable name when running on Windows:

```yaml
agents:
  kiro:
    command: "kiro-cli chat --trust-all-tools --no-interactive {prompt}"
    description: "Kiro CLI agent"
    windows-suffix: ".cmd"
```

On Windows, the invoked executable becomes `kiro-cli.cmd`. On other platforms the suffix is ignored. The built-in registry already sets `windows-suffix: ".cmd"` for `kiro` and `codex`.

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
    windows-suffix: ".cmd"  # Optional: appended to executable on Windows
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

### Verification Report Format

The agent must append this section to the task file:

```markdown
## Verification Report
- **Verdict:** PASS | FAIL
- **Parent revision observed:** <short hash> (dirty: yes/no)
- **Child revision observed:** <short hash> (dirty: yes/no)
- **Rationale:** <3-10 sentences explaining the assessment>
```
