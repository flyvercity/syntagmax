# Code Review: `more-agents`

- **Date**: 2026-08-07
- **Target Branch**: `main`
- **Files Changed**: 3 (`docs/reference/ai.md`, `src/syntagmax/cli_ai.py`, `src/syntagmax/resources/agents.yaml`)

---

## 1. Architectural & Design Overview

This PR enhances Syntagmax's AI integration layer by:
1. Adding an ad-hoc `--command <pattern>` flag to `syntagmax ai verify`, enabling users to execute arbitrary AI agent commands containing `{prompt}` without modifying configuration or registry YAML files.
2. Expanding the built-in AI agent registry (`agents.yaml`) with support for 7 additional AI coding agents (`crush`, `pi`, `kimi`, `aider`, `cline`, `grok`, `hermes`).
3. Updating documentation in `docs/reference/ai.md` to reflect CLI and agent registry updates.

The overall architectural design is clean and adheres to existing patterns:
- `--command` bypasses the agent registry lookup and constructs a temporary `agent_config` dictionary inline.
- Command pattern validation enforces presence of the `{prompt}` placeholder to prevent silent failures during prompt injection.
- `--agent` and `--command` flags are correctly marked as mutually exclusive.

---

## 2. Security & Performance Audit

- **Security Concerns**:
  - Command pattern formatting (`command_pattern.format(prompt=prompt_path)`) injects the path to a temporary markdown file into shell commands.
  - In `agents.yaml`, `cline` uses `'Execute {prompt}'`. If the temp path contains single quotes, this could cause shell escaping issues.
  - Agent CLI execution continues to run with un-sandboxed user permissions (inherent to CLI agent integrations; properly documented in `ai.md`).
- **Performance & Scalability**:
  - No performance regression. In fact, using `--command` slightly speeds up execution by skipping YAML registry loading (`load_agent_registry`).

---

## 3. Detailed File-by-File Findings

### [`docs/reference/ai.md`](file:///C:/Users/boris/projects/flyvercity/stmx-ws/stmx/syntagmax/docs/reference/ai.md)

- **[Severity: Medium]** Lines 123-134: Missing newly added agents in reference table.
  - **Context**: `agents.yaml` added `kimi`, `aider`, `cline`, `grok`, and `hermes`, but these 5 agents are absent from the Agent Registry table in `ai.md`.
  - **Suggested Fix**:
    ```suggestion
    | `crush` | `crush run {prompt}` | Charm Crush |
    | `pi` | `pi --print {prompt}` | PI Coding Agent |
    | `kimi` | `kimi --prompt {prompt}` | Kimi Code |
    | `aider` | `aider --no-auto-commits --yes-always --message-file {prompt}` | Aider |
    | `cline` | `cline 'Execute {prompt}'` | Cline CLI |
    | `grok` | `grok --always-approve --single {prompt}` | Grok Build |
    | `hermes` | `hermes --yolo --oneshot {prompt}` | Hermes CLI |
    ```

- **[Severity: Medium]** Lines 133, 135-137: Outdated `pi` agent caveat in documentation.
  - **Context**: `ai.md` lists `pi` command as `pi --print` (without `{prompt}`) and contains a warning block about `pi` lacking `{prompt}`. However, `agents.yaml` updated `pi` command to `pi --print {prompt}`, making this caveat obsolete and inaccurate.
  - **Suggested Fix**:
    Update table row for `pi` to `pi --print {prompt}` and remove or update the obsolete warning callout box.

### [`src/syntagmax/resources/agents.yaml`](file:///C:/Users/boris/projects/flyvercity/stmx-ws/stmx/syntagmax/src/syntagmax/resources/agents.yaml)

- **[Severity: Low]** Line 55: Double space in command string for `grok`.
  - **Context**: `command: "grok  --always-approve --single {prompt}"` contains an accidental extra space between `grok` and `--always-approve`.
  - **Suggested Fix**:
    ```suggestion
      grok:
        command: "grok --always-approve --single {prompt}"
        description: "Grok Build"
    ```

### [`src/syntagmax/cli_ai.py`](file:///C:/Users/boris/projects/flyvercity/stmx-ws/stmx/syntagmax/src/syntagmax/cli_ai.py)

- **[Severity: Low]** Code logic is sound and robust. Mutual exclusivity and `{prompt}` validation are properly handled.

---

## 4. Test Coverage & Edge Cases

- **Missing Tests**:
  - `tests/test_cli_ai.py` lacks unit tests covering the new `--command` option:
    1. `--command` with valid pattern (e.g. `echo {prompt}`) verifies execution bypassing registry.
    2. `--command` without `{prompt}` raises error and exits with code 1.
    3. `--agent` combined with `--command` raises mutual exclusivity error and exits with code 1.

---

## 5. Actionable Next Steps

- [x] **Task 1 (High Priority)**: Update `docs/reference/ai.md` to include all 7 new agents (`crush`, `pi`, `kimi`, `aider`, `cline`, `grok`, `hermes`) and remove the outdated `pi` caveat.
- [x] **Task 2 (Medium Priority)**: Add unit tests in `tests/test_cli_ai.py` for `--command` flag validation and mutual exclusivity with `--agent`.
- [x] **Task 3 (Low Priority)**: Fix double space typo in `src/syntagmax/resources/agents.yaml` under `grok`.
