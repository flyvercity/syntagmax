# Task 9: Update documentation and example config

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update README.md and example config to reflect the unified report, `--output` flag, and removal of per-section output options.

**Spec:** `docs/specs/united-report.spec.md`

**Depends on:** Tasks 1–8

---

### Step 1: Update `example/obsidian-driver/.syntagmax/config.toml`

- [ ] **Remove deprecated output fields**

Remove from `[metrics]`:
- `output_format = "markdown"`
- `output_file = "output/metrics.md"`

Remove from `[impact]`:
- `output_format = "markdown"`
- `output_file = "output/impact.md"`

Resulting config should look like:
```toml
[metrics]
enabled = true
requirement_type = "REQ"
status_field = "status"
verify_field = "verify"
tbd_marker = "TBD"

[impact]
enabled = true
```

---

### Step 2: Update `README.md`

- [ ] **Update CLI options section** — replace `--error-output` with `--output`, document default path (`.syntagmax/reports/report.md`) and `console` option.

- [ ] **Remove per-section output config documentation** — remove `output_format`, `output_file`, `template`, `locale` rows from the `[metrics]` and `[impact]` tables.

- [ ] **Add a "Report Output" section** explaining:
  - All analysis outputs are combined into a single Markdown report
  - Default location: `.syntagmax/reports/report.md`
  - `--output console` prints to stdout
  - `--render-tree` includes the artifact tree in the report
  - Section order: Errors → Tree → Metrics → Impact → AI

- [ ] **Update the example config** shown in the README to remove output fields.

---

### Step 3: Verify

- [ ] **Run:** `uv run syntagmax --render-tree --cwd ./example/obsidian-driver analyze`
  - Confirm end-to-end still works after config changes
- [ ] Review README reads correctly
