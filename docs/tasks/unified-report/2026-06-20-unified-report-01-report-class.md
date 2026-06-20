# Task 1: Create the Report class and unified template

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `Report` dataclass in `src/syntagmax/report.py` that accumulates report sections and renders them to Markdown via a Jinja2 template.

**Spec:** `docs/specs/united-report.spec.md`

---

### Step 1: Create `src/syntagmax/report.py`

- [ ] **Create the Report class**

```python
from dataclasses import dataclass, field
from pathlib import Path

from benedict import benedict
from jinja2 import Environment, FileSystemLoader, select_autoescape


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    tree_text: str | None = None
    metrics: benedict | None = None
    impact: benedict | None = None
    ai_results: list[dict] | None = None

    def render(self) -> str:
        resources_dir = Path(__file__).parent / 'resources'
        env = Environment(
            loader=FileSystemLoader(str(resources_dir)),
            autoescape=select_autoescape(default=False),
        )
        template = env.get_template('report.j2')
        return template.render(report=self)
```

---

### Step 2: Create `src/syntagmax/resources/report.j2`

- [ ] **Create the unified Jinja2 template**

Report section order: Errors → Tree → Metrics → Impact → AI

```jinja2
# Analysis Report
{% if report.errors %}

## Errors

Total errors: {{ report.errors | length }}

{% for error in report.errors %}
{{ loop.index }}. {{ error }}
{% endfor %}
{% endif %}
{% if report.tree_text %}

## Artifact Tree

```text
{{ report.tree_text }}
```
{% endif %}
{% if report.metrics %}

## Metrics

Total Requirements: {{ report.metrics.total_requirements }}

### Requirements by Status

| Status | Count |
|--------|-------|
{% for row in report.metrics.requirements_by_status %}| {{ row.status }} | {{ row.count }} |
{% endfor %}

Requirements without verification (%): {{ "%.1f" | format(report.metrics.requirements_without_verify_pct) }}%
Requirements with TBD (%): {{ "%.1f" | format(report.metrics.requirements_with_tbd_pct) }}%
{% endif %}
{% if report.impact %}

## Impact Analysis

Total suspicious links: {{ report.impact.total_suspicious }}
{% if report.impact.total_suspicious > 0 %}

| Artifact | Parent | Required Revision | Actual Revision |
|----------|--------|-------------------|-----------------|
{% for link in report.impact.suspicious_links %}| {{ link.artifact_atype }}:{{ link.artifact_aid }} | {{ link.parent_atype }}:{{ link.parent_aid }} | {{ link.nominal_revision }} | {{ link.actual_revision }} |
{% endfor %}
{% if report.impact.suspicious_tree %}

### Suspicious Tree

```text
{{ report.impact.suspicious_tree }}
```
{% endif %}
{% endif %}
{% endif %}
{% if report.ai_results %}

## AI Analysis

| Artifact | Ambiguity | Completeness | Verifiability | Singularity |
|----------|-----------|--------------|---------------|-------------|
{% for r in report.ai_results %}| {{ r.atype }}:{{ r.aid }} | {{ r.ambiguity }} | {{ r.completeness }} | {{ r.verifiability }} | {{ r.singularity }} |
{% endfor %}
{% endif %}
```

---

### Step 3: Create unit test

- [ ] **Create `tests/test_report.py`**

```python
from benedict import benedict
from syntagmax.report import Report


def test_report_render_all_sections():
    report = Report(
        errors=['Error 1', 'Error 2'],
        tree_text='ROOT\n├─REQ: REQ-001\n└─REQ: REQ-002',
        metrics=benedict({
            'total_requirements': 5,
            'requirements_by_status': [
                {'status': 'active', 'count': 3},
                {'status': 'draft', 'count': 2},
            ],
            'requirements_without_verify_pct': 20.0,
            'requirements_with_tbd_pct': 10.0,
        }),
        impact=benedict({
            'total_suspicious': 1,
            'suspicious_links': [{
                'artifact_aid': 'REQ-002',
                'artifact_atype': 'REQ',
                'parent_aid': 'SYS-001',
                'parent_atype': 'SYS',
                'nominal_revision': 'abc1234',
                'actual_revision': 'def5678',
            }],
            'suspicious_tree': 'ROOT\n└─SYS:SYS-001 [*] UPDATED\n  └─REQ:REQ-002 [!] OUTDATED',
        }),
        ai_results=[{
            'aid': 'REQ-001',
            'atype': 'REQ',
            'ambiguity': 0.2,
            'completeness': 0.8,
            'verifiability': 0.9,
            'singularity': 0.7,
        }],
    )

    md = report.render()
    assert '## Errors' in md
    assert 'Error 1' in md
    assert '## Artifact Tree' in md
    assert 'REQ-001' in md
    assert '## Metrics' in md
    assert '## Impact Analysis' in md
    assert '## AI Analysis' in md
    assert '| REQ:REQ-001 |' in md


def test_report_render_empty():
    report = Report()
    md = report.render()
    assert '# Analysis Report' in md
    assert '## Errors' not in md
    assert '## Metrics' not in md
```

- [ ] **Run:** `uv run pytest tests/test_report.py -v`
