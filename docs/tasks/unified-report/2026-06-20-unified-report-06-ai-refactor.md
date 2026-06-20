# Task 6: Refactor AI step to return structured results

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modify `ai_analyze()` to collect results into a list of dicts and return it, instead of printing per-artifact results to console.

**Spec:** `docs/specs/united-report.spec.md`

---

### Step 1: Modify `src/syntagmax/ai.py`

- [ ] **Return structured results instead of printing**

```python
def ai_analyze(config: Config, artifacts: ArtifactMap, errors: list[str]) -> list[dict]:
    # ... provider setup unchanged ...
    results = []

    for artifact in artifacts.values():
        if artifact.atype == 'ROOT':
            continue

        lg.info(f'Launching AI analysis for {artifact.aid}')

        try:
            result = provider.analyze_requirement(artifact.contents())
            results.append({
                'aid': artifact.aid,
                'atype': artifact.atype,
                'ambiguity': result['metrics']['ambiguity'],
                'completeness': result['metrics']['completeness'],
                'verifiability': result['metrics']['verifiability'],
                'singularity': result['metrics']['singularity'],
            })
        except Exception as e:
            errors.append(f'AI analysis failed for {artifact}: {e}')

    return results
```

- [ ] **Remove `import rich`** (no longer needed)

---

### Step 2: Verify

- [ ] **Run:** `uv run pytest -v`
- [ ] Confirm no console output from AI step (only logging).
