# Task 3: Refactor Config to remove per-section output options

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove `output_format`, `output_file`, `template`, and `locale` from `MetricsConfig` and `ImpactConfig`. Ensure backward compatibility with existing config files that still have these fields.

**Spec:** `docs/specs/united-report.spec.md`

---

### Step 1: Update `src/syntagmax/config.py`

- [ ] **Strip output fields from `MetricsConfig`**

Keep only the fields relevant to metrics calculation:
```python
class MetricsConfig(BaseModel):
    model_config = ConfigDict(extra='ignore')
    requirement_type: str = Field(default='REQ')
    status_field: str = Field(default='status')
    verify_field: str = Field(default='verify')
    tbd_marker: str = Field(default='TBD')
```

- [ ] **Strip output fields from `ImpactConfig`**

Make it an empty model (impact config had no calculation-relevant fields, only output fields):
```python
class ImpactConfig(BaseModel):
    model_config = ConfigDict(extra='ignore')
```

Note: If `ImpactConfig` becomes empty, consider removing it from `Config` class entirely and just checking if the `[impact]` section exists in the TOML (indicating impact is enabled). However, keeping it as an empty model with `extra='ignore'` is the minimal change.

- [ ] **Add `ConfigDict(extra='ignore')` import** from pydantic if not already present

---

### Step 2: Remove references to removed fields

- [ ] **In `metrics.py`:** Remove the `if config.metrics.output_format == ...` branching at the end of `calculate_metrics`. The function will just return data (handled in Task 4, but remove dead references here if doing in sequence).

- [ ] **In `impact.py`:** Remove references to `config.impact.output_format`, `config.impact.output_file`, `config.impact.template`, `config.impact.locale` (handled in Task 5).

Note: If Tasks 4 and 5 are done after this task, the code may temporarily have attribute errors. Coordinate accordingly — or do Task 3 together with Tasks 4 and 5.

---

### Step 3: Verify backward compatibility

- [ ] **Run:** `uv run syntagmax --cwd ./example/obsidian-driver analyze extract`
  - The example config still has `output_format` and `output_file` in `[metrics]` and `[impact]` — these should be silently ignored.
- [ ] **Run:** `uv run pytest -v`
