# Task 7: Refactor tree rendering for Markdown output

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `render_tree_markdown()` function in `render.py` that returns a plain-text tree string (without rich markup) suitable for embedding in the Markdown report as a code block.

**Spec:** `docs/specs/united-report.spec.md`

---

### Step 1: Add `render_tree_markdown` to `src/syntagmax/render.py`

- [ ] **Implement a text-only tree renderer**

The function should produce the same visual structure as `print_arttree` but return a string instead of printing, and without any rich markup (`[cyan]`, `[green]`, etc.).

```python
def render_tree_markdown(artifacts: ArtifactMap, ref: str = 'ROOT', verbose: bool = False) -> str:
    lines: list[str] = []

    def _render(ref: str, indent: str = '', last: bool = True, top: bool = True):
        artifact = artifacts[ref]
        children = sorted(artifact.children, key=lambda c: artifacts[c].aid)

        prefix = '' if top else (indent + (CONST_L_CHAR if last else CONST_T_CHAR))
        label = f'{artifact.atype}: {artifact.aid}' if artifact.atype != 'ROOT' else artifact.aid
        lines.append(f'{prefix}{label}')

        new_indent = indent if top else (indent + ('  ' if last else CONST_I_CHAR + ' '))

        for i, child_id in enumerate(children):
            _render(child_id, new_indent, i == len(children) - 1, False)

    _render(ref)
    return '\n'.join(lines)
```

---

### Step 2: Create unit test

- [ ] **Add test in `tests/test_report.py`** (or a new `tests/test_render_tree.py`)

```python
from syntagmax.artifact import Artifact, ArtifactMap
from syntagmax.render import render_tree_markdown


def test_render_tree_markdown():
    artifacts: ArtifactMap = {
        'ROOT': Artifact(aid='ROOT', atype='ROOT', pids=[], source='', fields={}),
        'REQ-001': Artifact(aid='REQ-001', atype='REQ', pids=['ROOT'], source='test.md', fields={}),
        'REQ-002': Artifact(aid='REQ-002', atype='REQ', pids=['ROOT'], source='test.md', fields={}),
    }
    artifacts['ROOT'].children = {'REQ-001', 'REQ-002'}

    result = render_tree_markdown(artifacts)
    assert 'ROOT' in result
    assert 'REQ: REQ-001' in result
    assert 'REQ: REQ-002' in result
    assert '├─' in result or '└─' in result
```

---

### Step 3: Verify

- [ ] **Run:** `uv run pytest tests/test_render_tree.py -v` (or wherever the test lands)
