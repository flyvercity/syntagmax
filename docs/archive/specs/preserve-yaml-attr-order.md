# Specification: Preserve YAML Attribute Order in Editing Commands

## Problem Statement

The `edit attrs` and `edit renumber` commands re-emit YAML blocks using `benedict.to_yaml()`, which sorts keys alphabetically. This produces noisy git diffs and destroys the user's intentional attribute ordering. This is neither user-friendly nor git-friendly.

## Requirements

- YAML attribute blocks must preserve their original key order after editing
- Comments within YAML blocks should be preserved (currently warned about and lost)
- The fix applies to both `_update_yaml_attrs` (attrs command) and `update_artifacts` (renumber command)
- Existing tests must continue passing
- New tests must verify order preservation

## Background

- Two call sites in `src/syntagmax/extractors/markdown.py` use `yaml_data.to_yaml()`: line 137 (renumber) and line 287 (attrs)
- The raw YAML text is available in each segment between `` ```yaml `` and `` ``` `` markers
- `ruamel.yaml` provides round-trip parsing that preserves key order, comments, and formatting
- The project already depends on `pyyaml` and `python-benedict[yaml]`; `ruamel.yaml` will be an additional dependency
- The `MarkdownArtifact.yaml_data` field is typed as `benedict | None` — but this is only used for data access during extraction and attribute checks. The editing path can work with the raw YAML text directly using ruamel.

## Proposed Solution

Introduce a `yaml_utils.py` module that wraps `ruamel.yaml` round-trip operations (load/modify/dump). Replace both `to_yaml()` call sites in `markdown.py` to use round-trip editing: parse the raw YAML from the segment, apply the modification, dump back preserving order and comments. This avoids changing the `yaml_data` field type on `MarkdownArtifact` (which would be a much larger refactor).

**Design note:** The in-memory `MarkdownArtifact.yaml_data` (benedict-based) is intentionally NOT synchronized with the written file during editing. Since the CLI executes a single command and exits, updating the written file is sufficient. This trade-off should be documented in a code comment to prevent future developers from assuming the in-memory objects stay in sync.

## Task Breakdown

### Task 1: Add `ruamel.yaml` dependency and create `yaml_utils.py` helper module

- **Objective:** Add `ruamel.yaml` to `pyproject.toml` and create a utility module with functions for round-trip YAML editing.
- **Implementation guidance:**
  - Add `"ruamel.yaml>=0.18.0"` to `dependencies` in `pyproject.toml`
  - Create `src/syntagmax/yaml_utils.py` with a single unified utility function:
    - `roundtrip_modify_attrs(raw_yaml: str, attrs_delta: dict[str, Any], operation: str) -> str`
  - Inside `roundtrip_modify_attrs`:
    - Parse `raw_yaml` using `ruamel.yaml.YAML(typ='rt')`.
    - Catch `ruamel.yaml.error.YAMLError` and raise a custom exception (e.g., `YAMLParsingError`) to allow callers to report clear errors.
    - Verify if the `attrs` key is present; if missing or null, initialize it to an empty `CommentedMap`.
    - Apply changes to `attrs` based on `operation` (`add`, `del`, `replace`):
      - `add`: Insert key/value if not already present.
      - `del`: Remove key if present.
      - `replace`: Set key/value if value is not None, else remove it.
    - Serialize the output back to a string, ensuring line endings match the format of the input.
  - The function takes raw YAML text (without the `` ```yaml `` fences) and returns modified YAML text
- **Test requirements:** Unit tests for `yaml_utils.py` verifying:
  - Key order is preserved when adding a new attr
  - Key order is preserved when replacing a value
  - Key order is preserved when deleting a key
  - Comments are preserved
  - List values (like `tag: [a, b]`) round-trip correctly
- **Demo:** Tests pass demonstrating order-preserving YAML editing in isolation

### Task 2: Refactor `_update_yaml_attrs` to use round-trip editing

- **Objective:** Replace the `benedict.to_yaml()` call in `_update_yaml_attrs` with the new `yaml_utils` functions, operating on the raw YAML text from the segment.
- **Implementation guidance:**
  - Extract raw YAML from segment (between `` ```yaml\n `` and `` \n``` ``)
  - Apply modifications using `yaml_utils.roundtrip_modify_attrs(raw_yaml, attrs_delta, operation)`
  - Catch `YAMLParsingError`, log a user-friendly error with the artifact's ID and filename, and skip the artifact.
  - Re-wrap with fences and inject back into segment
  - When no YAML block exists (new block creation), fall back to current behavior (building from scratch is fine since there's no order to preserve)
  - Remove the warning about comment loss (it's now preserved)
- **Test requirements:**
  - Existing `test_yaml_add_new_attr`, `test_yaml_del_removes_attr`, `test_yaml_replace_updates_existing` tests pass
  - New test: `test_yaml_attr_order_preserved` — add attribute to a block with 5+ attrs, verify output order matches input order
  - New test: `test_yaml_comments_preserved` — YAML block with inline/above comments survives editing
- **Demo:** Run `syntagmax edit attrs -s requirements -n owner --dry-run` on the example project, confirm output wouldn't re-sort existing attributes

### Task 3: Refactor `update_artifacts` (renumber) to use round-trip editing

- **Objective:** Replace the `yaml_data.to_yaml()` call in `update_artifacts` with round-trip editing that only modifies the `id` field.
- **Implementation guidance:**
  - Extract raw YAML from segment (same pattern as Task 2)
  - Use `yaml_utils.roundtrip_modify_attrs(raw_yaml, {'id': new_id}, 'replace')` to update only the `id` key
  - Catch `YAMLParsingError`, log a user-friendly error, and skip the artifact.
  - Re-wrap and replace in segment
  - Keep the fallback path (no yaml_data, regex-based) unchanged
- **Test requirements:**
  - Existing renumber tests pass
  - New test: `test_renumber_preserves_yaml_order` — renumber an artifact with ordered attrs, verify only `id` value changes
- **Demo:** Run the renumber quick demo and inspect the output file to confirm only IDs changed, no attribute re-ordering

### Task 4: Integration test and cleanup

- **Objective:** End-to-end verification and removal of unused code paths.
- **Implementation guidance:**
  - Add an integration test that reads a sample file, runs `edit attrs` (add + replace + del in sequence), and asserts the final file only differs in the expected attributes
  - Remove the YAML comment warning (`lg.warning(...contains comments...)`) since comments are now preserved
  - Verify `benedict` is still needed for other purposes (extraction, data access) — do NOT remove it
  - Run `ruff` and full test suite
- **Test requirements:** Full test suite green, no regressions
- **Demo:** Full round-trip test — edit attrs on the example project, `git diff` shows only the intended attribute changes with no reordering
