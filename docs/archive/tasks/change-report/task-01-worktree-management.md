# [x] Task 1: Worktree Management Utility

## Objective

Create `src/syntagmax/change_worktree.py` with functions to create/remove git worktrees under `.syntagmax/worktrees/`.

## Target File

`src/syntagmax/change_worktree.py`

## Dependencies

None — this is a foundational task.

## Implementation

### Functions

- `create_worktree(repo: git.Repo, revision: str, label: str) -> Path`
  - Calls `git worktree add .syntagmax/worktrees/<label> <revision>`
  - Validates system Git version is >= 2.5 before proceeding
  - Returns the absolute path to the created worktree

- `remove_worktree(repo: git.Repo, path: Path)`
  - Calls `git worktree remove <path>`
  - Wrapped in retry-with-backoff logic (exponential, up to 3 retries) to handle Windows file locks
  - Falls back to `shutil.rmtree` if `git worktree remove` fails after retries
  - Runs `git worktree prune` after removal

- `resolve_revision(repo: git.Repo, rev_str: str) -> str`
  - Validates and resolves the revision string to a full commit hash
  - Accepts: commit hashes, tags, branches, HEAD, HEAD~N
  - Accepts `working` keyword — returns a sentinel indicating the current working directory should be used directly (no worktree needed)
  - Raises `RMSException` with clear message if the revision does not exist

- `worktree_pair(repo, base_rev, target_rev)` — context manager
  - Creates both worktrees on entry
  - Ensures robust cleanup on exit (even on exceptions)
  - If either revision is `working`, skips worktree creation for that one and returns the repo's working directory path instead

### Pre-flight Check

- `check_worktrees_gitignored(repo: git.Repo) -> bool`
  - Uses `git check-ignore .syntagmax/worktrees/` or parses `.gitignore` to verify the path is ignored
  - If NOT ignored: abort with error message instructing the user to add `.syntagmax/worktrees/` to `.gitignore`

### Git Version Check

- `check_git_version(repo: git.Repo) -> None`
  - Parses output of `git --version`
  - Raises `FatalError` if version < 2.5

## Technical Notes

- Use `git.Repo.git.worktree('add', ...)` for GitPython integration
- Worktree labels should be sanitized (no special characters) — use short commit hash or `base`/`target` as labels
- All file handles must be explicitly closed before removal attempts (use context managers in extractors)
- On Windows, indexers/antivirus may hold locks — retry logic is critical

## Test Requirements

- Unit test with a temp git repo (pytest `tmp_path` fixture)
- Verify worktree creation produces expected directory with correct file contents at the given revision
- Verify worktree removal cleans up the directory
- Test that invalid revision raises appropriate error
- Test pre-flight gitignore check (positive and negative cases)
- Test `working` keyword returns the repo working dir path without creating a worktree

## Test File

`tests/test_change_worktree.py`
