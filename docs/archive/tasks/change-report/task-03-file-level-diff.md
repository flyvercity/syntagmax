# [x] Task 3: File-Level Diff Identification

## Objective

Create `src/syntagmax/change_diff.py` with logic to identify changed files between two Git revisions, filtered to files relevant to the project's input records.

## Target File

`src/syntagmax/change_diff.py`

## Dependencies

None — this task can be implemented independently using only GitPython.

## Implementation

### Data Model

```python
from dataclasses import dataclass
from enum import Enum


class FileStatus(Enum):
    ADDED = 'Added'
    REMOVED = 'Removed'
    MODIFIED = 'Modified'
    RENAMED = 'Renamed'


@dataclass
class FileDiff:
    path: str                    # Current path (target revision)
    status: FileStatus
    old_path: str | None = None  # Only set for renames
```

### Main Function

```python
def get_changed_files(
    repo: git.Repo,
    base_commit: str,
    target_commit: str,
) -> list[FileDiff]:
```

- Uses `base_commit_obj.diff(target_commit_obj)` from GitPython
- Maps GitPython's diff change types to `FileStatus`:
  - `A` → Added
  - `D` → Removed
  - `M` → Modified
  - `R` → Renamed (captures `rename_from` as `old_path`)
- Returns the full list of changed files

### Filter Function

```python
def filter_changed_files(
    changed_files: list[FileDiff],
    input_records: list[InputRecord],
    base_dir: Path,
) -> dict[str, list[FileDiff]]:
```

- Groups changed files by input record name
- A file belongs to a record if its path falls within `record.dir` and matches the record's filter glob pattern
- Files not matching any record are excluded from the result
- Returns `{record_name: [FileDiff, ...]}`

## Technical Notes

- GitPython's `diff()` returns `DiffIndex` objects — iterate with `iter_change_type()` for each status type
- For renamed files, both `a_path` and `b_path` are available on the diff object
- Paths from git diff are relative to the repo root — normalize them relative to the project's base directory for matching
- Handle the case where base or target is a `working` revision: use `repo.index.diff(None)` for uncommitted changes or `repo.head.commit.diff(None)` for working tree changes

## Test Requirements

- Create a temp git repo
- Commit initial files, then make changes (add, remove, modify, rename files) in a second commit
- Verify `get_changed_files` returns correct statuses for each file
- Verify renamed files have `old_path` populated
- Test `filter_changed_files` correctly groups by input record
- Test files outside input records are excluded

## Test File

`tests/test_change_diff.py`
