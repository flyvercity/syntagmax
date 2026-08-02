# Task 8: Wire everything together in main.py and cli.py

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Orchestrate the unified report flow: accumulate data in `Report` during pipeline execution, render and write the report at the end, print a console summary.

**Spec:** `docs/specs/united-report.spec.md`

**Depends on:** Tasks 1–7

---

### Step 1: Modify `src/syntagmax/main.py`

- [ ] **Import Report and render_tree_markdown**

```python
from syntagmax.report import Report
from syntagmax.render import render_tree_markdown
```

- [ ] **Create Report instance and collect data from steps**

```python
def process(requested_step, config: Config) -> Report:
    report = Report()
    errors: list[str] = []
    artifacts_list = None
    artifacts = None
    plan = get_execution_plan(DEPS, requested_step)

    for step in plan:
        lg.info(f'Executing step: {step}')

        match step:
            case 'extract':
                artifacts_list = extract(config, errors)
            case 'build_artifact_map':
                if artifacts_list is None:
                    raise FatalError(f'Artifacts list not initialized for step {step}')
                artifacts = build_artifact_map(artifacts_list, errors)
            case 'metrics':
                if artifacts is None:
                    raise FatalError(f'Artifacts not initialized for step {step}')
                report.metrics = calculate_metrics(config, artifacts, errors)
            case 'impact':
                if artifacts is None:
                    raise FatalError(f'Artifacts not initialized for step {step}')
                report.impact = perform_impact_analysis(config, artifacts, errors)
            case 'ai':
                if artifacts is None:
                    raise FatalError(f'Artifacts not initialized for step {step}')
                report.ai_results = ai_analyze(config, artifacts, errors)
            case _:
                if artifacts is None:
                    raise FatalError(f'Artifacts not initialized for step {step}')
                STEPS[step](config, artifacts, errors)

    if config.params['render_tree']:
        if artifacts and 'ROOT' in artifacts:
            report.tree_text = render_tree_markdown(artifacts)

    report.errors = errors
    return report
```

---

### Step 2: Modify `src/syntagmax/cli.py`

- [ ] **Update the `analyze` command to use the report**

```python
@rms.command(help='Run full analysis of the project')
@click.pass_obj
@click.option('-f', '--config-file', type=click.Path(exists=True), default='.syntagmax/config.toml')
@click.option('--allow-dirty-worktree', is_flag=True)
@click.option('--suppress-tracing', is_flag=True)
@click.argument('step', type=click.Choice(public_steps()), default='metrics')
def analyze(obj: Params, config_file: Path, allow_dirty_worktree: bool, suppress_tracing: bool, step: str):
    obj['allow_dirty_worktree'] = allow_dirty_worktree
    obj['suppress_tracing'] = suppress_tracing
    config = Config(obj, config_file)
    report = process(step, config)
    _write_report(report, obj['output'])
```

- [ ] **Implement `_write_report` helper**

```python
def _write_report(report: Report, output: str):
    markdown = report.render()

    if output == 'console':
        print(markdown)
    else:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding='utf-8')

    error_count = len(report.errors)
    if output != 'console':
        summary = f'Report written to {output}'
        if error_count:
            summary += f', {error_count} error(s) found'
        u.pprint(f'[green]{summary}[/green]' if not error_count else f'[yellow]{summary}[/yellow]')
```

- [ ] **Remove `_write_error_report` function and `FatalError` error-file logic**

In `main()`, the `FatalError` handler should no longer write a separate error file. Instead, let the report handle it. Since `process()` no longer raises `FatalError` for validation errors (they're in the report), simplify:

```python
def main():
    try:
        rms()
    except FatalError as e:
        u.pprint(f'[red]{len(e.errors)} fatal error(s): {e.errors[0]}[/red]')
        sys.exit(1)
    except RMSException as e:
        u.pprint(f'[red]Failed: {e}[/red]')
        sys.exit(2)
    except Exception as e:
        u.pprint(f'[red]Failed: {e}[/red]')
        traceback.print_exc()
        sys.exit(3)
```

- [ ] **Remove the global `_error_output` variable** (already done in Task 2, confirm)

---

### Step 3: Remove `FatalError` raise for validation errors in `main.py`

- [ ] The old code raised `FatalError(errors)` at the end of `process()`. Now errors are part of the report, so remove that raise. Keep `FatalError` only for truly fatal situations (missing artifacts list, etc.).

---

### Step 4: Verify

- [ ] **Run:** `uv run pytest -v`
- [ ] **Run:** `uv run syntagmax --render-tree --cwd ./example/obsidian-driver analyze`
  - Confirm `.syntagmax/reports/report.md` is created under the example project's working dir
  - Confirm it contains: Errors section (if any), Tree section, Metrics section
- [ ] **Run:** `uv run syntagmax --output console --cwd ./example/obsidian-driver analyze`
  - Confirm Markdown is printed to stdout
