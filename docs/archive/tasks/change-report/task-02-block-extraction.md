# [x] Task 2: Block Extraction at a Specific Revision

## Objective

Create `src/syntagmax/change_extract.py` that extracts blocks from a worktree path using existing extractors without mutating the shared `Config` object.

## Target File

`src/syntagmax/change_extract.py`

## Dependencies

- **Task 1** (worktree management — provides the worktree path to extract from)

## Implementation

### Main Function

```python
def extract_blocks_at_revision(
    config: Config,
    worktree_path: Path,
    changed_files: list[str] | None = None,
) -> dict[str, list[FileRecord]]:
```

- Returns a mapping of `{record_name: [FileRecord, ...]}` keyed by input record name
- If `changed_files` is provided, only extract from files in that list (performance optimization)
- If `worktree_path` is the repo working directory (i.e., `working` revision), use files as-is

### Config Isolation Strategy

The `Config` object must NOT be mutated. Two approaches (choose one):

**Option A: Shallow clone with remapped paths**
- Create a lightweight wrapper or dataclass that holds the original config's settings but with `record_base` and `filepaths` remapped to the worktree directory
- Use `dataclasses.replace()` on `InputRecord` to produce modified copies

**Option B: Path remapping function**
- `remap_path(original_path: Path, original_base: Path, worktree_base: Path) -> Path`
- Compute the relative path from original base, then resolve against worktree base
- Pass remapped paths to extractors without touching the config

### Extraction Flow

1. For each `InputRecord` in config:
   - Compute the equivalent directory path within the worktree: `worktree_path / record.dir`
   - Re-glob filepaths using the same filter pattern as the original record
   - If `changed_files` is provided, intersect with the globbed results
   - Instantiate the appropriate extractor (from `EXTRACTORS` dict) with a cloned/remapped config
   - Call `extract_blocks_from_file(filepath)` for each file
   - Collect results into `FileRecord` objects with relative paths (relative to base)

2. All file reads use context managers to ensure handles are closed immediately

### Return Type

```python
@dataclass
class FileRecord:
    path: str  # Relative path (consistent between base and target for comparison)
    blocks: list[Block]
```

Reuses the existing `FileRecord` from `syntagmax.blocks`.

## Technical Notes

- The path stored in `FileRecord.path` must be normalized and relative to the project base (not the worktree path) so that base and target records can be compared by path
- Extractors use `config.derive_path(filepath)` internally — ensure this returns consistent relative paths regardless of whether the file is in a worktree or the main working directory
- The `metamodel` from config is shared and read-only — safe to reuse without cloning

## Test Requirements

- Create a temp git repo with sample obsidian markdown files containing artifacts
- Commit version 1, modify artifacts, commit version 2
- Create worktrees for both commits
- Extract blocks from both worktrees
- Verify: correct number of artifacts extracted, correct field values at each revision
- Verify: `FileRecord.path` values are consistent between base and target extractions

## Test File

`tests/test_change_extract.py`
