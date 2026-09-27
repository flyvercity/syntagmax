# [ ] Task 5: `syntagmax.api` facade — read side

**Spec:** `docs/specs/library-embedding-api.spec.md` (R1, part 1; critique E2, P2)

**Depends on:** none beyond the existing pipeline.

## Objective

The embedding entry point (`open_project` / `Session`) and structured read operations.

## Implementation

### `src/syntagmax/api.py` (new)

- `@dataclass class Options`: `render_tree=False, no_git=False, allow_dirty_worktree=False, suppress_tracing=False, tasks=False, language='en', warnings_as_errors=False, log_level=None`.
- Internal `_options_to_params(options, cwd) -> Params` filling every required `Params` key (`render_tree, ai=False, cwd, no_git, allow_dirty_worktree, language, suppress_tracing, tasks`, plus optional `log_level`, `warnings_as_errors`).
- `open_project(config_path, *, options=None) -> Session`: resolve path, build `Config(_options_to_params(...), Path(config_path))`.
- `class Session`:
  - holds a `threading.Lock`; lazily runs `extract → build_artifact_map → populate_pids → build_tree → analyse_tree` **under the lock** to cache an `ArtifactMap`; `reload()` acquires the same lock and clears the cache (E2). Note the Phase-1 full-reparse trade-off.
  - `artifacts()`, `get(aid)`, `query(atype=None, ...)`, `search(q)` build `ArtifactView`s from `Artifact`s.
  - **`search(q)` (P2):** case-insensitive over `aid`, `atype`, and all `fields` **including `contents`**; **AND** semantics across whitespace-separated terms.
- `@dataclass class ArtifactView`: `aid, atype, fields, parents (list of {pid, nominal_revision, is_suspicious}), children, latest_revision`.

## Test Requirements (`tests/test_api.py`)

- `Config` parity: facade-built `Config` matches a CLI-style `Config` on `root_dir`, `output_dir`, `input_records` for `example/`.
- `get`/`query`/`search` over `example/` return expected ids/atypes; `query(atype=...)` filters; `search` matches fields **and body `contents`**; multi-term requires all terms.
- Concurrency smoke: two threads calling `artifacts()`/`reload()` on one `Session` do not corrupt the cache.
- `FatalError` propagates for a broken config path.

## Demo

`python -c "from syntagmax import api; s=api.open_project('example/.../config.toml'); print(len(s.artifacts()))"`.

## Files Modified

- `src/syntagmax/api.py` (new)
- `tests/test_api.py` (new)
