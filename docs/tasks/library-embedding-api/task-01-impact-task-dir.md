# [ ] Task 1: `impact.task_dir` redirectable task output

**Spec:** `docs/specs/library-embedding-api.spec.md` (R4)

## Objective

Allow embedders to redirect generated impact tasks out of the versioned worktree, without changing default CLI behaviour.

## Implementation

### `src/syntagmax/config.py`

- Add to `ImpactConfig`: `task_dir: str | None = Field(default=None, description='Override directory for generated task files; absolute honoured as-is, else relative to config dir. When unset, uses tasks_dir.')`.
- Add method `Config.task_dir()`:
  - if `self.impact.task_dir` is set: `p = Path(self.impact.task_dir)`; return `p` if `p.is_absolute()` else `Path(self._root_dir, p)`.
  - else: return `Path(self._root_dir, self.impact.tasks_dir)` (current behaviour, byte-identical).

### `src/syntagmax/tasks.py` (+ `main.py` impact step)

- Route the task-file write site that currently uses `tasks_dir()` to `Config.task_dir()`.

## Test Requirements

- Unset `task_dir` → tasks written under `<root>/tasks/` (unchanged); an existing task test still passes.
- Relative `task_dir = "out/tasks"` → written under `<root>/out/tasks`.
- Absolute `task_dir` → written at that absolute path, outside the root.

## Demo

`uv run syntagmax --cwd ./example/<a-project-with-tasks> analyze --tasks` writes to the default location; setting `task_dir` in that project's config redirects them.

## Files Modified

- `src/syntagmax/config.py`
- `src/syntagmax/tasks.py`
- `src/syntagmax/main.py` (if the write site is there)
- `tests/test_task_dir.py` (new) / `tests/test_tasks.py`
