# Task 5: Refactor impact step to return data

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modify `perform_impact_analysis()` to return `impact_data` without rendering. Remove all rendering functions and template dependencies from `impact.py`.

**Spec:** `docs/specs/united-report.spec.md`

**Depends on:** Task 3 (config cleanup)

---

### Step 1: Modify `src/syntagmax/impact.py`

- [ ] **Remove rendering logic**

Remove:
- `_render_impact_report` function
- `_print_impact_console` function
- `_publish_impact_report` function
- `_load_catalog` and `_make_gettext` helper functions
- Imports: `rich`, `babel`, `jinja2`, `Path` (if no longer needed)

Keep:
- `perform_impact_analysis` — the core logic that builds `impact_data`
- `_generate_suspicious_tree` — still needed to build the tree string for the report

- [ ] **Remove the `_render_impact_report(impact_data, config)` call** at the end of `perform_impact_analysis`

The function already returns `impact_data`, so the signature stays the same.

---

### Step 2: Delete `src/syntagmax/resources/impact.j2`

- [ ] **Delete the file** — content is now in `report.j2`.

---

### Step 3: Verify

- [ ] **Run:** `uv run pytest tests/test_impact.py -v`
- [ ] **Run:** `uv run pytest -v`
