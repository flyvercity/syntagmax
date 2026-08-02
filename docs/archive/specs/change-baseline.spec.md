# Specification: `syntagmax change baseline` Command

## Problem Statement

Syntagmax needs a `change baseline <tag-name>` command that creates a consistent git tag across all repositories that input records point to, enabling baseline snapshots for multi-repo requirement projects.

## Requirements

1. Command: `syntagmax change baseline <tag-name>`
2. Discovers all distinct git repositories from input records' `record_base` paths
3. Refuses to proceed if **any** discovered repo is dirty (tracked changes OR untracked files)
4. Creates an annotated tag at HEAD in each repo, with auto-generated message ("Baseline created by Syntagmax") and optional `--message` override
5. Optional `tag_pattern` regex in `[baseline]` section of `config.toml` — rejects tag names that don't match
6. `--force` flag to overwrite existing tags; without it, errors if tag already exists in any repo
7. Atomic behavior: validates all preconditions (dirty check, tag existence, regex) across all repos **before** creating any tags
8. `--dry-run` flag to preview actions without creating tags
9. Rollback behavior: if tag creation fails on any repo during execution, all tags created during this run are deleted to preserve atomicity

## Design Decisions

| # | Question | Answer |
|---|----------|--------|
| 1 | Multi-repo support | Yes. The whole purpose of `baseline` is to ensure consistency across multiple repos. All input records are always included. |
| 2 | Config location for tag regex | `[baseline]` section — e.g., `tag_pattern = "^v\\d+\\.\\d+$"` |
| 3 | Tag already exists behavior | Error by default; `--force` flag allows overwrite with verbose logging of each overwritten tag |
| 4 | Dirty check strictness | Strict — `repo.is_dirty() or len(repo.untracked_files) > 0` (same as existing behavior) |
| 5 | Tag type | Annotated with optional message. Default: "Baseline created by Syntagmax", override via `--message` |
| 6 | Target commit | Always HEAD of each repo |
| 7 | Boundary check | Repositories must be located within `config.base_dir()`. Escaping it raises FatalError. |
| 8 | Post-creation push | Success summary prints a reminder to push tags (`git push origin <tag>`). |

## Context

- The `change` command group already exists in `cli.py` (line 508)
- GitPython (`git` package) is already a dependency, used extensively
- `git_utils.py` has a `is_dirty()` helper and `RepoCache` pattern for discovering repos from artifact paths
- `InputRecord.record_base` is a `Path` pointing to the directory each record lives in — used to discover repos
- `Config` exposes `input_records()` and the `ConfigFile` pydantic model defines the config schema
- `FatalError` from `syntagmax.errors` is the standard way to report fatal validation failures
- Existing tests use `git.Repo.init(tmp_path)` + `CliRunner` patterns
- Note: `change report` currently enforces all records in one repo via `validate_records_in_repo`. The `baseline` command intentionally supports multi-repo.

## Flow

```
Parse CLI args: tag-name, --message, --force, --dry-run
    → Load Config
    → Discover distinct repos from input_records
    → Validate: At least one repo found?
        No → FatalError: no repositories discovered
    → Validate: Repos lie within project base directory?
        No → FatalError: repos outside project boundary
    → Validate: All repos clean?
        No → FatalError: list dirty repos
    → Validate: tag_pattern configured?
        Yes → Tag name matches regex?
            No → FatalError: tag doesn't match pattern
    → Validate: Tag exists in any repo?
        Yes, no --force → FatalError: tag exists in repos X, Y
    → If --dry-run: Print plan and exit
    → Create annotated tags at HEAD in all repos
        On failure: Delete tags created in this run, raise FatalError
    → Success output: list repos tagged + push reminder
```

## File Changes

### New Files

- `src/syntagmax/change_baseline.py` — core logic (repo discovery, validation, tagging)
- `tests/test_change_baseline.py` — unit + integration tests

### Modified Files

- `src/syntagmax/cli.py` — add `baseline` subcommand to the `change` group
- `src/syntagmax/config.py` — add `BaselineConfig` pydantic model and wire it into `ConfigFile`
- `src/syntagmax/init_cmd.py` — handle new `BaselineConfig` in default TOML template generator

## Configuration

```toml
[baseline]
tag_pattern = "^v\\d+\\.\\d+\\.\\d+$"   # optional regex
```

## CLI Interface

```
syntagmax change baseline <tag-name> [OPTIONS]

Arguments:
  tag-name              Tag name to create in all repos

Options:
  -m, --message TEXT    Tag annotation message (default: "Baseline created by Syntagmax")
  --force               Overwrite existing tags
  --dry-run             Preview changes without creating tags
  -f, --config-file     Path to config file (default: .syntagmax/config.toml)
```

## Task Breakdown

### Task 1: Add `BaselineConfig` to the config model

- **Objective:** Add a `[baseline]` section to `config.toml` schema with an optional `tag_pattern` field.
- **Implementation:** Add a `BaselineConfig` pydantic model with `tag_pattern: str | None = None`. Add it to `ConfigFile` as `baseline: BaselineConfig = Field(default_factory=BaselineConfig)`. Expose it via a property on `Config`.
- Add a `@field_validator('tag_pattern')` that compiles the regex via `re.compile()` and raises `ValueError` if invalid.
- Update `src/syntagmax/init_cmd.py` `generate_toml()` to ignore `baseline` in `ConfigFile` fields iteration and append a commented `# [baseline]` section.
- **Test:** Unit test that config loads with and without `[baseline]` section; test that invalid regex raises a validation error.
- **Demo:** `Config` object successfully parses a config with `[baseline]\ntag_pattern = "^v\\d+\\.\\d+$"`.

### Task 2: Implement repo discovery logic

- **Objective:** Given a list of `InputRecord` objects, discover the set of distinct git repos they belong to.
- **Implementation:** Create `src/syntagmax/change_baseline.py`. Implement `discover_repos(input_records: list[InputRecord], base_dir: Path) -> dict[Path, git.Repo]` that iterates `record_base` paths, calls `git.Repo(path, search_parent_directories=True)`, deduplicates by resolved `working_tree_dir`, and returns a mapping of `repo_root → Repo`.
- Check that each repo root is a subdirectory of or equal to `config.base_dir()`. Raise `FatalError` if it traverses outside the project boundary.
- Raise `FatalError` if the discovered dict is empty (no repos found).
- **Test:** Test with records in one repo → returns 1 entry. Test with records in two different repos → returns 2 entries. Test with a record not in any repo → raises `FatalError`. Test with a repo outside base_dir → raises `FatalError`.
- **Demo:** Function correctly identifies 2 repos when given records pointing to different git repositories.

### Task 3: Implement pre-flight validations (dirty check, tag existence, regex)

- **Objective:** Validate all preconditions before any tag is created.
- **Implementation:** In `change_baseline.py`, implement:
  - `check_repos_clean(repos: dict[Path, git.Repo])` — checks `repo.is_dirty() or len(repo.untracked_files) > 0` for each, raises `FatalError` listing all dirty repos.
  - `validate_tag_name(tag_name: str, pattern: str | None)` — compiles regex, matches tag_name, raises `FatalError` if no match.
  - `check_tag_exists(tag_name: str, repos: dict[Path, git.Repo], force: bool)` — checks if tag exists in any repo; if it does and `--force` is not set, raises `FatalError` listing repos.
- **Test:** Test dirty detection (staged, unstaged, untracked). Test regex validation (match/no-match/no-pattern). Test tag-exists with and without force.
- **Demo:** Running against a dirty repo raises a clear error listing which repos are dirty.

### Task 4: Implement tag creation logic

- **Objective:** Create annotated tags at HEAD in all discovered repos.
- **Implementation:** Implement `create_baseline_tag(tag_name: str, repos: dict[Path, git.Repo], message: str, force: bool)`. For each repo, use `repo.create_tag(tag_name, message=message, force=force)`.
- When `--force` is active and a tag already exists in a repo, log a warning for each overwritten tag (e.g., "Overwriting existing tag 'v1.0.0' in <repo_path> (was at <old_commit_short>)").
- Wrap the tag creation loop in a try/except block. If creation fails on any repository, delete the newly created tags in already-processed repositories during this run to roll back, then raise `FatalError`.
- **Test:** Test tag creation in single repo. Test tag creation across two repos. Test force-overwrite of existing tag. Verify tag is annotated with correct message. Verify rollback on failure (tag deleted from repos that were already tagged in this run).
- **Demo:** After running, `git tag -n` in each repo shows the new annotated tag.

### Task 5: Wire up the CLI command

- **Objective:** Add `syntagmax change baseline <tag-name>` with `--message`, `--force`, `--dry-run`, and `-f/--config-file` options.
- **Implementation:** In `cli.py`, add a `@change.command('baseline')` with:
  - `tag_name` argument
  - `--message` / `-m` option (default: "Baseline created by Syntagmax")
  - `--force` flag
  - `--dry-run` flag
  - `-f, --config-file` option (default `.syntagmax/config.toml`)
  - Load config, call `discover_repos`, run all validations. If `--dry-run`, print the planned repositories and exit. Otherwise, call `create_baseline_tag`. Print success summary listing each repo, its tagged commit, and a push reminder.
- **Test:** Integration test using `CliRunner` — single repo happy path, multi-repo happy path, dirty repo error, regex mismatch error, existing tag error, `--force` override, `--dry-run` preview.
- **Demo:** `syntagmax change baseline v1.0.0` creates an annotated tag in all repos and prints a summary with push reminder.

### Task 6: End-to-end test with multi-repo setup

- **Objective:** Full integration test simulating the real use case — two repos with input records, baseline created consistently.
- **Implementation:** Create a test that sets up two git repos in `tmp_path`, writes a `config.toml` with input records pointing to both, runs the baseline command via `CliRunner`, and verifies tags exist in both repos with correct messages.
- Ensure test setup commits at least one file to each repo before tagging (git cannot tag an empty repo without HEAD).
- **Test:** Verify tags exist. Verify atomic failure (if second repo is dirty, no tag is created in the first either — rollback removes it).
- **Demo:** Demonstrates the atomicity guarantee — all-or-nothing tagging across repos.
