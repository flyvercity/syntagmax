# Task 2: Refactor Params and CLI flags

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `--error-output` with `--output` (default `.syntagmax/reports/report.md`). Update `Params` TypedDict and all usages.

**Spec:** `docs/specs/united-report.spec.md`

---

### Step 1: Update `src/syntagmax/params.py`

- [ ] **Replace `error_output` with `output`**

```python
class Params(TypedDict):
    verbose: bool
    render_tree: bool
    ai: bool
    cwd: str
    no_git: bool
    allow_dirty_worktree: bool
    suppress_tracing: bool
    output: str
```

---

### Step 2: Update `src/syntagmax/cli.py`

- [ ] **Rename the CLI option and remove the global `_error_output` variable**

In the `@rms` group:
- Remove `_error_output` global variable
- Replace `--error-output` option with `--output` option, default `.syntagmax/reports/report.md`
- Remove the global assignment in `rms()` function body

In `main()`:
- Remove `_write_error_report` function (will be handled by unified report later in Task 8)
- For now, keep `FatalError` handling but reference `'output'` key

---

### Step 3: Update all test files constructing `Params`

- [ ] **Update every test file** that constructs a `Params` dict to use `output` instead of `error_output`

Affected files (grep for `Params(`):
- `tests/test_git_utils.py`
- `tests/test_impact.py`
- `tests/test_hyphen_support.py`
- `tests/test_suspicious_tree_marks.py`
- `tests/test_enum_multiple.py`
- `tests/test_extractors.py`
- `tests/test_independent_atype_marker.py`
- `tests/test_ipynb_extractor.py`
- `tests/test_multiple_attributes_e2e.py`
- `tests/test_multiple_records_same_driver.py`

Add `output='.syntagmax/reports/report.md'` to each `Params(...)` call.

---

### Step 4: Verify

- [ ] **Run:** `uv run pytest -v`
- [ ] **Run:** `uv run syntagmax --help` — confirm `--output` appears, `--error-output` does not
