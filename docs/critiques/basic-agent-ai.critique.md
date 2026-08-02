# Spec Critique: AI Agent Commands — Phase 1: Impact Task Verification

## Executive Summary

The specification `docs/specs/basic-agent-ai.spec.md` presents a well-structured design for integrating local CLI AI coding agents into Syntagmax to automate impact task verification. The architecture is modular, cleanly separating configuration (`AiConfig`), agent registry loading (`agents.yaml`), prompt templating (`Jinja2`), interactive execution, and post-edit validation.

However, the review identified **4 Must-Address (🎯)** issues and **5 Recommendations (💡)** spanning both Product and Engineering lenses. Key concerns involve process error handling, temporary file leaks, relative path resolution bugs during repository discovery, ambiguity regarding artifact modification vs task-only reporting, and missing automated test strategies for CLI subprocesses.

Overall Verdict: ⚠️ **PROCEED WITH UPDATES**. The proposed design is sound, and all identified issues can be resolved with targeted spec updates before implementation begins.

---

## Product Lens Findings

### 1a. Problem Validation & Scope
- **P1 (🎯 Must-Address — Scope & Intent Clarity)**: 
  Requirement 1 states that the agent assesses whether a child artifact is consistent with an updated parent. However, the prompt template and task instructions only explicitly direct the agent to update the task file (`task_file_path`) and append a `## Verification Report`. It is ambiguous whether Phase 1 permits or expects the agent to modify the child artifact file itself when inconsistencies are found.
  *Suggestion*: Clarify in Requirement 1 and Prompt Template instructions that in Phase 1, `syntagmax ai verify` is strictly an audit step where the agent only edits the task file's frontmatter and appends the verification report.

### 1b. User Experience & Interaction
- **P2 (💡 Recommendation — Stdin & Interactive Modes)**: 
  The proposed `invoke_agent` code uses `subprocess.run(..., input=stdin_input)` for `prompt_mode == 'stdin'`. Piping `input` closes standard input (EOF), which prevents interactive CLI agents (e.g. `kiro --chat`) from remaining interactive.
  *Suggestion*: Specify that agents using `stdin` prompt mode operate non-interactively, while agents using `file` mode support interactive user terminal sessions.

- **P3 (💡 Recommendation — Workflow & Discovery)**: 
  `syntagmax ai verify <task-file>` requires specifying a single task file path. For users with multiple impact tasks, verifying them one by one may be tedious.
  *Suggestion*: Add a section in Future Work / Scope noting that batch task verification (`syntagmax ai verify-all`) is planned for Phase 2.

- **P4 (🤔 Question — Dirty Repository Safety)**: 
  Requirement 6 states that if the repository is dirty, a warning is emitted but execution proceeds. If an agent fails midway or leaves uncommitted edits, users might find it difficult to untangle pre-existing uncommitted changes from agent output.
  *Suggestion*: Add a recommendation for a `--force` flag or explicit CLI prompt if the working directory is dirty.

---

## Engineering Lens Findings

### 2a. Architecture & Robustness
- **E1 (🎯 Must-Address — Command Execution & Error Handling)**: 
  The `invoke_agent` sketch uses `agent_config['command'].split()`, which breaks if arguments contain quoted strings or spaces. Additionally, missing agent binaries (`FileNotFoundError`) or non-zero exit codes (e.g., agent crash or user cancellation via Ctrl+C) are not explicitly caught, allowing post-edit validation to run on incomplete edits.
  *Suggestion*: Use `shlex.split()` for command parsing. Catch `FileNotFoundError` and check `result.returncode != 0`. If execution fails, abort immediately with a `FatalError` and skip post-edit validation.

- **E2 (🎯 Must-Address — Resource Management)**: 
  `invoke_agent` creates a temporary file with `delete=False` when `prompt_mode == 'file'`, but does not wrap `subprocess.run` in a `try...finally` block. If subprocess execution raises an exception, the temporary file is leaked on disk.
  *Suggestion*: Use a `try...finally` block or context manager around temp file deletion (`Path(prompt_path).unlink(missing_ok=True)`).

### 2b. Integration & Path Resolution
- **E3 (🎯 Must-Address — Relative Path Resolution Bug)**: 
  Task 7 states: "Resolve repository root for parent and child file paths using `git.Repo(path, search_parent_directories=True)`." The `File:` fields in task markdown are relative paths (e.g. `SYS/SYS-003.md`). Passing a relative path directly to `git.Repo()` without resolving it relative to the workspace root (`config.root_dir`) will fail if `cwd` is different or relative paths don't exist under current working directory.
  *Suggestion*: Explicitly require resolving relative artifact file paths to absolute paths using `(config.root_dir / file_path).resolve()` before instantiating `git.Repo()`.

### 2c. Security & Compatibility
- **E4 (💡 Recommendation — Command-Line Argument Limits & Exposure)**: 
  `agents.yaml` defines `prompt_mode: "arg"` for `codex` and `copilot`. Prompts containing full persona, task metadata, and guidelines can exceed Windows command line length limits (8191 chars) and expose prompt text in system process listings.
  *Suggestion*: Recommend `prompt_mode: "file"` or `"stdin"` as preferred defaults for all agents, noting `arg` mode length limitations in `agents.yaml` documentation.

### 2d. Testing Strategy
- **E5 (💡 Recommendation — Automated Subprocess Testing)**: 
  Tasks 4 and 6 only list manual integration testing against real agents. CI/CD test suites cannot depend on external CLI agent binaries (`kiro`, `claude`, etc.) being installed.
  *Suggestion*: Add automated unit test requirements in Tasks 4 and 6 using `unittest.mock.patch('subprocess.run')` and dummy mock executables.

### 2e. Packaging & Resource Distribution
- **E6 (💡 Recommendation — Resource Inclusion for Binary Freezes)**: 
  Adding `src/syntagmax/resources/` requires ensuring non-python `.yaml` and `.j2` files are packaged properly for wheels and binary freezes (`cx_freeze`).
  *Suggestion*: Add `src/syntagmax/resources/__init__.py` so package resources can be loaded via `importlib.resources.files('syntagmax.resources')`.

---

## Cross-Lens Insights

- **X1 (🎯 Must-Address — Execution Safety & UX Convergence)**: 
  Robust subprocess error handling (E1) directly affects User Experience (P2). Halting validation and returning clean error messages when an agent fails or is canceled prevents user confusion and avoids validating broken or half-edited task files.
- **X2 (💡 Recommendation — Explicit Artifact Scope & Path Handling)**: 
  Resolving artifact relative paths against workspace root (E3) and defining clear audit boundaries (P1) ensures predictable behavior across multi-repository setups.

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| P1 | Product | 🎯 | Scope & Intent | Ambiguous whether child artifact can be modified | Clarify Phase 1 is strictly audit mode (only task file updated) |
| E1 | Engineering | 🎯 | Execution Safety | `split()` breaks quoted args; missing error handling for non-zero exit/missing binary | Use `shlex.split()`, check returncode, catch `FileNotFoundError`, abort before validation |
| E2 | Engineering | 🎯 | Failure Modes | Temp file leak if `subprocess.run` fails | Wrap temp file cleanup in `try...finally` |
| E3 | Engineering | 🎯 | Integration Risk | `git.Repo()` called on unresolved relative paths | Resolve artifact paths relative to `config.root_dir` first |
| P2 | Product | 💡 | User Experience | `stdin` prompt mode closes stdin, preventing interactive chat | Clarify non-interactive vs interactive agent modes |
| P3 | Product | 💡 | Workflow | Single task verification only | Document batch verification as Phase 2 scope |
| P4 | Product | 🤔 | UX / Safety | Warning on dirty repo could lead to mixed uncommitted changes | Note dirty repo risks in user guidance |
| E4 | Engineering | 💡 | Security | `prompt_mode: arg` risks process exposure and CLI length limits | Prefer `file` or `stdin` modes |
| E5 | Engineering | 💡 | Testing | No automated tests for agent subprocess invocation | Add mock subprocess test cases to Task 4 and 6 |
| E6 | Engineering | 💡 | Packaging | Package resource directory needs `__init__.py` for `cx_freeze` | Add `src/syntagmax/resources/__init__.py` |

---

## Verdict

⚠️ **PROCEED WITH UPDATES**

The specification is well-conceived and close to ready. Updating the spec to address the 4 Must-Address findings (P1, E1, E2, E3) and incorporating key recommendations will ensure robust execution and seamless implementation.

---

## Remediation Plan & Suggested Spec Edits

Below are specific proposed edits to `docs/specs/basic-agent-ai.spec.md`:

### 1. Spec Edit for P1 (Child Artifact Modification Scope)
Update Requirement 1 and Prompt Template Constraints:
```diff
- 1. A new `syntagmax ai verify <task-file>` command invokes a configured CLI agent to assess whether an impact task's child artifact is consistent with its updated parent.
+ 1. A new `syntagmax ai verify <task-file>` command invokes a configured CLI agent to assess whether an impact task's child artifact is consistent with its updated parent. In Phase 1, verification is an audit operation: the agent evaluates consistency, updates task `status` (to `closed` if consistent or `open` if not), and appends a verification report. The agent MUST NOT modify the child artifact file.
```

### 2. Spec Edit for E1 & E2 (Process Invocation & Temp File Cleanup)
Update Section "Invocation Logic" and Task 4 implementation guidance:
```diff
 def invoke_agent(agent_config: dict, prompt: str, working_dir: Path) -> int:
     """Invoke the agent interactively, returning exit code."""
     import subprocess
     import tempfile
+    import shlex
+    import os
 
-    cmd_parts = agent_config['command'].split()
+    cmd_parts = shlex.split(agent_config['command'])
     prompt_flag = agent_config.get('prompt_flag', '')
     prompt_mode = agent_config.get('prompt_mode', 'file')
 
+    prompt_path = None
+    try:
         if prompt_mode == 'file':
             with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
                 f.write(prompt)
                 prompt_path = f.name
             if prompt_flag:
                 cmd_parts += [prompt_flag, prompt_path]
             else:
                 cmd_parts.append(prompt_path)
             stdin_input = None
         elif prompt_mode == 'stdin':
             if prompt_flag:
                 cmd_parts.append(prompt_flag)
             stdin_input = prompt
         elif prompt_mode == 'arg':
             if prompt_flag:
                 cmd_parts += [prompt_flag, prompt]
             else:
                 cmd_parts.append(prompt)
             stdin_input = None
 
         result = subprocess.run(
             cmd_parts,
             cwd=working_dir,
             stdin=subprocess.PIPE if stdin_input else None,
             input=stdin_input,
             encoding='utf-8' if stdin_input else None,
         )
         return result.returncode
+    except FileNotFoundError:
+        raise FatalError(f"Agent executable '{cmd_parts[0]}' not found on PATH.")
+    finally:
+        if prompt_path and os.path.exists(prompt_path):
+            os.unlink(prompt_path)
```

### 3. Spec Edit for E3 (Relative Path Resolution)
Update Task 7 implementation guidance:
```diff
- Resolve repository root for parent and child file paths using `git.Repo(path, search_parent_directories=True)`.
+ Resolve parent and child file paths to absolute paths relative to `config.root_dir` (e.g. `abs_path = (config.root_dir / file_path).resolve()`), then discover their repository roots using `git.Repo(abs_path, search_parent_directories=True)`.
```

### 4. Spec Edit for E5 (Automated Test Strategy)
Update Task 4 Test Requirements:
```diff
 **Test requirements:**
 - Unit test: command construction for each `prompt_mode`.
+- Unit test: mock `subprocess.run` returning exit code 0 and non-zero exit code.
+- Unit test: handles missing executable `FileNotFoundError` gracefully.
 - Integration test (manual): invoke a real agent against example task.
```

---

Would you like me to apply these changes to `docs/specs/basic-agent-ai.spec.md`? (all / select / none)
