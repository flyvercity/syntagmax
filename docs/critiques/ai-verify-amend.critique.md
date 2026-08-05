# Critique: Spec `ai verify --amend` — Two-Phase Verification with Amendment

## Executive Summary

The specification `docs/specs/ai-verify-amend.spec.md` introduces a valuable `--amend` capability to `syntagmax ai verify`, transitioning verification from an audit-only operation to an automated remediation workflow. Overall, the architectural design (splitting into Phase 1 Analysis and Phase 2 Recommendation/Implementation via Jinja2 templates) is clean, minimal, and maintains strong backward compatibility.

However, the critique identified key gaps in **post-edit safety/validation** and **CLI user messaging accuracy**. Specifically:
1. The CLI messaging falsely reports "child artifact amended" even when verification passed without needing any amendment.
2. In `--amend` mode, `child_file_path` is edited without post-edit validation, risking silent corruption of project artifacts.
3. The specification explicitly skips CLI unit tests for `--amend` logic, leaving post-run status branch handling untested.

With targeted updates to post-edit validation, CLI status reporting, prompt constraints, and test coverage, this specification is ready for implementation.

---

## Product Lens Findings

### 1a. User Value & Workflow Consistency
- **Feature Impact:** Automated amendment of outdated child artifacts removes manual friction and accelerates impact traceability resolution.
- **Scope Alignment:** Scope is well-bounded; `--amend` is CLI-only and keeps post-edit task validation loose and compatible.

### 1b. Edge Cases & User Experience
- **Misleading Post-Run Status Message (P1 - 🎯 Must-Address):**
  When running `syntagmax ai verify task.md --amend` on a task where Phase 1 verdict is **PASS** (the child is already consistent), no amendment is performed. However, the current proposed implementation prints:
  `✓ Task TASK-123 verified and child artifact amended.`
  This is inaccurate and confusing to users, as the child artifact was never touched.
- **Lack of Post-Amendment Verification Hint (P2 - 💡 Recommendation):**
  When `--amend` modifies a child artifact on disk, users should be clearly instructed to inspect the resulting diff using `git diff <child_file_path>` before committing.
- **Handling Ambiguous Discrepancies (P3 - 🤔 Question):**
  If an agent encounters a discrepancy during Phase 2 that requires human design judgment, how should it proceed? Should it leave `status: open` and apply only safe partial amendments?

---

## Engineering Lens Findings

### 2a. Architecture Soundness & Integrity
- **Unchecked Child Artifact Edits (E1 - 🎯 Must-Address):**
  In `--amend` mode, the AI agent modifies `child_file_path`. Currently, `validate_task_post_edit` only checks `task_file_path`. If the agent truncates `child_file_path`, writes invalid frontmatter, or empties the file, Syntagmax will report success as long as `task_file_path` is valid.
- **Strict Parent Immutability (E3 - 💡 Recommendation):**
  Under `amend=True`, the prompt template removes the "Do NOT modify child artifact" constraint. It is critical that constraints explicitly state that parent artifacts and all other project files remain strictly read-only.

### 2b. Testing Strategy
- **CLI Testing Gap (E2 - 🎯 Must-Address):**
  Task 3 explicitly opts out of CLI unit tests ("No new unit tests for the CLI layer..."). Because `--amend` introduces branching in `cli_ai.py` (option parsing and conditional post-run output), leaving this untested increases regression risk.

### 2c. Operational Readiness
- **Git Dirtiness Awareness (E4 - 💡 Recommendation):**
  Running `--amend` on uncommitted or dirty files may overwrite pending edits in `child_file_path`. Emphasizing workspace cleanliness in documentation and CLI output helps prevent accidental data loss.

---

## Cross-Lens Insights

Both the Product and Engineering lenses converge on **Artifact Integrity and Transparent Feedback**:
- Falsely claiming an amendment occurred when a task passed without changes damages user trust (Product Lens) and obscures actual agent behavior during debugging (Engineering Lens).
- Validating child artifact non-emptiness/integrity post-edit (Engineering Lens) directly prevents data corruption in user codebases (Product Lens).

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| P1 | Product | 🎯 | User Experience | CLI outputs "child artifact amended" on PASS when no amendment occurred | Check for `### Amendment Applied` or verdict before printing "amended" |
| E1 | Engineering | 🎯 | Architecture | `validate_task_post_edit` does not validate `child_file_path` integrity | Validate child file existence, non-emptiness, and basic frontmatter if present |
| E2 | Engineering | 🎯 | Testing | Task 3 omits CLI unit tests for `--amend` options and status output | Add `CliRunner` unit tests covering `--amend` in PASS, FAIL, and error scenarios |
| P2 | Product | 💡 | User Experience | No prompt/output hint guiding users to review `git diff` after amendment | Output `git diff <child_file>` recommendation in CLI success message |
| E3 | Engineering | 💡 | Safety | Potential ambiguity in file modification scope under `amend=True` | Explicitly enforce parent artifact and non-target file immutability in prompt |
| E4 | Engineering | 💡 | Operations | Overwriting dirty child files risks uncommitted data loss | Recommend clean git status in docs and log warning before invocation |
| P3 | Product | 🤔 | Edge Cases | Unclear handling if agent cannot safely perform complete automated amendment | Instruct agent to leave `status: open` and note unresolvable items |

---

## Verdict

### ⚠️ PROCEED WITH UPDATES

The specification concept is sound, well-motivated, and architecturally clean. Addressing the 3 Must-Address items (P1, E1, E2) and incorporating the recommendations will ensure safe, reliable, and user-friendly automated amendments.

---

## Proposed Spec Remediation

### 1. Remediate P1 (CLI Status Messaging)
Update Section **Proposed Solution > CLI Change (`cli_ai.py`)** and **Task 3** in `docs/specs/ai-verify-amend.spec.md`:

```python
# Post-run messaging
if final_status == 'closed':
    if amend and '### Amendment Applied' in final_content:
        u.pprint(f'[green]✓ Task {task_info.task_id} verified and child artifact amended.[/green]')
        u.pprint(f'[dim]Review changes: git diff {child_paths.relative_path}[/dim]')
    else:
        u.pprint(f'[green]✓ Task {task_info.task_id} verified and closed.[/green]')
else:
    u.pprint(f'[yellow]Task {task_info.task_id} requires more work (status: {final_status}).[/yellow]')
```

### 2. Remediate E1 (Child File Post-Edit Validation)
Add a helper function `validate_child_post_edit(child_path: Path) -> tuple[bool, str]` in `src/syntagmax/ai.py`:
- Assert `child_path.exists()` and `child_path.stat().st_size > 0`.
- If child contains YAML frontmatter (`---`), ensure it parses without syntax errors.

Call `validate_child_post_edit` in `cli_ai.py` when `amend=True` before declaring verification complete.

### 3. Remediate E2 (CLI Unit Tests)
Update **Task 3: Test requirements** in `docs/specs/ai-verify-amend.spec.md`:
- Add unit tests using `click.testing.CliRunner` in `tests/test_ai.py` (or `test_cli_ai.py`):
  - Test `syntagmax ai verify task.md --amend` when agent passes without amendment.
  - Test `syntagmax ai verify task.md --amend` when agent fails and amends child artifact.
  - Assert correct stdout status messages and options passing.

### 4. Remediate E3 (Template Immutability Constraints)
Update Section **Proposed Solution > Template Structure > Constraints**:
- Explicitly add constraint: `"Do NOT modify the parent artifact file or any file other than the child artifact and task file."`
