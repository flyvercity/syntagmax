# Syntagmax Application Logic — Change, Trace, and Baseline Subsystem

> Covers revision comparison, worktree isolation, trace matrix generation/export, and multi-repository baseline tagging. Source: `change_*.py`, `trace.py`, and their CLI wrappers.

## 1. Change report

### 1.1 Preconditions

- Load configured input records.
- Open Git repository containing the configured base directory.
- Require Git worktree support (>= 2.5).
- Require all input records inside the discovered repository.
- Require the worktree staging directory to be Git-ignored.
- Resolve base/target revisions; sentinel `working` uses the current worktree.

### 1.2 Revision worktrees

- Non-working revisions are checked out into detached worktrees under `<config_root>/worktrees`.
- Existing stale `base`/`target` paths are removed first.
- Worktrees are removed in `finally` blocks.
- Windows removal retries three times, then falls back to `shutil.rmtree`; Git worktree prune follows.
- One or both sides may use the live working tree.

### 1.3 File and artifact comparison

File statuses: Added, Removed, Modified, Renamed.

Changed files are filtered by input-record directory relative to repository root.

Artifacts are matched by `aid`:

- target-only → added;
- base-only → removed;
- both → compare non-content fields, stripped contents, and sorted parent IDs.

Field comparison:

- added field = `(None, new)`;
- removed field = `(old, None)`;
- changed scalar = `(old, new)`;
- lists compare order-insensitively after string conversion;
- `contents` is compared separately.

Optional text-block comparison:

- groups blocks by file;
- matches explicit IDs first, then sequence/position alignment;
- uses `SequenceMatcher` up to 200 lines and line-based fallback for larger blocks;
- records added/removed/modified content with line estimates and markers.

Sidecar/binary comparison is included separately through `change_binary` support.

Extraction failures generate a fallback unified diff from readable base/target files.

### 1.4 Output

- Detailed or summary renderer produces per-record Markdown.
- Empty record set prints no-change message and returns.
- Console mode prints reports with separators when multiple.
- Separate mode writes dated per-record files.
- Single mode joins reports with `---`; directory-like output receives generated filename.
- `working` appears as a filename label instead of a hash.

## 2. Trace matrix

`TraceMatrix` fields: direction, child/parent types, attribute names, records, artifact-to-record names.

`build_trace_matrix()` uses left-outer-join semantics:

- forward: every child appears; linked IDs are matching parents;
- reverse: every parent appears; linked IDs are matching children;
- unresolved forward IDs remain visible as raw linked IDs;
- wrong-type links are ignored;
- no links produce a row with empty linked ID.

Flat mode combines links with `; `. Non-flat mode emits one row per link. Rows and lead artifacts are sorted by ID; record numbers are 1-based sequential.

Lead artifact attributes are serialized as strings; lists use `; `.

CSV/TSV rendering:

- forward header: `RecordNumber,ChildID,ParentID,...`;
- reverse header: `RecordNumber,ParentID,ChildID,...`;
- Python CSV writer uses newline `\n` and selected delimiter.

CLI trace path first builds extraction/map/tree, warns on pipeline/type issues, then either calls configured `export_trace` plugins or writes built-in CSV/TSV.

## 3. Baseline tagging

`discover_repos()`:

1. Find Git repository for each input record.
2. Deduplicate by resolved repository root.
3. Reject repositories outside configured base directory.
4. Reject records outside Git.
5. Reject no repositories.

`check_repos_clean()` rejects tracked modifications, staged changes, and untracked files.

`validate_tag_name()` applies configured `baseline.tag_pattern` with full regex matching.

`check_tag_exists()`:

- existing tag without force → fatal;
- with force → warning and overwrite path.

`create_baseline_tag()`:

- creates annotated tag at each repository HEAD;
- force deletes old tag first;
- on failure, deletes tags created earlier in this run and raises fatal error;
- returns repository roots and short HEAD hashes.

CLI dry-run validates all preconditions and prints tag/message/repository/HEAD plan without changing tags. Normal CLI prints success and push instructions but never pushes.

## 4. Risks/status

- Change reports depend on valid Git worktrees and input/repository boundaries.
- Baseline tagging has rollback for tags created in the current run, but cannot restore a force-deleted old tag if later creation fails.
- **`UNVERIFIED`:** exact sequence-matching corner cases, binary comparison details, and all worktree cleanup failure modes require the complete change test suite.
