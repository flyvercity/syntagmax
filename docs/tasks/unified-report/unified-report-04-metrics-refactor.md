# Task 4: Refactor metrics step to return data

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modify `calculate_metrics()` to return its data dict instead of rendering output. Remove `publish.py` and `print_metrics` from `render.py`.

**Spec:** `docs/specs/united-report.spec.md`

**Depends on:** Task 3 (config cleanup)

---

### Step 1: Modify `src/syntagmax/metrics.py`

- [ ] **Remove rendering logic, return data**

Remove imports of `print_metrics` and `publish_metrics`. Remove the output format branching at the end. Return `metrics` dict.

```python
def calculate_metrics(config: Config, artifacts: ArtifactMap, errors: list[str]) -> benedict:
    metrics = benedict()
    # ... existing calculation logic unchanged ...
    return metrics
```

---

### Step 2: Delete `src/syntagmax/publish.py`

- [ ] **Delete the file** — its rendering logic is replaced by the unified report template.

---

### Step 3: Remove `print_metrics` from `src/syntagmax/render.py`

- [ ] **Remove the `print_metrics` function** and its associated import of `benedict`.

---

### Step 4: Delete `src/syntagmax/resources/metrics.j2`

- [ ] **Delete the file** — content is now in `report.j2`.

---

### Step 5: Verify

- [ ] **Run:** `uv run pytest -v`
- [ ] Confirm no import errors or dead references remain.
