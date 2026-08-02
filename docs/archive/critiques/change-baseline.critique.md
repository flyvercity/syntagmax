# Specification Critique: `syntagmax change baseline` Command

This critique evaluates [change-baseline.spec.md](../specs/change-baseline.spec.md) through the Product Lens (CEO/Product Lead perspective) and Engineering Lens (Staff Engineer perspective) to identify gaps, risks, and areas for improvement before implementation.

---

## Executive Summary

The specification presents a solid design for a `change baseline <tag-name>` command. The proposed feature addresses a crucial need for multi-repository requirements management by allowing consistent tagging across all repositories referenced by input records.

The core flow is well-defined, and the pre-flight check phase is structured to ensure correctness before writing changes. However, several critical gaps must be addressed before proceeding to implementation to ensure true atomicity, usability, and safety:
1. **Rollback Mechanism**: True atomicity is promised, but tag creation is not a transactional operation. If tagging fails mid-loop, the system is left in a partially tagged state unless rollback logic is added.
2. **Safety and Boundaries**: GitPython's default parent directory search (`search_parent_directories=True`) may escape the project boundary and tag parent repositories (e.g. user home directories). We must restrict discovery to repositories within the project base directory.
3. **User Experience (UX)**: A dry-run preview is essential for destructive git operations. Additionally, creating local tags is incomplete without pushing; a push option or a clear reminder should be provided.
4. **Configuration Generation**: The template configuration generator (`init_cmd.py`) needs updating to properly handle the new config schema section.

With these updates addressed, the implementation will be robust and ready to proceed.

---

## Product Lens Findings

### 1b. User Value Assessment & Workflow Completeness
* **No Tag Pushing Option**: In a multi-repo setup, local git tags are only useful if shared. The spec defines local tag creation but does not mention pushing them to a remote repository (like `origin`). Without a mechanism to push, users must manually navigate to each repository to run `git push origin <tag-name>`.
  * *Solution*: Provide a clear message after successful tagging reminding the user to push the new baseline tags to their remotes, or add an optional `--push` flag to push them automatically.
* **Lack of Dry-Run Preview**: Altering git tags across multiple repositories is a significant operation. Standard Syntagmax commands support `--dry-run` to let users verify actions before they are executed.
  * *Solution*: Add a `--dry-run` flag to the CLI command. When enabled, the tool discovers repos and runs all validation steps without executing any tag modifications.

### 1d. Edge Cases & User Experience
* **Empty Discovery Set**: If no input records are configured, or if none of them map to directories containing git repositories, the command should handle this gracefully rather than failing with a generic traceback.
  * *Solution*: Explicitly validate that the set of discovered repositories is not empty, and raise a clear `FatalError` if it is.

---

## Engineering Lens Findings

### 2a. Failure Mode Analysis & Rollback
* **Lack of Tag Rollback on Failure**: The spec claims "Atomic behavior: validates all preconditions... **before** creating any tags". While validations are performed upfront, runtime errors (e.g., git lock issues, write permissions, or missing commit references) can still occur during the tag creation loop. If tagging fails on repo 3 out of 5, the first two repos will remain tagged, leaving the system in an inconsistent state.
  * *Solution*: Wrap the tag creation loop in a try/except block. If any repository fails to tag, catch the error, iterate back over the repositories that were successfully tagged during this execution, delete the newly created tags, and then raise the `FatalError`.

### 2b. Security & Boundaries
* **Traversing Beyond Project Base Directory**: Discovering git repositories with `search_parent_directories=True` on `record_base` paths runs the risk of discovering and tagging an unintended parent repository (e.g. a Git repository in the user's home folder) if an input record's path is not within a project-level repository.
  * *Solution*: Validate that the resolved `working_tree_dir` of each discovered repository is located under (or equal to) the project's base directory (`config.base_dir()`). Raise a `FatalError` if any repository escapes this project boundary.

### 2e. Testing Strategy
* **Empty Repository Tagging**: Git cannot create tags in a repository that has no commits (no `HEAD` reference). Task 6 (E2E tests) should specify that helper repositories must have at least one commit (e.g. initialized with a dummy file commit) before tagging is attempted.
  * *Solution*: Clarify in Task 6 that test setups must create at least one commit in all test repositories.

### 2f. Operational Readiness
* **Template Generator Alignment**: Syntagmax includes a template generator in [init_cmd.py](../../src/syntagmax/init_cmd.py) that iterates over `ConfigFile` models to produce a default `.syntagmax/config.toml`. Adding `baseline` to `ConfigFile` without updating the template generator could result in a malformed default configuration file.
  * *Solution*: Exclude `baseline` from default fields in `generate_toml()` and add a commented `[baseline]` section block to the generated string.

### 2g. Dependencies & Integration Risks
* **Regex Compilation Validation**: An invalid regex string in the `tag_pattern` configuration will raise an error when the baseline command runs. This should be validated at configuration load time.
  * *Solution*: Add a `@field_validator` in `BaselineConfig` to compile `tag_pattern` using `re.compile()` and raise a validation error if it is invalid.

---

## Cross-Lens Insights

### X1: CLI Dry-Run and Push Features
* **Product Aspect**: Dry-run gives users the confidence to verify multi-repo baselines before taking action, and tag pushing completes the developer workflow.
* **Engineering Aspect**: Separating validation/dry-run checks from execution minimizes the likelihood of mid-execution failures, and implementing a dry-run flag allows safe testing of the command path.

### X2: Atomic Rollback Guarantee
* **Product Aspect**: Ensures repository state stays consistent across the workspace. Users do not need to manually delete tags across several repos if one fails.
* **Engineering Aspect**: Provides a transaction-like wrapper around GitPython write operations, improving reliability and robustness.

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| **E1** | Engineering | 🎯 | Failure Modes | Tag creation loop lacks rollback logic; a mid-loop failure leaves the workspace in a partially-tagged state. | Wrap the tag creation loop in a try/except block that deletes newly created tags on failure. |
| **E2** | Engineering | 💡 | Boundaries | `search_parent_directories=True` could find and tag a parent repository outside the project base directory. | Validate that all resolved repository roots are subdirectories of or equal to `config.base_dir()`. |
| **P1** | Product | 💡 | UX | The command only creates local tags, leaving the user to figure out that they must manually push them. | Suggest a reminder message in console output to push tags, and/or add an optional `--push` flag. |
| **P2** | Product | 💡 | UX | No `--dry-run` flag is defined to preview changes before mutating git repositories. | Add a `--dry-run` flag to the Click command and support it in the tagging logic. |
| **P3** | Product | 💡 | Edge Cases | If no git repositories are discovered, behavior is not explicitly defined. | Raise a `FatalError` if the discovered repository set is empty. |
| **E3** | Engineering | 💡 | Operational | Adding `baseline` to `ConfigFile` without modifying [init_cmd.py](../../src/syntagmax/init_cmd.py) affects TOML template generation. | Update [init_cmd.py](../../src/syntagmax/init_cmd.py) to ignore `baseline` in `ConfigFile` fields iteration and add it as a template section. |
| **E4** | Engineering | 💡 | Testing | Task 6 does not specify creating a commit in test repos before tagging, which will cause git errors. | Ensure E2E test setup creates a commit in each test repository. |
| **E5** | Engineering | 💡 | Validation | Invalid regex in `tag_pattern` configuration is not validated on configuration load. | Add a `@field_validator` to `BaselineConfig` in `config.py` to compile `tag_pattern` and raise ValueError on error. |

---

## Verdict

⚠️ **PROCEED WITH UPDATES**

---

## Offer Remediation

Here are the specific suggested updates to [change-baseline.spec.md](../specs/change-baseline.spec.md):

### Proposed Spec Modification

```diff
--- docs/specs/change-baseline.spec.md
+++ docs/specs/change-baseline.spec.md
@@ -14,5 +14,7 @@
 5. Optional `tag_pattern` regex in `[baseline]` section of `config.toml` — rejects tag names that don't match
 6. `--force` flag to overwrite existing tags; without it, errors if tag already exists in any repo
 7. Atomic behavior: validates all preconditions (dirty check, tag existence, regex) across all repos **before** creating any tags
+8. `--dry-run` flag to preview actions without creating tags
+9. Rollback behavior: if tag creation fails on any repo during execution, all tags created during this run are deleted to preserve atomicity
 
 ## Design Decisions
 
@@ -25,2 +27,4 @@
 | 5 | Tag type | Annotated with optional message. Default: "Baseline created by Syntagmax", override via `--message` |
 | 6 | Target commit | Always HEAD of each repo |
+| 7 | Boundary check | Repositories must be located within `config.base_dir()`. Escaping it raises FatalError. |
+| 8 | Post-creation push | Success summary prints a reminder to push tags (`git push origin <tag>`). |
 
 ## Context
@@ -40,11 +44,14 @@
 ## Flow
 
 ```
-Parse CLI args: tag-name, --message, --force
+Parse CLI args: tag-name, --message, --force, --dry-run
     → Load Config
     → Discover distinct repos from input_records
+    → Validate: At least one repo found?
+    → Validate: Repos lie within project base directory?
     → Validate: All repos clean?
         No → FatalError: list dirty repos
     → Validate: tag_pattern configured?
         Yes → Tag name matches regex?
             No → FatalError: tag doesn't match pattern
     → Validate: Tag exists in any repo?
         Yes, no --force → FatalError: tag exists in repos X, Y
-    → Create annotated tags at HEAD in all repos
-    → Success output: list repos tagged
+    → If --dry-run: Print plan and exit
+    → Create annotated tags at HEAD in all repos
+        On failure: Delete tags created in this run, raise FatalError
+    → Success output: list repos tagged + push reminder
 ```
 
 ## File Changes
@@ -62,4 +69,5 @@
 - `src/syntagmax/cli.py` — add `baseline` subcommand to the `change` group
 - `src/syntagmax/config.py` — add `BaselineConfig` pydantic model and wire it into `ConfigFile`
+- `src/syntagmax/init_cmd.py` — handle new `BaselineConfig` in default TOML template generator
 
 ## Configuration
@@ -82,4 +90,5 @@
   Arguments:
     tag-name              Tag name to create in all repos
   
   Options:
     -m, --message TEXT    Tag annotation message (default: "Baseline created by Syntagmax")
     --force               Overwrite existing tags
+    --dry-run             Preview changes without modifying files
     -f, --config-file     Path to config file (default: .syntagmax/config.toml)
@@ -90,4 +99,5 @@
 
 ### Task 1: Add `BaselineConfig` to the config model
 
 - **Objective:** Add a `[baseline]` section to `config.toml` schema with an optional `tag_pattern` field.
 - **Implementation:** Add a `BaselineConfig` pydantic model with `tag_pattern: str | None = None`. Add it to `ConfigFile` as `baseline: BaselineConfig = Field(default_factory=BaselineConfig)`. Expose it via a property on `Config`.
+- Add a `@field_validator('tag_pattern')` that compiles the regex and raises ValueError if invalid.
+- Update `src/syntagmax/init_cmd.py` `generate_toml()` to ignore `baseline` in `ConfigFile` fields iteration and append a commented `[baseline]` section.
 - **Test:** Unit test that config loads with and without `[baseline]` section; test that invalid regex raises a validation error.
@@ -98,4 +108,5 @@
 
 - **Objective:** Given a list of `InputRecord` objects, discover the set of distinct git repos they belong to.
 - **Implementation:** Create `src/syntagmax/change_baseline.py`. Implement `discover_repos(input_records: list[InputRecord]) -> dict[Path, git.Repo]` that iterates `record_base` paths, calls `git.Repo(path, search_parent_directories=True)`, deduplicates by resolved `working_tree_dir`, and returns a mapping of `repo_root → Repo`.
+- Check that each repo root is a subdirectory of or equal to `config.base_dir()`. Raise `FatalError` if it traverses outside. Raise `FatalError` if the discovered dict is empty.
 - **Test:** Test with records in one repo → returns 1 entry. Test with records in two different repos → returns 2 entries. Test with a record not in any repo → raises `FatalError`.
@@ -107,5 +118,5 @@
 
 - **Objective:** Validate all preconditions before any tag is created.
 - **Implementation:** In `change_baseline.py`, implement:
   - `check_repos_clean(repos: dict[Path, git.Repo])` — checks `repo.is_dirty() or len(repo.untracked_files) > 0` for each, raises `FatalError` listing all dirty repos.
   - `validate_tag_name(tag_name: str, pattern: str | None)` — compiles regex, matches tag_name, raises `FatalError` if no match.
   - `check_tag_exists(tag_name: str, repos: dict[Path, git.Repo], force: bool)` — checks if tag exists in any repo; if it does and `--force` is not set, raises `FatalError` listing repos.
 - **Test:** Test dirty detection (staged, unstaged, untracked). Test regex validation (match/no-match/no-pattern). Test tag-exists with and without force.
@@ -117,4 +128,5 @@
 
 - **Objective:** Create annotated tags at HEAD in all discovered repos.
 - **Implementation:** Implement `create_baseline_tag(tag_name: str, repos: dict[Path, git.Repo], message: str, force: bool)`. For each repo, use `repo.create_tag(tag_name, message=message, force=force)`. If `force`, delete existing tag first then create (GitPython's `create_tag` with `force=True` handles this).
+- Wrap the tag creation loop in a try/except block. If creation fails on any repository, delete the newly created tags in already processed repositories during this run to roll back.
 - **Test:** Test tag creation in single repo. Test tag creation across two repos. Test force-overwrite of existing tag. Verify tag is annotated with correct message. Verify rollback on error.
@@ -124,5 +136,5 @@
 
 - **Objective:** Add `syntagmax change baseline <tag-name>` with `--message`, `--force`, and `-f/--config-file` options.
 - **Implementation:** In `cli.py`, add a `@change.command('baseline')` with:
   - `tag_name` argument
   - `--message` / `-m` option (default: "Baseline created by Syntagmax")
   - `--force` flag
+  - `--dry-run` flag
   - `-f, --config-file` option (default `.syntagmax/config.toml`)
-  - Load config, call `discover_repos`, run all validations, then `create_baseline_tag`. Print success summary listing each repo and its tagged commit.
+  - Load config, call `discover_repos`, run all validations. If `--dry-run`, print the planned repositories and exit. Otherwise, call `create_baseline_tag`. Print success summary listing each repo, its tagged commit, and a push reminder.
 - **Test:** Integration test using `CliRunner` — single repo happy path, multi-repo happy path, dirty repo error, regex mismatch error, existing tag error, `--force` override.
@@ -136,3 +149,3 @@
 
 - **Objective:** Full integration test simulating the real use case — two repos with input records, baseline created consistently.
 - **Implementation:** Create a test that sets up two git repos in `tmp_path`, writes a `config.toml` with input records pointing to both, runs the baseline command via `CliRunner`, and verifies tags exist in both repos with correct messages.
+- Ensure test setup commits at least one file to each repo before tagging.
 - **Test:** Verify tags exist. Verify atomic failure (if second repo is dirty, no tag is created in the first either).
```
