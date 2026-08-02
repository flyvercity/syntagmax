# Spec Critique: Change Report Implementation Specification

## Executive Summary

This report evaluates the proposed specification for [change-report.spec.md](../specs/change-report.spec.md) under the Product Lens and the Engineering Lens.

The specification outlines a robust and clean approach for implementing a `syntagmax change report` command that compares requirements and text blocks across Git revisions using physical worktrees. However, several critical usability issues and technical risks must be addressed before proceeding to implementation:
1. **Windows File System Locks and Cleanup**: On Windows systems (the user's OS), deleting directories used as Git worktrees often fails due to file system locks from open file handles or external indexers. Robust retry/cleanup logic is required.
2. **Path Resolution and Config Mutation**: In-place mutation of the shared `Config` object's input records files will trigger side-effects and bugs. A path-mapping or config-cloning strategy is needed.
3. **Documentation Tasks (Factoid Compliance)**: The specification fails to include a documentation update task, which violates the workspace `spec-doc-update-rule` requiring updates to both `README.md` and `docs/reference/` pages (such as `docs/reference/CLI.md`).
4. **Naming Conflicts and Output Discoverability**: Day-only based file naming (`<section>-<YYYYMMDD>.md`) will overwrite previous runs on the same day. Additionally, the default output directory is hidden by default.

With these updates applied, the specification will be solid and ready to proceed.

**Verdict:** ⚠️ **PROCEED WITH UPDATES**

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| **E1** | Engineering | 🎯 **Must-Address** | Failure Mode Analysis | On Windows, `git worktree remove` or folder deletion frequently fails with file locks if handles are held by Python, indexers, or antiviruses. | Implement robust retry-with-backoff logic for directory cleanup and run `git worktree prune` before creation. |
| **E2** | Engineering | 🎯 **Must-Address** | Architecture | Mutating `InputRecord.filepaths` on the shared global `Config` object in-place causes side-effects between base and target extractions. | Provide a method to clone or dynamically derive configuration with remapped bases/paths without mutating the shared config. |
| **E5** | Engineering | 🎯 **Must-Address** | Compliance | The specification lacks a documentation update task, violating the `spec-doc-update-rule` factoid. | Add a new Task 10 to the task breakdown for updating `README.md` and `docs/reference/CLI.md`. |
| **P1** | Product | 💡 **Recommendation** | User Value | Generating one report file per input record forces manual collation of files in multi-input projects. | Add a `--single` or `--combined` report option or generate a master index report summarizing all records. |
| **P2** | Product | 💡 **Recommendation** | Edge Cases & UX | `<section>-<YYYYMMDD>.md` will overwrite reports if the command is run multiple times on the same day. | Include revision identifiers in the filename (e.g. `<section>-<base>-to-<target>-<YYYYMMDD>.md`) or add an `--output-file` option. |
| **P3** | Product | 💡 **Recommendation** | Edge Cases & UX | The default output directory `.syntagmax/reports/change/` is hidden, which hurts discoverability. | Print the absolute paths of all successfully generated report files to the console on command completion. |
| **P4** | Product | 💡 **Recommendation** | Edge Cases & UX | No support is planned for comparing active uncommitted (dirty) working directory changes against a revision. | Document this workflow limitation or support a special `working` revision identifier. |
| **E3** | Engineering | 💡 **Recommendation** | Dependencies | Git worktree commands require Git >= 2.5. CLI lacks validation of the system's Git version on startup. | Add a Git version check on CLI command initialization to verify compatibility. |
| **E4** | Engineering | 💡 **Recommendation** | Performance | `difflib.SequenceMatcher` has $O(N^2)$ complexity and can hang or consume excessive memory on large text files. | Impose length limits on text blocks sent to `SequenceMatcher`, or fall back to line-by-line diffs for large blocks. |

---

## Product Lens Findings

### User Value
* **P1: Fragmented Reports in Multi-Input Projects (Severity: 💡 Recommendation)**
  * *Finding:* Generating one report per input record means that in large projects with multiple configured inputs, the user receives multiple independent markdown files. This requires the user to open and inspect each file separately to understand the overall impact of a change.
  * *Suggestion:* Provide a way to generate a single consolidated change report (e.g. via a `--single` flag) or generate a master summary index report file that lists all processed records and links to their individual reports.

### Edge Cases & UX
* **P2: Output Filename Collision (Severity: 💡 Recommendation)**
  * *Finding:* The file format `<section>-<YYYYMMDD>.md` assumes at most one report is generated per day. If a developer runs reports comparing multiple branches or commits on the same day, they will constantly overwrite their previous files.
  * *Suggestion:* Include short revision hashes or names in the default output filename, e.g., `<section>-<base_rev>-to-<target_rev>-<YYYYMMDD>.md`, or expose an `--output-file` option.

* **P3: Hidden Output Discoverability (Severity: 💡 Recommendation)**
  * *Finding:* The default output directory `.syntagmax/reports/change/` resides inside a dot-folder, which is hidden by default in file browsers (like Windows Explorer or macOS Finder) and standard `ls` outputs.
  * *Suggestion:* In the CLI command execution, print the absolute paths of all generated files to stdout so users can easily copy/paste or open them.

* **P4: Comparing Uncommitted Changes (Severity: 💡 Recommendation)**
  * *Finding:* Developers often want to inspect their uncommitted local changes (dirty working copy) before they commit them. The worktree-based approach checkout of specific revisions does not easily support comparing uncommitted files without stashing.
  * *Suggestion:* Document this limitation in the CLI help, or support a special keyword like `working` for the target revision that bypasses worktree creation and reads the current active files directly.

---

## Engineering Lens Findings

### Architecture Soundness
* **E2: Config Mutation Side-Effects (Severity: 🎯 Must-Address)**
  * *Finding:* The implementation details for Task 2 suggest modifying `InputRecord.filepaths` on the `Config` instance. Because the `Config` object is shared, modifying it in-place during base revision extraction will override the target revision's settings, leading to sequence bugs and data corruption.
  * *Suggestion:* Introduce a clean method to duplicate/clone the `Config` instance, or pass a base path parameter to the extractor that overrides the default base directory resolving, avoiding mutation of the shared `Config` structure.

### Failure Mode Analysis
* **E1: Windows Worktree Deletion Locks (Severity: 🎯 Must-Address)**
  * *Finding:* On Windows, directory deletion commands (`git worktree remove` or python `shutil.rmtree`) frequently fail with permission errors if file handles are held open (e.g., if any of the extractors forgot to close a file stream, or if indexers/antivirus tools lock the files). If cleanups fail, subsequent runs will error with "worktree already exists".
  * *Suggestion:* Use robust try-except wrapper with exponential backoff and retries when removing directories. Close all file handles explicitly in extractors using context managers. Run `git worktree prune` on command startup and shutdown to release stale references.

### Compliance
* **E5: Missing Documentation Tasks (Severity: 🎯 Must-Address)**
  * *Finding:* The task breakdown does not contain any documentation tasks. This violates the `spec-doc-update-rule` workspace factoid: *"Every spec must include a documentation update task that covers ALL relevant documentation: README.md AND docs/reference/ pages. Not just the README."*
  * *Suggestion:* Add `Task 10: Documentation Updates` to the Task Breakdown. This task should cover updating `README.md` and `docs/reference/CLI.md` with options and examples of the new command.

### Performance & Scalability
* **E4: `difflib.SequenceMatcher` Bottleneck (Severity: 💡 Recommendation)**
  * *Finding:* `SequenceMatcher` has a worst-case time complexity of $O(N^2)$. On large narrative documents with thousands of lines, text fragment diffing could hang the CLI or consume high memory.
  * *Suggestion:* Add a fallback limit: if a text block contains more than e.g., 200 lines, skip `SequenceMatcher` and run a fast line-by-line unified diff instead.

### Dependencies & Integration Risks
* **E3: Git Version Compatibility (Severity: 💡 Recommendation)**
  * *Finding:* The `git worktree` command was introduced in Git 2.5. If a user runs the CLI on an older git environment, the subcommand will fail with cryptic Git errors.
  * *Suggestion:* Validate that the Git version is >= 2.5 when the command is initialized, returning a clear error if the version is unsupported.

---

## Cross-Lens Insights

* **Windows Reliability and Onboarding UX (P3 × E1):**
  Providing robust worktree cleanups on Windows (E1) combined with printing the absolute paths of generated reports (P3) ensures that Windows developers have a smooth, error-free experience and can immediately find their files.
* **Config Copying and Performance (E2 × E4):**
  Avoiding config mutation (E2) keeps the extraction state pure and makes it safe to run extraction of the two revisions concurrently (using threading or multiprocessing) in the future to improve performance on large repositories.

---

## Verdict & Action Plan

**Verdict:** ⚠️ **PROCEED WITH UPDATES**

### Specific Edits Suggested

1. **Add new task under Task Breakdown in `docs/specs/change-report.spec.md`:**
   * Append the following task:
     ```markdown
     ---

     ### Task 10: Documentation Updates

     **Objective:** Update all relevant project documentation to cover the new `change report` command.

     **Implementation:**
     - Add command description, options, and usage examples to `README.md`.
     - Update `docs/reference/CLI.md` to document the new `change` group and `report` subcommand.
     - Document default output path and behavior of the `--include-non-artifact` option.

     **Test requirements:** Verify that built/rendered documentation includes the new command details.
     ```

2. **Under Task 1: Worktree Management Utility:**
   * Replace:
     ```markdown
     - `create_worktree(repo: git.Repo, revision: str, label: str) -> Path` — calls `git worktree add`
     - `remove_worktree(repo: git.Repo, path: Path)` — calls `git worktree remove`
     - `resolve_revision(repo: git.Repo, rev_str: str) -> str` — validates and resolves to a commit hash
     - Context manager `worktree_pair(repo, base_rev, target_rev)` that creates both and ensures cleanup
     ```
   * With:
     ```markdown
     - `create_worktree(repo: git.Repo, revision: str, label: str) -> Path` — calls `git worktree add`. Validates system Git version is >= 2.5.
     - `remove_worktree(repo: git.Repo, path: Path)` — calls `git worktree remove`, wrapped in retry-with-backoff logic to handle Windows file locks. Runs `git worktree prune`.
     - `resolve_revision(repo: git.Repo, rev_str: str) -> str` — validates and resolves to a commit hash. Accepts `working` for active uncommitted files if supported.
     - Context manager `worktree_pair(repo, base_rev, target_rev)` that creates both and ensures robust cleanup.
     ```

3. **Under Task 2: Block Extraction at a Specific Revision:**
   * Replace:
     ```markdown
     - `extract_blocks_at_revision(config: Config, worktree_path: Path) -> dict[str, list[FileRecord]]` keyed by input record name
     - Rebuild `InputRecord.filepaths` by re-globbing within the worktree directory
     - Instantiate extractors pointing at worktree paths, call `extract_blocks_from_file` per file
     - Return a per-record mapping of `FileRecord` objects (path → blocks)
     ```
   * With:
     ```markdown
     - `extract_blocks_at_revision(config: Config, worktree_path: Path) -> dict[str, list[FileRecord]]` keyed by input record name
     - Safely clone the `Config` instance or map filepaths to the worktree path without mutating the original `Config` object in-place
     - Re-glob `InputRecord.filepaths` relative to the worktree root path
     - Instantiate extractors pointing at worktree paths, call `extract_blocks_from_file` per file, ensuring all file streams are closed
     - Return a per-record mapping of `FileRecord` objects (path → blocks)
     ```

4. **Under Task 5: Text Block Comparison (Non-Artifact):**
   * Replace:
     ```markdown
     - Use Python's `difflib.SequenceMatcher` to align text blocks by position/content similarity within same file
     ```
   * With:
     ```markdown
     - Use Python's `difflib.SequenceMatcher` to align text blocks by position/content similarity within same file. For blocks exceeding 200 lines, skip `SequenceMatcher` and fall back to standard line-by-line diff to prevent performance bottlenecks.
     ```

5. **Under Task 7: CLI Command Wiring:**
   * Replace:
     ```markdown
     - File naming: `<section>-<YYYYMMDD>.md`
     - Support `--output console` for stdout
     ```
   * With:
     ```markdown
     - File naming: `<section>-<base_rev>-to-<target_rev>-<YYYYMMDD>.md` to avoid date-only file collisions.
     - Output paths: Print the absolute path of each generated report file to stdout on success.
     - Support `--output console` for stdout.
     - Add `--single` / `--combined` option to generate a single consolidated report across all input records.
     ```
