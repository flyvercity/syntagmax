# Code Review: [ai-with-agents]
- **Date**: 2026-08-03
- **Target Branch**: `main`
- **Files Changed**: 23

## 1. Architectural & Design Overview
This pull request refactors the AI capability in Syntagmax from direct API provider calls (OpenAI, Anthropic, Gemini, Ollama, Bedrock) to an agent-delegation model using CLI tools (`kiro`, `claude`, `codex`, `copilot`, `opencode`, `antigravity`, `mistral-vibe`).

Key architectural changes include:
- Removal of direct HTTP/SDK provider implementations (`ai_providers.py`) and legacy provider unit tests (`test_ai_providers.py`).
- Introduction of an agent registry (`agents.yaml`) and CLI command `rms ai verify <task_file>` (`cli_ai.py`).
- Prompt rendering with Jinja2 (`ai-verify-impact.j2`) and automated post-edit validation of task markdown frontmatter (`validate_task_post_edit`).

The architecture is significantly simpler and decouples Syntagmax from LLM vendor API key management, delegating execution to local CLI agents.

## 2. Security & Performance Audit
- **Security Concerns**: 
  - Subprocess execution: `invoke_agent` constructs command strings using `shlex.split(command_str)`. The command string includes a temporary prompt file path. No raw shell strings are passed to `shell=True`, which mitigates arbitrary command injection risks.
  - Temporary files: Prompts are written to `tempfile.NamedTemporaryFile` with strict file deletion in a `finally:` block.
- **Performance & Scalability**:
  - `rms ai verify` runs synchronously per task file. Execution time depends on the target CLI agent's processing speed.
  - Resource usage is minimal on the Syntagmax side (simple Jinja2 rendering and file parsing).

## 3. Detailed File-by-File Findings

### `src/syntagmax/ai.py`
- **[Severity: High]** Line 230-237: Potential path corruption on Windows during `shlex.split`.
  - **Context**: On Windows, `f.name` produces backslash-delimited paths (e.g. `C:\Users\...\AppData\Local\Temp\tmp...`). `shlex.split` defaults to `posix=True` in Python, which interprets backslashes as escape characters. If the temporary path contains characters like `\t`, `shlex.split` converts it to a literal ASCII tab character, breaking the file path passed to `subprocess.run`.
  - **Suggested Fix**:
    ```suggestion
    prompt_path = Path(f.name).as_posix()
    command_str = command_pattern.replace('{prompt}', prompt_path)
    cmd_parts = shlex.split(command_str, posix=(sys.platform != 'win32'))
    ```

- **[Severity: Low]** Line 94-102: Unhandled `yaml.YAMLError` in `_parse_frontmatter`.
  - **Context**: If a task file contains malformed YAML in its frontmatter, `yaml.safe_load(match.group(1))` will raise a `yaml.YAMLError` exception rather than being caught by `_parse_frontmatter`.
  - **Suggested Fix**:
    ```suggestion
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None
    ```

- **[Severity: Low]** Line 171-180: Strict case-sensitivity in section heading matching.
  - **Context**: `re.search(r'## Parent \(Updated\)...')` and `## Child \(Outdated\)` require exact case and formatting. Minor variations in task templates (e.g. `## parent (updated)`) will fail parsing.
  - **Suggested Fix**: Add `re.IGNORECASE` flag to `re.search`.

### `src/syntagmax/init_cmd.py`
- **[Severity: Medium]** Line 21-31: `generate_toml()` does not render the `[ai]` section properly.
  - **Context**: `init_cmd.py` omits `ai` from the section skip list in line 22, causing `AiConfig` fields to be serialized as an inline string under global config instead of rendering a documented `# [ai]` TOML section.
  - **Suggested Fix**: Exclude `'ai'` from the global loop and append a dedicated `# [ai]` block using `AiConfig.model_fields`.

### `src/syntagmax/resources/agents.yaml`
- **[Severity: Low]** Lines 7-9 & 26-28: Inconsistent `windows-suffix` for CLI agents.
  - **Context**: `claude` and `antigravity` lack `windows-suffix: ".cmd"`, whereas `kiro`, `codex`, `copilot`, and `opencode` include it. On Windows, npm/pip wrappers often produce `.cmd` or `.bat` files.
  - **Suggested Fix**: Consider using `shutil.which()` in `ai.py` to dynamically resolve agent executables across platforms.

## 4. Test Coverage & Edge Cases
- **Missing Tests**:
  - `tests/test_ai_providers.py` was removed, but no replacement test file (`tests/test_ai.py` or `tests/test_cli_ai.py`) was introduced.
  - Scenarios needing unit test coverage:
    1. Parsing valid and invalid task frontmatters in `parse_impact_task`.
    2. Validating task file post-edit status in `validate_task_post_edit`.
    3. Resolving agents from default and custom `agents.yaml` registries.
    4. Mocking `subprocess.run` inside `invoke_agent` for both successful and non-zero exit codes.
    5. CLI execution of `rms ai verify`.

- **Edge Cases to Handle**:
  - Non-existent task file or path with spaces/special characters.
  - Dirty git state handling when running impact verification.

## 5. Actionable Next Steps
- [ ] Task 1 (High Priority): Fix Windows path formatting in `invoke_agent` (`ai.py`) using `as_posix()` and cross-platform `shlex.split`.
- [ ] Task 2 (Medium Priority): Add unit test suite `tests/test_ai.py` to cover `ai.py` functions and `cli_ai.py` commands.
- [ ] Task 3 (Medium Priority): Fix TOML template generation for `[ai]` section in `src/syntagmax/init_cmd.py`.
- [ ] Task 4 (Low Priority): Normalize `windows-suffix` or use `shutil.which` in `agents.yaml` and `ai.py`.
