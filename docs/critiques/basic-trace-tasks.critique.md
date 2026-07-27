# Critique: Task Subsystem — Phase I: Tasks from Impact Analysis

## Executive Summary

The specification [basic-trace-tasks.spec.md](../specs/basic-trace-tasks.spec.md) outlines a very valuable feature: automatically generating actionable, git-friendly task files to verify and resolve parent-child artifact discrepancies identified during impact analysis.

Following clarification on the design direction, task files will use a simpler, flat YAML frontmatter format (e.g., without `attrs:` nesting) suitable for a future `simple-markdown` driver rather than the existing `obsidian` driver.

However, several high-priority **Must-Address** gaps remain:
1. **Implicit Metamodel Registration**: The implicit TASK metamodel is defined in a helper file but not registered with the main configuration, leading to validation errors ("Unknown artifact type 'TASK'") during regular validation runs.
2. **Idempotency & Stale State Issues**: The task de-duplication/overwrite logic does not check if parent or child revisions have changed, resulting in infinite task regeneration loops for closed tasks and stale revision metadata in open tasks.
3. **CLI/Pipeline Execution Mismatch**: The task generation step is not automatically run when the user executes the `analyze impact` step in the CLI.
4. **Custom Template Loading**: The hardcoded template loading logic does not respect the configured `tasks_template` path.

With the updates suggested below, the specification will be robust, correct, and ready for implementation.

---

## Product Lens Findings

### 1b. User Value & State Management (Severity: 🎯 Must-Address)
* **Finding (P1 - Infinite Loops and Stale Task Files):** The proposed de-duplication logic only checks `status` (`open` or `closed`). 
  1. If a user sets `status: closed` on a task but the child artifact has not yet been updated (so it remains suspicious), the next run of `analyze impact` will see that the task is `closed` and will regenerate/overwrite it back to `status: open`. This makes it impossible to resolve/ignore tasks without changing the child reference.
  2. If a task is `status: open` but the parent has been updated *again* (new commit/revision), the next run will *skip* generation because the task is still open, leaving the revision details in the task file stale and outdated.
* **Suggestion:** Store the parent and child revision hashes in the task frontmatter. Modify the generation criteria to check these hashes: if they differ from the current state, regenerate the task file (to update details, keeping the status `open`); if they match and status is `closed`, skip regeneration.

### 1d. Edge Cases & UX (Severity: 💡 Recommendation)
* **Finding (P2 - Safe Filenames for Special Artifact IDs):** Task files are named `TASK-IMPACT-{child_aid}-{parent_aid}.md`. Artifact IDs (`aid`) can contain spaces, slashes, or other filesystem-unsafe characters. In such cases, writing the file will fail with an `OSError` or write to unintended subdirectories.
* **Suggestion:** Sanitize the generated filenames by replacing filesystem-unsafe characters (like `/`, `\`, `:`, `*`, `?`, `"`, `<`, `>`, `|`) with hyphens.

---

## Engineering Lens Findings

### 2a. Architecture Soundness (Severity: 💡 Recommendation / Question)
* **Finding (E1 - Flat YAML Frontmatter & Driver Compatibility):** The flat frontmatter structure (e.g., `id: TASK-...` directly at the root) is incompatible with the current `obsidian` driver, which expects attributes to be nested under `attrs`. While this flat format is intended for future parsing via a new `simple-markdown` driver, configuring the tasks directory under the `obsidian` driver in `config.toml` will trigger extraction errors.
* **Suggestion:** Explicitly document in the specification that the task files use a flat frontmatter format and are designed to be parsed by the future `simple-markdown` driver, and warn against parsing them with the `obsidian` driver.

### 2a. Architecture Soundness (Severity: 🎯 Must-Address)
* **Finding (E2 - Implicit Metamodel Validation Failure):** Task 4 defines an implicit TASK metamodel in `tasks.py` but does not register it with `config.metamodel`. When the user runs the `tree` step (which runs the `ArtifactValidator`), any generated task file (being a standard markdown artifact of type `TASK`) will trigger an `Unknown artifact type: 'TASK'` error because it is missing from the global metamodel definition.
* **Suggestion:** Inject the implicit `TASK` (or the customized mapped atype) metamodel definition dynamically during configuration/metamodel loading in `config.py` so that all validation tools recognize it.

### 2b. Failure Mode & Configurations (Severity: 🎯 Must-Address)
* **Finding (E3 - Hardcoded Jinja2 Template):** Task 2 hardcodes `template = template_env.get_template('task.j2')`. This ignores the custom `tasks_template` field defined in `ImpactConfig`, preventing users from using a custom task template.
* **Suggestion:** Configure the Jinja2 Environment loader as a `ChoiceLoader` (incorporating both the project config directory and the package resources directory) and load the template dynamically using `config.impact.tasks_template` if provided, falling back to `'task.j2'`.

### 2g. Dependencies & Integration (Severity: 🎯 Must-Address)
* **Finding (E4 - Pipeline/CLI execution gap):** Requirement 1 states that task generation triggers automatically at the end of `analyze impact` if `tasks_enabled = true`. However, Task 5 only adds a `case 'tasks'` in the `process` function's match block. The CLI execution plan for `analyze impact` will execute only up to `impact` and stop, never running the `tasks` step.
* **Suggestion:** Update the pipeline controller `process` in [main.py](../../src/syntagmax/main.py) to automatically run `tasks` or append it to the execution plan if the requested step is `impact` and `tasks_enabled` is set to `true`.

### 2g. Dependencies & Integration (Severity: 💡 Recommendation)
* **Finding (E5 - Pydantic default_factory in TOML Generator):** Task 1 defines `task_atype_map: dict[str, str] = Field(default_factory=dict)`. In Pydantic v2, fields with `default_factory` have a default value of `PydanticUndefined`. The config generation logic in [init_cmd.py](../../src/syntagmax/init_cmd.py) does not handle this, which will write `# task_atype_map = PydanticUndefined` into the generated `config.toml`, producing a broken TOML template.
* **Suggestion:** Update `init_cmd.py` to check for `default_factory` fields or dict types and print them cleanly as `# task_atype_map = {}` or similar.

---

## Cross-Lens Insights

* **X1: Revision-Tracking for State Management (🎯 Must-Address):** Storing parent/child revision hashes in the flat frontmatter avoids infinite loop bugs (Product UX) and allows the system to remain stateless and git-independent when resolving de-duplication (Engineering robustness).

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| **P1** | Product | 🎯 | State Management | Flat state checking causes infinite overwrite loops or stale data. | Track parent and child revision hashes in frontmatter. |
| **P2** | Product | 💡 | Edge Cases | Unsafe chars in task filenames can cause filesystem write errors. | Sanitize task filenames before writing. |
| **E1** | Engineering | 💡 | Integration | Flat YAML format is incompatible with the current `obsidian` driver. | Document the future `simple-markdown` driver and task format choice. |
| **E2** | Engineering | 🎯 | Architecture | Missing TASK metamodel definition in validator causes validation errors. | Dynamically inject TASK metamodel during config loading. |
| **E3** | Engineering | 🎯 | Configuration | Custom template configuration is ignored due to hardcoded template name. | Use `ChoiceLoader` and dynamically load configured template path. |
| **E4** | Engineering | 🎯 | Integration | CLI `analyze impact` will not automatically trigger task generation. | Append `tasks` step to execution plan when `tasks_enabled` is true. |
| **E5** | Engineering | 💡 | Integration | Pydantic default_factory maps to `PydanticUndefined` in TOML generator. | Format dictionary and default_factory fields safely in `init_cmd.py`. |

---

## Verdict

### ⚠️ PROCEED WITH UPDATES

*The proposed updates resolve critical architectural and usability flaws in the task subsystem design. Proceeding to implementation is recommended once these edits are applied.*

---

## Offer Remediation

### Proposed Edits to `docs/specs/basic-trace-tasks.spec.md`

#### Edit 1: Requirements (State Tracking, Driver Intent, and CLI Execution)

```diff
-1. Task generation triggers automatically at the end of `analyze impact` when `tasks_enabled = true` in `[impact]` config.
+1. Task generation triggers automatically at the end of `analyze impact` when `tasks_enabled = true` in `[impact]` config. This is achieved by dynamically appending the `tasks` step to the execution plan if `tasks_enabled` is set.
-3. Status-aware de-duplication: if an existing task file for that pair has `status: open`, skip; if `status: closed`, create a new one.
+3. Status-aware and revision-aware de-duplication: task generation tracks the parent and child revision hashes in frontmatter. A task is regenerated only if the parent or child revision has changed (updating details, preserving `status: open`), or if no task file exists. If revisions match, regeneration is skipped.
-4. Task files are markdown with YAML frontmatter containing mandatory attributes (`id`, `contents`, `status`).
+4. Task files are markdown with flat YAML frontmatter containing attributes (`id`, `contents`, `status`, `parent_revision`, `child_revision`). These files are designed for a future `simple-markdown` driver and must not be parsed using the `obsidian` driver.
```

#### Edit 2: Configuration & Metamodel Integration (Task 1 & Task 4)

```diff
-180:   def tasks_dir(self) -> Path:
-181:       return Path(self._root_dir, self.impact.tasks_dir)
+180:   def tasks_dir(self) -> Path:
+181:       return Path(self._root_dir, self.impact.tasks_dir)
+
+   Additionally, when the metamodel is loaded in `src/syntagmax/config.py` (or `src/syntagmax/metamodel.py`), dynamically inject the implicit `TASK` metamodel definition (or the custom resolved task `atype`) if not explicitly defined by the user:
+   ```python
+   if 'TASK' not in self.metamodel['artifacts']:
+       self.metamodel['artifacts']['TASK'] = IMPLICIT_TASK_METAMODEL
+   ```
```

#### Edit 3: Task Frontmatter & Template Structure (Task 2)

```diff
-228:   ---
-229:   id: {{ task.task_id }}
-230:   status: open
-231:   contents: "Verify {{ task.child_aid }} is updated after {{ task.parent_aid }} change"
-232:   ---
+228:   ---
+229:   id: {{ task.task_id }}
+230:   status: open
+231:   contents: "Verify {{ task.child_aid }} is updated after {{ task.parent_aid }} change"
+232:   parent_revision: "{{ task.parent_revision_short or '' }}"
+233:   child_revision: "{{ task.child_revision_short or '' }}"
+234:   ---
```

#### Edit 4: De-duplication Logic & Frontmatter Parsing (Task 3)

```diff
-270:   def scan_existing_tasks(tasks_dir: Path) -> dict[str, str]:
+270:   def scan_existing_tasks(tasks_dir: Path) -> dict[str, dict]:
-271:       """Scan task files and return {task_id: status} mapping."""
+271:       """Scan task files and return {task_id: {'status': status, 'parent_revision': ..., 'child_revision': ...}} mapping."""
-277:           frontmatter = _parse_frontmatter(content)
-278:           if frontmatter and 'id' in frontmatter:
-279:               status = frontmatter.get('status', 'open')
-280:               existing[frontmatter['id']] = status
+277:           frontmatter = _parse_frontmatter(content)
+278:           if frontmatter and 'id' in frontmatter:
+279:               existing[frontmatter['id']] = {
+280:                   'status': frontmatter.get('status', 'open'),
+281:                   'parent_revision': frontmatter.get('parent_revision', ''),
+282:                   'child_revision': frontmatter.get('child_revision', '')
+283:               }
```

```diff
-283:   def should_generate_task(task_id: str, existing_tasks: dict[str, str]) -> bool:
-284:       if task_id not in existing_tasks:
-285:           return True
-286:       return existing_tasks[task_id] == 'closed'
+283:   def should_generate_task(task_id: str, current_parent_rev: str, current_child_rev: str, existing_tasks: dict[str, dict]) -> bool:
+284:       if task_id not in existing_tasks:
+285:           return True
+286:       task_info = existing_tasks[task_id]
+287:       # If parent or child revision has changed, we must regenerate (updates details, retains open status)
+288:       if task_info.get('parent_revision') != current_parent_rev or task_info.get('child_revision') != current_child_rev:
+289:           return True
+290:       # Revisions match, so skip regeneration
+291:       return False
```

#### Edit 5: CLI execution plan adjustment (Task 5)

```diff
- In `src/syntagmax/main.py`:
-   - Add `'tasks'` to `STEPS` and `DEPS` (`{'impact'}`)
+ In `src/syntagmax/main.py`:
+   - Add `'tasks'` to `STEPS` and `DEPS` (`{'impact'}`)
+   - In `process`, dynamically append `'tasks'` to the execution plan if `'impact'` is executed and `config.impact.tasks_enabled` is true:
+     ```python
+     plan = get_execution_plan(DEPS, requested_step)
+     if 'impact' in plan and config.impact.tasks_enabled and 'tasks' not in plan:
+         plan.append('tasks')
+     ```
```
