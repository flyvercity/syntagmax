# Critique: Refactor Large Modules Specification

This document presents a critique of [refactor-large-modules.md](../specs/refactor-large-modules.md) using the dual Product and Engineering Lenses framework defined in `.gemini/commands/sc.critique.spec.md`.

---

## Executive Summary

The specification [refactor-large-modules.md](../specs/refactor-large-modules.md) addresses real maintainability debt by splitting two monolithic files (`src/syntagmax/cli.py` and `src/syntagmax/extractors/markdown.py`) and moving domain logic (`_get_working_tree_changed_files`) to `src/syntagmax/change_diff.py`.

Overall assessment: **⚠️ PROCEED WITH UPDATES**. The intent and general approach are sound and necessary for long-term codebase health. However, the proposal to dump 5 unrelated command groups (`trace`, `edit`, `mcp`, `schema`, `ci`) into a single `cli_commands.py` creates a "junk drawer" module that risks exceeding the ~500-line target limit and violates single-responsibility principles. Furthermore, mixin extraction in `extractors/markdown.py` needs explicit type safety and protocol considerations to prevent hidden attribute errors, and initial file line count baselines need updating.

---

## Product Lens Review (CEO / Product Lead Perspective)

### 1a. Problem Validation
- **Clear Problem**: Yes. Large files (1000+ lines) hinder readability, slow down code reviews, and increase merge conflict surface area.
- **Scope & User Impact**: This is an internal technical debt refactoring. It delivers no new user features directly, but protects developer velocity and maintainability.

### 1b. User Value Assessment
- **Value Delivery**: Internal quality improvement. Ensures zero user-facing regressions for CLI commands and document extraction.
- **MVP Analysis**: The proposed 8-task breakdown is well-sequenced, enabling incremental commit and test execution after each step.

### 1c. Alternative Approaches
- **Subcommand Dynamic Discovery vs `add_command()`**: The spec chooses explicit `rms.add_command()` registrations in `cli.py`, which is standard for Click applications and avoids magic import reflection.

### 1d. Edge Cases & User Experience
- **Backward Compatibility**: Entry point `syntagmax.cli:main` in `pyproject.toml` remains unchanged. Subcommand CLI flags and behaviors must remain identical.
- **CLI Startup Overhead**: Top-level eager imports in sub-modules must not slow down basic CLI executions like `syntagmax --version` or `syntagmax --help`.

### 1e. Success Measurement
- Target line count < 500 lines per file.
- 100% of existing unit and integration tests passing.
- Clean `ruff check .` output.

---

## Engineering Lens Review (Staff Engineer Perspective)

### 2a. Architecture Soundness
- **`cli_commands.py` Junk Drawer Anti-Pattern**: Combining `edit` (renumber, attrs, markers), `mcp`, `schema`, `ci`, and `trace` into a single `cli_commands.py` mixes separate domains (editing, MCP server, JSON schema generation, CI setup, and dependency tracing). With `cli.py` currently at 1122 lines, `cli_commands.py` would likely reach 450–550 lines, defeating the ~500-line constraint.
  - *Recommendation*: Split `edit` into `cli_edit.py`, and group developer/tool subcommands (`mcp`, `schema`, `ci`, `trace`) into `cli_tools.py`.
- **Mixin Coupling & Type Safety**: Extracting `MarkerSplitterMixin` and `ElementFilterMixin` for `MarkdownExtractor` creates cross-mixin dependencies on `self` (e.g. access to `self.config`, `self.builder`, `self._find_segment_boundary`).
  - *Recommendation*: Use `typing.Protocol` or clear type annotations on `self` within mixins to ensure static analyzers (Mypy/Pyright/Ruff) validate attribute existence cleanly.

### 2b. Operational Readiness & Baseline Accuracy
- **Line Count Discrepancy**: The spec notes `cli.py` as 922 lines and `extractors/markdown.py` as 1057 lines. The current codebase has `cli.py` at 1122 lines and `extractors/markdown.py` at 1259 lines. The spec baselines should be updated to reflect current numbers.

### 2c. Dependencies & Integration Risks
- **CLI Utility Isolation**: `_read_file_safe` and `_generate_fallback_diff` are currently placed into `cli_change.py`. If other modules need file reading or diff fallbacks, placing them in `cli_change.py` risks tight coupling. Common CLI helpers should be placed in `cli_utils.py` or re-used from `syntagmax.utils`.

### 2d. Testing Strategy
- **Brittle Test Count Assertion**: Hardcoding "803 tests" in the spec requirements and task list creates brittle assertions. The spec should mandate that 100% of the test suite passes dynamically.
- **Import Audit**: Test files importing internal functions (such as `_get_working_tree_changed_files` or `apply_soft_line_breaks`) must be audited to ensure updated import paths or re-exports in parent modules work without breaking tests.

---

## Cross-Lens Synthesis

- **Architecture Simplification × Risk Reduction**: Splitting `cli_edit.py` separately from `cli_tools.py` improves domain isolation (Product & Engineering benefit) and guarantees all files stay well below the 400-line mark.
- **Type Safety × Developer Velocity**: Protocol typing for mixins prevents subtle runtime `AttributeError` regressions during extraction, supporting smooth refactoring.

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|---|---|---|---|---|---|
| **E1** | Engineering | 🎯 | Architecture Soundness | `cli_commands.py` becomes a catch-all junk drawer combining 5 unrelated domain groups (`edit`, `mcp`, `schema`, `ci`, `trace`), risking high file size (~500+ lines). | Separate `edit` group into `cli_edit.py` and remaining tool commands into `cli_tools.py`. |
| **E2** | Engineering | 🎯 | Architecture Soundness | Mixin classes (`MarkerSplitterMixin`, `ElementFilterMixin`) introduce implicit cross-mixin dependencies on `self` without type annotations or Protocol interfaces. | Add `typing.Protocol` interfaces or explicit type hints for `self` in mixins to ensure clean static analysis. |
| **E3** | Engineering | 💡 | Operational Readiness | Baseline line counts in spec (`cli.py` 922, `markdown.py` 1057) are outdated compared to current codebase (`cli.py` 1122, `markdown.py` 1259). | Update spec with actual baseline line counts (1122 / 1259 lines) to accurately project target module sizes. |
| **P1** | Product | 💡 | User Value Assessment | Pure internal refactoring creates regression risk for CLI commands and markdown parsing with zero user-facing functionality changes. | Ensure strict regression testing via full test suite, CLI sanity checks, and CLI `--help` latency verification. |
| **E4** | Engineering | 💡 | Testing Strategy | Spec hardcodes test count "803", which creates brittle spec assertions if tests are added/removed. | Reference "100% pass rate of the test suite" dynamically rather than hardcoding exact numbers. |
| **E5** | Engineering | 💡 | Dependencies & Integration | Moving CLI helpers (`_read_file_safe`, `_generate_fallback_diff`) into `cli_change.py` may cause tight cross-module coupling if needed elsewhere. | Place shared CLI helpers in `cli_utils.py` or `syntagmax.utils`. |

---

## Verdict

### ⚠️ PROCEED WITH UPDATES

Must-address architectural items (E1: CLI commands decomposition into cohesive modules, E2: Mixin Protocol/typing safety) and recommendations (E3: Baseline line count updates, E4: Dynamic test count assertions) have been identified. They can be readily incorporated into `docs/specs/refactor-large-modules.md` before starting implementation.

---

## Proposed Remediation (Suggested Spec Updates)

Below are specific proposed edits to `docs/specs/refactor-large-modules.md`:

### 1. Update Baseline Line Counts & Split Plan
Update Problem Statement and CLI Split table:
- `cli.py` baseline: 1122 lines
- `extractors/markdown.py` baseline: 1259 lines
- Split `cli.py` into 5 modules instead of 4:
  - `cli.py`: Root group (`rms`), `init`, `analyze`, `main()`, imports + `add_command()`
  - `cli_publish.py`: `publish` command and pandoc/image helpers
  - `cli_change.py`: `change` group (`report`, `baseline`)
  - `cli_edit.py`: `edit` group (`renumber`, `attrs`, `markers`)
  - `cli_tools.py`: `trace`, `mcp`, `schema`, `ci` groups

### 2. Mixin Protocol Definition
Add explicit guidelines under Markdown Extractor Split:
- Define `MarkdownExtractorProtocol` or type annotations for `self` in `MarkerSplitterMixin` and `ElementFilterMixin` so IDEs and linters recognize inherited attributes (`config`, `builder`, etc.) without type errors.

### 3. Dynamic Test Verification
Update Requirements and Task Breakdown:
- Replace "All 803 tests" with "100% of the test suite must pass".
