# Specification: Refactor Large Modules (cli.py, extractors/markdown.py)

## Problem Statement

Two source files have grown too large:
- `src/syntagmax/cli.py` — 1122 lines
- `src/syntagmax/extractors/markdown.py` — 1259 lines

They need to be split into smaller, cohesive modules while preserving all existing behaviour and tests.

## Requirements

- Split `cli.py` into 5 modules using `rms.add_command()` pattern
- Split `extractors/markdown.py` into 3 modules using mixin classes with Protocol-based type safety
- Move `_get_working_tree_changed_files` from `cli.py` to `change_diff.py` (domain logic, not CLI glue)
- 100% of the test suite must pass after each task
- Ruff linter must remain clean
- No file should exceed ~500 lines after refactoring

## Background

- Entry point is `syntagmax.cli:main` (declared in `pyproject.toml`)
- No `__init__.py` files exist; this is a flat namespace package
- CLI uses Click with groups (`change`, `edit`, `mcp`, `schema`, `ci`) and top-level commands (`analyze`, `publish`, `trace`, `init`)
- `MarkdownExtractor` is a monolithic class with marker-splitting, filtering, and core extraction logic

## Proposed Solution

### CLI Split

| Module | Contents | Estimated Lines |
|--------|----------|-----------------|
| `cli.py` | Root group (`rms`), `init`, `analyze`, `main()`, imports + `add_command()` registrations | ~120 |
| `cli_publish.py` | `publish` command, `_run_pandoc_conversion`, `_copy_manifest_images`, template resolution | ~240 |
| `cli_change.py` | `change` group with `report` and `baseline` subcommands | ~280 |
| `cli_edit.py` | `edit` group (`renumber`, `attrs`, `markers` subcommands) | ~180 |
| `cli_tools.py` | `trace`, `mcp` group, `schema` group, `ci` group (install analyze, install publish) | ~300 |

Registration in `cli.py`:

```python
from syntagmax.cli_publish import publish
from syntagmax.cli_change import change
from syntagmax.cli_edit import edit
from syntagmax.cli_tools import trace, mcp, schema, ci

rms.add_command(publish)
rms.add_command(change)
rms.add_command(trace)
rms.add_command(edit)
rms.add_command(mcp)
rms.add_command(schema)
rms.add_command(ci)
```

### Markdown Extractor Split

| Module | Contents | Estimated Lines |
|--------|----------|-----------------|
| `extractors/markdown.py` | `MarkdownExtractor` class (init, `_find_segment_boundary`, `_process_segment`, `_extract_blocks_from_markdown`, `extract_blocks_from_file`, `update_artifacts`, `update_artifact`, `update_artifact_attributes`, `_update_yaml_attrs`, `_update_inline_fields`, `_insert_inline_field`, `_extract_from_markdown`), `MarkdownArtifact`, `MarkdownTransformer` | ~550 |
| `extractors/markdown_markers.py` | Mixin class `MarkerSplitterMixin` with: `_split_text_block_by_markers`, `_apply_marker_pass`, `_split_closed_paired`, `_split_unclosed_paired`, `_split_line_prefix`, `_split_headings` | ~350 |
| `extractors/markdown_filters.py` | Mixin class `ElementFilterMixin` with: `_apply_element_filters`, `_filter_text_content`, `_mask_code_spans`, `_line_has_tag`, `_line_starts_with_tag`, `_strip_tags_from_line`; top-level helpers (`apply_soft_line_breaks`, `_is_block_element`, `_validate_block_id`) | ~350 |

`MarkdownExtractor` will inherit from both mixins:

```python
class MarkdownExtractor(MarkerSplitterMixin, ElementFilterMixin, Extractor):
    ...
```

### Mixin Type Safety

Each mixin defines a `typing.Protocol` specifying the attributes it requires from the host class. This ensures static analysers (Ruff, Pyright) validate attribute access without runtime overhead:

```python
from typing import Protocol, TYPE_CHECKING
import re

if TYPE_CHECKING:
    from syntagmax.config import InputRecord, ExcludeElementConfig

class _MarkerSplitterHost(Protocol):
    """Protocol for attributes that MarkerSplitterMixin expects on self."""
    _record: 'InputRecord'
    _closed_paired_re: re.Pattern[str] | None
    _unclosed_paired_re: re.Pattern[str] | None
    _line_prefix_re: re.Pattern[str] | None

class MarkerSplitterMixin:
    """Mixin providing marker-splitting logic for MarkdownExtractor."""
    # Type annotation for self to satisfy static analysis
    if TYPE_CHECKING:
        _record: 'InputRecord'
        _closed_paired_re: re.Pattern[str] | None
        _unclosed_paired_re: re.Pattern[str] | None
        _line_prefix_re: re.Pattern[str] | None
    ...
```

The same pattern applies to `ElementFilterMixin`.

### Domain Logic Move

`_get_working_tree_changed_files` moves to `change_diff.py` as `get_working_tree_changed_files` (public function). The CLI change module imports it from there.

### Shared CLI Helpers

`_read_file_safe` and `_generate_fallback_diff` remain in `cli_change.py` as they are specific to change report generation and not used elsewhere. If future need arises, they can be promoted to `syntagmax.utils`.

## Task Breakdown

### Task 1: Create `extractors/markdown_filters.py`

- Move `apply_soft_line_breaks`, `_is_block_element`, `_validate_block_id` as module-level functions
- Move all compiled regexes used by these functions (`_VALID_BLOCK_ID_RE`, `_HEADING_RE`, `_TABLE_ROW_RE`, `_UNORDERED_LIST_RE`, `_ORDERED_LIST_RE`, `_THEMATIC_BREAK_RE`, `_HTML_BLOCK_RE`, `_FENCE_START_RE`, `_FRONTMATTER_PATTERN`, `_TAG_PATTERN`, `_CODE_SPAN_RE`, `_HR_PATTERN`, `_CALLOUT_ONLY_RE`, `_HEADING_ONLY_RE`, `_MULTIPLE_WS_RE`)
- Create `ElementFilterMixin` class with TYPE_CHECKING annotations for `self._record`, `self._config`
- Include methods: `_apply_element_filters`, `_filter_text_content`, `_mask_code_spans`, `_line_has_tag`, `_line_starts_with_tag`, `_strip_tags_from_line`
- Test: Run `pytest tests` — 100% must pass

### Task 2: Create `extractors/markdown_markers.py`

- Create `MarkerSplitterMixin` class with TYPE_CHECKING annotations for `self._record`, `self._closed_paired_re`, `self._unclosed_paired_re`, `self._line_prefix_re`
- Include methods: `_split_text_block_by_markers`, `_apply_marker_pass`, `_split_closed_paired`, `_split_unclosed_paired`, `_split_line_prefix`, `_split_headings`
- Move `_HEADING_RE_SPLIT` regex to this module
- Import `_validate_block_id` from `markdown_filters`
- Test: Run `pytest tests` — 100% must pass

### Task 3: Update `extractors/markdown.py` to use mixins

- Change `MarkdownExtractor` to inherit from `MarkerSplitterMixin`, `ElementFilterMixin`, and `Extractor`
- Remove methods and regexes that now live in mixin modules
- Re-export `apply_soft_line_breaks` from `markdown_filters` so existing imports continue to work
- Test: Run `pytest tests` — 100% must pass
- Verify: Audit test imports of `apply_soft_line_breaks` and update if needed

### Task 4: Move `_get_working_tree_changed_files` to `change_diff.py`

- Rename to `get_working_tree_changed_files` (public)
- Add it to `change_diff.py` with appropriate imports
- Update CLI code to import from `change_diff`
- Test: Run `pytest tests` — 100% must pass

### Task 5: Create `cli_publish.py`

- Move `publish` Click command function and helpers (`_run_pandoc_conversion`, `_copy_manifest_images`)
- Template resolution logic stays as a nested helper within the command or becomes a module-level function
- Export the `publish` command for `add_command()` registration
- Test: Run `pytest tests` — 100% must pass

### Task 6: Create `cli_change.py`

- Move `change` group and its subcommands (`report`, `baseline`)
- Move `_read_file_safe`, `_generate_fallback_diff`
- Import `get_working_tree_changed_files` from `change_diff`
- Export the `change` group for registration
- Test: Run `pytest tests` — 100% must pass

### Task 7: Create `cli_edit.py`

- Move `edit` group and its subcommands (`renumber`, `attrs`, `markers`)
- Export the `edit` group for registration
- Test: Run `pytest tests` — 100% must pass

### Task 8: Create `cli_tools.py`

- Move `trace` command, `mcp` group, `schema` group, `ci` group (install analyze, install publish)
- Export each top-level command/group for registration
- Test: Run `pytest tests` — 100% must pass

### Task 9: Update `cli.py` to register sub-modules via `add_command()`

- Remove all moved code from `cli.py`
- Import commands/groups from `cli_publish`, `cli_change`, `cli_edit`, `cli_tools`
- Register with `rms.add_command()`
- Keep `rms` group, `init`, `analyze`, and `main()` in place
- Test: Run `pytest tests` — 100% must pass; run `ruff check .`

### Task 10: Final verification and cleanup

- Run `ruff check .` — no errors
- Run `pytest tests` — 100% pass rate
- Verify line counts: no file exceeds ~500 lines
- Verify CLI startup: `syntagmax --help` displays all commands correctly
- All CLI entry points work as before

## Documentation Updates

- Update `README.md` if any import paths are mentioned (none currently)
- No docs/reference pages reference internal module layout — no changes needed

## Risks

- Circular imports: mitigated by the mixin pattern (mixins don't import from `markdown.py`)
- Click command discovery: `add_command()` is the standard Click pattern for multi-file CLIs
- Re-exports: `apply_soft_line_breaks` must remain importable from its current path if used externally (checked: only used internally within the extractors package and in tests for `strict_line_breaks`)
- CLI startup latency: sub-modules use lazy imports (inside command functions) for heavy dependencies, preserving fast `--help` and `--version` responses
