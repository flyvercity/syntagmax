# Change Report — Implementation Specification

## Problem Statement

Implement a `syntagmax change report` command that generates a human-readable Markdown report comparing artifacts between two Git revisions, analyzing changes at the artifact and text block level using the existing extraction pipeline.

## Requirements

- Compare two Git revisions (commits, tags, branches, HEAD, HEAD~N)
- Use physical worktrees under `.syntagmax/worktrees/` for extraction
- Reuse existing extractors (obsidian, markdown, text, sidecar, ipynb) unmodified
- Match artifacts by `aid` for comparison (added/modified/removed)
- Generate one report file per input record, named `<section>-<YYYYMMDD>.md`
- Default output to `.syntagmax/reports/change/`
- Include: repository info, summary stats, changed files, detailed artifact changes, attribute changes, text fragment changes
- `--include-non-artifact` flag for analyzing non-artifact text blocks
- Handle errors gracefully (fall back to plain-text diff when extraction fails)
- Support `--output console` for stdout

## Background

- CLI uses Click groups/commands (`cli.py`). New command: `rms.group('change')` → `report` subcommand.
- Extractors expose `extract_blocks_from_file(filepath)` returning `list[Block]` (ArtifactBlock, TextBlock, ErrorBlock).
- `Config` creates `InputRecord` with `filepaths` resolved via glob on `record_base`.
- GitPython is already a dependency; `git.Repo` is used throughout.
- `BlockTree` / `InputBlock` / `FileRecord` data model from `blocks.py` can inform the comparison structure.
- Artifacts have `aid`, `atype`, `fields` (dict), `pids` (parent links), and `location`.

## Design Decisions

1. **Physical worktrees** (not `git show`) — faster batch extraction, allows reusing extractors unmodified since they rely on `filepath.read_text()` and glob-based file discovery.
2. **Two worktrees** created under `.syntagmax/worktrees/` (one for base, one for target), cleaned up after report generation.
3. **Artifact matching by `aid`** — if an artifact ID exists in both revisions, it's compared field-by-field; only in target = added; only in base = removed.

## Proposed Solution

1. Add a `change` group with a `report` subcommand in CLI
2. Create a `change_report.py` module handling: worktree management, extraction at both revisions, diff computation (file-level via git, artifact-level via aid matching, text-block-level via content comparison), and Markdown report rendering
3. Use `git worktree add .syntagmax/worktrees/<rev-label> <rev>` to materialize both revisions, then construct a temporary `Config` pointing at each worktree to run extractors
4. Compare results per-input-record, generate per-record report files

---

## Task Breakdown

### Task 1: Worktree Management Utility

**Objective:** Create `src/syntagmax/change_worktree.py` with functions to create/remove git worktrees under `.syntagmax/worktrees/`.

**Implementation:**
- `create_worktree(repo: git.Repo, revision: str, label: str) -> Path` — calls `git worktree add`. Validates system Git version is >= 2.5.
- `remove_worktree(repo: git.Repo, path: Path)` — calls `git worktree remove`, wrapped in retry-with-backoff logic to handle Windows file locks. Runs `git worktree prune`.
- `resolve_revision(repo: git.Repo, rev_str: str) -> str` — validates and resolves to a commit hash. Accepts `working` for active uncommitted files if supported.
- Context manager `worktree_pair(repo, base_rev, target_rev)` that creates both and ensures robust cleanup.
- **Pre-flight check:** Before creating worktrees, verify that `.syntagmax/worktrees/` is covered by `.gitignore`. If not, abort with a clear error message instructing the user to add the path to `.gitignore` (or offer to add it automatically).

**Test requirements:** Unit test with a temp git repo, verify worktree creation/removal, test invalid revision error.

---

### Task 2: Block Extraction at a Specific Revision

**Objective:** Create `src/syntagmax/change_extract.py` that extracts blocks from a worktree path using existing extractors.

**Implementation:**
- `extract_blocks_at_revision(config: Config, worktree_path: Path) -> dict[str, list[FileRecord]]` keyed by input record name
- Safely clone the `Config` instance or map filepaths to the worktree path without mutating the original `Config` object in-place
- Re-glob `InputRecord.filepaths` relative to the worktree root path
- Instantiate extractors pointing at worktree paths, call `extract_blocks_from_file` per file, ensuring all file streams are closed
- Return a per-record mapping of `FileRecord` objects (path → blocks)

**Test requirements:** Create a temp git repo with sample markdown files, commit, modify, extract at both revisions, verify block counts.

---

### Task 3: File-Level Diff Identification

**Objective:** Create `src/syntagmax/change_diff.py` with logic to identify changed files between two revisions.

**Implementation:**
- `get_changed_files(repo: git.Repo, base: str, target: str) -> list[FileDiff]` using `base_commit.diff(target_commit)` from GitPython
- `FileDiff` dataclass with: `path`, `status` (Added/Removed/Modified/Renamed), `old_path` (for renames)
- Filter results to only files relevant to input records (match against record glob patterns)

**Test requirements:** Test with added, removed, modified, and renamed files in a temp repo.

---

### Task 4: Artifact-Level Comparison

**Objective:** Create comparison logic in `change_diff.py` that matches artifacts by `aid` between base and target.

**Implementation:**
- `compare_artifacts(base_blocks: list[FileRecord], target_blocks: list[FileRecord]) -> ArtifactDiff`
- `ArtifactDiff` contains: `added: list[Artifact]`, `removed: list[Artifact]`, `modified: list[ArtifactChange]`
- `ArtifactChange` dataclass: `aid`, `atype`, `base_artifact: ArtifactBlock`, `target_artifact: ArtifactBlock`, `changed_fields: dict[str, tuple[old, new]]`, `content_changed: bool`
- Compare `fields` dicts to identify attribute changes
- Compare `raw_text` / `contents` field for text changes

**Test requirements:** Test with added, removed, modified artifacts; test attribute changes detection.

---

### Task 5: Text Block Comparison (Non-Artifact)

**Objective:** Add text fragment diffing to `change_diff.py`.

**Implementation:**
- `compare_text_blocks(base_blocks: list[FileRecord], target_blocks: list[FileRecord]) -> list[TextFragmentChange]`
- `TextFragmentChange`: `status` (Added/Removed/Modified), `old_content`, `new_content`, `old_lines: tuple[int,int]`, `new_lines: tuple[int,int]`
- Use Python's `difflib.SequenceMatcher` to align text blocks by position/content similarity within same file. For blocks exceeding 200 lines, skip `SequenceMatcher` and fall back to standard line-by-line diff to prevent performance bottlenecks.
- Track line ranges based on block position in original file

**Test requirements:** Test detection of modified, added, removed text fragments.

---

### Task 6: Markdown Report Renderer

**Objective:** Create `src/syntagmax/change_render.py` that generates the full Markdown report from diff data.

**Implementation:**
- `render_change_report(report_data: ChangeReportData) -> str`
- `ChangeReportData` dataclass aggregating: repo info, summary stats, per-file changes, artifact changes, text fragment changes
- Sections: Repository Information → Summary → Changed Files → Detailed Changes (per file: document structure, artifacts, text fragments)
- Format attribute changes as tables, text changes as fenced code blocks with Previous/Current
- No HTML — headings, tables, lists, code blocks, horizontal rules only

**Test requirements:** Test rendering with known input data, verify valid Markdown output, verify section structure.

---

### Task 7: CLI Command Wiring

**Objective:** Add `change report` command to `cli.py`.

**Implementation:**
- Add `@rms.group('change')` group
- Add `report` subcommand with options: `--base`, `--target`, `--output`, `--include-non-artifact`, `-f/--config-file`
- Wire together: resolve revisions → create worktrees → extract blocks at both revisions → compute file diffs → compute artifact diffs → (optionally) compute text diffs → render reports → write per-record output files → cleanup worktrees
- Default output path: `.syntagmax/reports/change/`
- File naming: `<section>-<base_rev>-to-<target_rev>-<YYYYMMDD>.md` to avoid date-only file collisions.
- Output paths: Print the absolute path of each generated report file to stdout on success.
- Support `--output console` for stdout.
- Add `--single` / `--combined` option to generate a single consolidated report across all input records.

**Test requirements:** Integration test using Click's `CliRunner` with a temp git repo containing sample artifacts.

---

### Task 8: Error Handling and Fallback

**Objective:** Implement graceful error handling per the spec (Section 25).

**Implementation:**
- Validate revisions exist before proceeding (clear error message if not)
- If extraction fails for a file, catch the exception and generate a fallback section with plain-text diff (using `difflib.unified_diff`) and error information
- Handle missing files in one revision (file added/removed cases)
- Handle corrupted input gracefully

**Test requirements:** Test with invalid revisions, test with a file that fails extraction, verify fallback output.

---

### Task 9: End-to-End Integration Test

**Objective:** Create a full integration test using the existing `example/obsidian-driver` fixture.

**Implementation:**
- Create `tests/test_change_report.py` with an end-to-end scenario
- Set up a temp repo, copy example files, make commits with changes, run the full pipeline
- Verify: report file exists, contains expected sections, correct summary stats, artifact changes are accurately reported
- Verify per-record file naming convention

**Test requirements:** Full pipeline test covering the happy path.

---

## Workflow Diagram

```
CLI (syntagmax change report --base X --target Y)
│
├── Resolve revisions (validate X, Y exist)
│
├── Create worktrees
│   ├── .syntagmax/worktrees/base → checkout X
│   └── .syntagmax/worktrees/target → checkout Y
│
├── Get changed files (git diff --name-status X Y)
│   └── Filter to files within input records
│
├── For each input record:
│   ├── Extract blocks at base revision (existing extractors)
│   ├── Extract blocks at target revision (existing extractors)
│   ├── Compare artifacts by aid
│   │   ├── Added (in target only)
│   │   ├── Removed (in base only)
│   │   └── Modified (in both, fields differ)
│   ├── Compare text blocks (if --include-non-artifact)
│   ├── Compute summary statistics
│   └── Render per-record Markdown report
│
├── Write report files (<section>-<YYYYMMDD>.md)
│
└── Cleanup worktrees
```

## File Layout

```
src/syntagmax/
├── change_worktree.py   # Worktree creation/removal utilities
├── change_extract.py    # Block extraction at a specific revision
├── change_diff.py       # File-level, artifact-level, text-block comparison
├── change_render.py     # Markdown report generation
└── cli.py               # (modified) Add `change` group + `report` command

tests/
└── test_change_report.py  # Integration and unit tests
```

---

### Task 10: Documentation Updates

**Objective:** Update all relevant project documentation to cover the new `change report` command.

**Implementation:**
- Add command description, options, and usage examples to `README.md`.
- Update `docs/reference/CLI.md` to document the new `change` group and `report` subcommand.
- Document default output path and behavior of the `--include-non-artifact` option.
- Document the `--single` option for consolidated reports.
- Document the `working` keyword for comparing uncommitted changes.

**Test requirements:** Verify that built/rendered documentation includes the new command details.
