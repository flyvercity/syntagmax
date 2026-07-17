# [x] Task 7: CLI Command Wiring

## Objective

Add `change report` command to `cli.py` that orchestrates the full pipeline: revision resolution → worktree creation → extraction → comparison → rendering → output → cleanup.

## Target File

`src/syntagmax/cli.py` (modify existing)

## Dependencies

- **Task 1** (worktree management)
- **Task 2** (block extraction)
- **Task 3** (file-level diff)
- **Task 4** (artifact comparison)
- **Task 5** (text block comparison)
- **Task 6** (report renderer)

This task is the integration point — it wires all other components together.

## Implementation

### CLI Structure

```python
@rms.group(help='Change Analysis Commands')
def change():
    pass


@change.command('report', help='Generate change report between two revisions')
@click.pass_obj
@click.option('--base', required=True, help='Base Git revision (commit, tag, branch, HEAD, HEAD~N, or "working")')
@click.option('--target', required=True, help='Target Git revision (commit, tag, branch, HEAD, HEAD~N, or "working")')
@click.option('--output', default=None, help='Output directory or "console" for stdout')
@click.option('--include-non-artifact', is_flag=True, help='Include non-artifact text block changes')
@click.option('--single', is_flag=True, help='Generate a single consolidated report across all input records')
@click.option('-f', '--config-file', type=click.Path(), default='.syntagmax/config.toml')
def report(obj, base, target, output, include_non_artifact, single, config_file):
    ...
```

### Orchestration Flow

1. **Load config:**
   - Validate config file exists
   - Create `Config` instance

2. **Resolve revisions:**
   - Call `resolve_revision(repo, base)` and `resolve_revision(repo, target)`
   - If either fails, print error and exit

3. **Pre-flight checks:**
   - Call `check_worktrees_gitignored(repo)`
   - Call `check_git_version(repo)`

4. **Create worktrees:**
   - Use `worktree_pair` context manager

5. **Get changed files:**
   - Call `get_changed_files(repo, base_hash, target_hash)`
   - Call `filter_changed_files(changed_files, config.input_records(), config.base_dir())`

6. **For each input record (or combined if `--single`):**
   - Extract blocks at base revision (only changed files)
   - Extract blocks at target revision (only changed files)
   - Compute `ArtifactDiff`
   - Compute `TextBlockDiff` (if `--include-non-artifact`)
   - Build `ChangeReportData`
   - Render markdown

7. **Write output:**
   - Default path: `.syntagmax/reports/change/`
   - File naming: `<section>-<base_rev_short>-to-<target_rev_short>-<YYYYMMDD>.md`
   - `base_rev_short` / `target_rev_short`: first 7 chars of commit hash, or branch/tag name if short enough
   - If `--output console`: print to stdout
   - If `--single`: write one consolidated file
   - Print absolute path of each generated file to console (rich formatted)

8. **Cleanup:**
   - Context manager handles worktree removal

### File Naming

```python
def build_report_filename(record_name: str, base_rev: str, target_rev: str) -> str:
```

- Sanitize record name: replace spaces with `-`, remove invalid chars
- Use short revision identifiers (7-char hash or name)
- Format: `<section>-<base>-to-<target>-<YYYYMMDD>.md`
- Example: `software-requirements-abc1234-to-def5678-20260715.md`

### Console Output

On success, print:
```
[green]Change report generated:[/green]
  /absolute/path/to/software-requirements-abc1234-to-def5678-20260715.md (3 artifacts changed)
  /absolute/path/to/system-requirements-abc1234-to-def5678-20260715.md (1 artifact changed)
```

## Technical Notes

- Import new modules lazily (inside the command function) to avoid slowing down CLI startup
- Error handling: wrap the pipeline in try/except, ensure worktree cleanup always runs
- If no files changed between revisions, print a message and exit cleanly (no empty report)
- The `--single` option merges all records' data into one `ChangeReportData` before rendering

## Test Requirements

- Integration test using Click's `CliRunner`
- Create a temp git repo with config, artifacts, two commits
- Invoke the CLI command and verify:
  - Exit code 0
  - Report file created at expected path with expected name
  - Report contains expected sections
- Test `--output console` prints to stdout
- Test `--single` produces one file
- Test invalid revision produces clear error message
- Test missing gitignore entry produces clear error message

## Test File

`tests/test_change_report_cli.py`
