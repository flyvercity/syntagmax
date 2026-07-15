# [ ] Task 4: Artifact-Level Comparison

## Objective

Create comparison logic that matches artifacts by `aid` between base and target revisions, identifying added, removed, and modified artifacts with detailed field-level changes.

## Target File

`src/syntagmax/change_diff.py` (extends the file from Task 3)

## Dependencies

- **Task 2** (block extraction — provides `list[FileRecord]` with `ArtifactBlock` instances)
- **Task 3** (file diff — provides the `change_diff.py` module to extend)

## Implementation

### Data Model

```python
@dataclass
class ArtifactChange:
    aid: str
    atype: str
    base_block: ArtifactBlock
    target_block: ArtifactBlock
    changed_fields: dict[str, tuple[str | list[str], str | list[str]]]  # {field: (old_value, new_value)}
    content_changed: bool
    base_raw_text: str
    target_raw_text: str


@dataclass
class ArtifactDiff:
    added: list[ArtifactBlock]       # Artifacts only in target
    removed: list[ArtifactBlock]     # Artifacts only in base
    modified: list[ArtifactChange]   # Artifacts in both with differences
```

### Main Function

```python
def compare_artifacts(
    base_records: list[FileRecord],
    target_records: list[FileRecord],
) -> ArtifactDiff:
```

### Algorithm

1. **Collect artifacts by `aid`:**
   - Scan all `ArtifactBlock` instances in base records → `base_map: dict[str, ArtifactBlock]`
   - Scan all `ArtifactBlock` instances in target records → `target_map: dict[str, ArtifactBlock]`

2. **Classify:**
   - `added` = aids in target_map but not in base_map
   - `removed` = aids in base_map but not in target_map
   - `common` = aids in both maps

3. **Compare common artifacts:**
   - For each common aid, compare:
     - `artifact.fields` dict — detect added, removed, and changed keys
     - `raw_text` — detect content body changes
     - Parent links (`pids`) — detect link changes
   - If any difference is found, create an `ArtifactChange` entry
   - Link changes (pids) are reported as field changes with a synthetic field name (e.g., `_parents`)

### Field Comparison Logic

```python
def compare_fields(
    base_fields: dict[str, str | list[str]],
    target_fields: dict[str, str | list[str]],
) -> dict[str, tuple[str | list[str] | None, str | list[str] | None]]:
```

- Returns only fields that differ
- Added fields: `(None, new_value)`
- Removed fields: `(old_value, None)`
- Changed fields: `(old_value, new_value)`
- For list fields, compare as sorted sets to avoid ordering false-positives

## Technical Notes

- `ArtifactBlock.artifact.aid` is the primary matching key
- `ArtifactBlock.artifact.fields` contains all extracted attributes
- `ArtifactBlock.raw_text` contains the full raw source text of the artifact block
- The `contents` field within `fields` holds the processed text content — compare both `raw_text` and `contents` for thoroughness
- Handle edge case: same `aid` appearing in multiple files (should not happen per extraction logic, but guard against it)

## Test Requirements

- Create mock `FileRecord` lists with `ArtifactBlock` instances
- Test: artifact present only in target → classified as added
- Test: artifact present only in base → classified as removed
- Test: artifact in both with same fields → NOT in modified list
- Test: artifact with changed field values → appears in modified with correct `changed_fields`
- Test: artifact with changed content text → `content_changed = True`
- Test: artifact with changed parent links → reported as field change
- Test: list-valued fields compared correctly (order-independent)

## Test File

`tests/test_change_diff.py` (extends from Task 3)
