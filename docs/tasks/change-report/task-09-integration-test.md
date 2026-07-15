# [ ] Task 9: End-to-End Integration Test

## Objective

Create a comprehensive integration test that exercises the full `change report` pipeline from CLI invocation through to report output, using realistic project data.

## Target File

`tests/test_change_report.py`

## Dependencies

- **All tasks 1-8** must be implemented before this test can pass.

This task should be written early (test-first approach possible) but will only pass after all components are integrated.

## Implementation

### Test Fixture Setup

Create a helper function or fixture that:

1. Creates a temp directory with a git repo
2. Sets up `.syntagmax/config.toml` with at least one input record (obsidian driver)
3. Sets up a `.syntagmax/project.syntagmax` metamodel file
4. Adds `.syntagmax/worktrees/` to `.gitignore`
5. Creates sample markdown files with artifacts:
   ```markdown
   [REQ]
   id: REQ-001
   status: draft
   priority: high
   ---
   The system shall do something.
   ```
6. Commits as "Initial commit" (this becomes the base)
7. Makes changes:
   - Modify an existing artifact (change status, change content)
   - Add a new artifact
   - Remove an artifact (delete its file or section)
   - Add non-artifact text
8. Commits as "Second commit" (this becomes the target)

### Test Cases

#### `test_basic_change_report`

- Run `syntagmax change report --base HEAD~1 --target HEAD`
- Verify exit code 0
- Verify report file created in `.syntagmax/reports/change/`
- Verify filename matches `<section>-<hash>-to-<hash>-<YYYYMMDD>.md` pattern

#### `test_report_contains_all_sections`

- Generate a report
- Verify presence of:
  - `# Change Report`
  - `## Repository Information`
  - `## Summary`
  - `## Changed Files`
  - `## Detailed Changes`

#### `test_summary_statistics_accurate`

- Generate a report with known changes (1 added, 1 modified, 1 removed artifact)
- Parse the summary table
- Verify counts match expected values

#### `test_artifact_changes_detected`

- Generate a report
- Verify the modified artifact shows both old and new content
- Verify attribute changes are displayed in a table
- Verify added artifact appears with `Status: Added`
- Verify removed artifact appears with `Status: Removed`

#### `test_include_non_artifact_flag`

- Run without `--include-non-artifact` → verify no text fragment sections
- Run with `--include-non-artifact` → verify text fragment changes appear

#### `test_output_console`

- Run with `--output console`
- Verify report content appears in stdout
- Verify no file is written

#### `test_single_consolidated_report`

- Set up config with two input records
- Run with `--single`
- Verify only one output file generated (not per-record)

#### `test_per_record_separate_files`

- Set up config with two input records
- Run without `--single`
- Verify two separate report files generated, one per record

#### `test_renamed_file_handling`

- Rename a file between commits using `git mv`
- Verify the report shows `Status: Renamed` with old and new paths

#### `test_no_changes_between_revisions`

- Run with same commit as base and target
- Verify graceful exit with informational message (no empty report)

### Fixture Helper

```python
@pytest.fixture
def change_report_repo(tmp_path):
    """Create a git repo with two commits containing artifact changes."""
    ...
    return repo_path, base_hash, target_hash
```

## Technical Notes

- Use `click.testing.CliRunner` for CLI invocation
- Use `git.Repo.init()` for repo setup
- Keep test artifacts simple (minimal metamodel, few requirements)
- Use the existing `example/obsidian-driver` structure as inspiration for the test fixture format
- Tests should be independent (each creates its own repo)
- Clean up worktrees even if tests fail (use pytest fixtures with cleanup)

## Test Requirements

- All test cases must pass with exit code 0 (or expected error codes)
- Report output must be valid Markdown (no unclosed code blocks, proper table syntax)
- Tests must run on both Windows and Unix (use `Path` objects, avoid hardcoded separators)
- Tests must not leave stale worktrees behind

## Test File

`tests/test_change_report.py`
