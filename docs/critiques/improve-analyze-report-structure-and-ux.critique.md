# Critique Report: Improve Analyze Report Structure and UX Specification

**Target Spec:** `docs/specs/improve-analyze-report-structure-and-ux.spec.md`  
**Date:** 2026-08-04  
**Evaluator:** Antigravity AI (Product & Engineering Lenses)

---

## Executive Summary

The **Improve Analyze Report Structure and UX** specification (`docs/specs/improve-analyze-report-structure-and-ux.spec.md`) addresses a major usability bottleneck in `syntagmax`: when analyzing large requirement sets (150+ errors across multiple inputs), flat, unnumbered error lists and non-clickable paths make debugging cumbersome.

The overall design direction — introducing a structured `ReportError` dataclass, error grouping by input record and category, Jinja2 link formatting, and per-input metrics — is sound and well-aligned with user needs. 

However, critical gaps were identified during review:
1. **Type safety & runtime crash risk (Engineering)**: Passing plain string errors (from AI validation, metamodel parsing, or plugins) into `Report.errors` will trigger unhandled `AttributeError` exceptions in report rendering.
2. **Metrics overview loss (Product)**: Completely replacing total project metrics with per-input metrics in multi-record projects deprives users of top-level system summary metrics.
3. **Broken link navigation (Product & Engineering)**: Making Markdown link file paths relative to individual "input record roots" rather than the project/report root breaks relative links in IDEs, GitHub, and Markdown viewers.

With these items addressed, the specification will be robust, backwards-compatible, and ready for implementation.

---

## Product Lens Findings

### 1a. User Value Assessment: Total System Metrics Loss
- **Finding (P1)**: Requirement 9 and Task 5 state that when multiple input records exist, metrics group strictly per input record, omitting the top-level aggregate total section. Users reviewing multi-record projects need both top-level total system metrics (overall requirement count, total trace coverage) and per-input breakdown. Forcing users to manually sum numbers across input tables reduces value.
- **Suggestion**: Retain the aggregate total system metrics section first, followed by the optional per-input breakdown ("Metrics by Input Record").

### 1b. Edge Cases & User Experience: Link Relativity & Broken Links
- **Finding (P2)**: Requirement 6 states file paths in links are relative to the input record root directory. However, Markdown readers (VS Code, GitHub, Obsidian) resolve relative Markdown links `[file.md](path)` relative to the `report.md` file location (or project root). If input records reside in subfolders, links relative only to input record root will produce broken 404 links when clicked in standard Markdown tools.
- **Suggestion**: Define link paths as relative to the project root (or working directory where report is saved) so clickable links navigate seamlessly across all Markdown editors.

### 1c. User Experience: Erratic Category Presentation Order
- **Finding (P3)**: `errors_grouped()` groups errors by category using dictionary order. Without a defined canonical category order, category headings (`Schema Errors`, `Trace Errors`, `Attribute Errors`) will appear in arbitrary sequences depending on error occurrence order.
- **Suggestion**: Establish a fixed `CANONICAL_CATEGORY_ORDER` in `report.py` to ensure consistent report visual hierarchy.

---

## Engineering Lens Findings

### 2a. Failure Mode Analysis: Runtime `AttributeError` on Legacy String Errors
- **Finding (E1)**: `Report.errors` is updated to `list[ReportError]`. However, string errors can still be produced by legacy code paths, `ai.py`, `metamodel.py`, `publish.py`, or custom extractors/plugins. In `report.j2` and `errors_grouped()`, accessing `.input_record` or `.category` on a plain `str` will crash report generation with an unhandled `AttributeError`.
- **Suggestion**: Implement defensive normalization in `Report` (e.g., `ReportError.from_any(err: ReportError | str)`) so plain string errors are safely coerced into `ReportError(message=str(err), category=CAT_STRUCTURE, input_record=None)`.

### 2b. Architecture Soundness: Incomplete `__str__()` Formatting Fallback
- **Finding (E2)**: `ReportError.__str__()` requires `artifact_type`, `artifact_id`, AND `file_path` to render location metadata `(type።id።path)`. If an error has `artifact_id` and `artifact_type` set but `file_path` is `None`, location metadata is completely dropped from `__str__()`.
- **Suggestion**: Update `__str__()` to handle partial metadata gracefully, e.g., rendering `(type።id)` when `file_path` is absent.

### 2c. Operational Readiness & Build Tools: i18n Catalog Compilation
- **Finding (E3)**: Task 8 describes adding category translations to `messages.po` but does not specify the compilation step for binary `.mo` files, creating a risk that new strings remain untranslated at runtime in CI or package builds.
- **Suggestion**: Explicitly document the `.po` to `.mo` compilation command / script in Task 8.

### 2d. Testing Strategy: CLI `--warnings-as-errors` E2E Test Coverage
- **Finding (E4)**: The task breakdown lacks test coverage verifying CLI `--warnings-as-errors` behavior when `ReportError` instances are raised in `FatalError`.
- **Suggestion**: Add a test case in Task 10 validating `--warnings-as-errors` CLI behavior with `ReportError`.

---

## Cross-Lens Insights

1. **Metrics Hierarchy (P1 × E1)**: Presenting aggregate totals first followed by per-input breakdown provides a complete product summary while keeping the metric calculation pipeline modular and testable.
2. **Link Navigation (P2 × E2)**: Standardizing relative path calculation against project root fixes both product link navigation (preventing 404 links) and engineering path resolution logic in `format_error`.

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| P1 | Product | 🎯 Must-Address | User Value | Replacing aggregate total metrics with per-input subsections loses top-level system overview. | Retain top-level aggregate metrics section first, followed by per-input breakdown. |
| P2 | Product | 🎯 Must-Address | Edge Cases & UX | Link file paths relative to "input record root" produce broken Markdown links in readers. | Compute link file paths relative to project root / current working directory. |
| P3 | Product | 💡 Recommendation | User Experience | `errors_grouped()` does not enforce canonical category ordering, leading to erratic heading order. | Define `CANONICAL_CATEGORY_ORDER` in `report.py` for consistent category sorting. |
| E1 | Engineering | 🎯 Must-Address | Failure Modes | Plain string errors passed to `Report.errors` cause unhandled `AttributeError` crash during rendering. | Implement defensive `ReportError.from_any()` normalization in `Report`. |
| E2 | Engineering | 💡 Recommendation | Architecture | `ReportError.__str__()` drops artifact ID metadata if `file_path` is `None`. | Support `(atype።aid)` fallback in `ReportError.__str__()`. |
| E3 | Engineering | 💡 Recommendation | Operational Readiness | Task 8 doesn't specify `.po` to `.mo` compilation command, risking uncompiled locale catalogs. | Document exact i18n compilation command in Task 8. |
| E4 | Engineering | 💡 Recommendation | Testing Strategy | Task breakdown lacks verification of CLI `--warnings-as-errors` with `ReportError`. | Add an E2E test in Task 10 for CLI `--warnings-as-errors`. |

---

## Verdict

⚠️ **PROCEED WITH UPDATES**

The specification is well-architected and ready for implementation once the 3 Must-Address items (P1, P2, E1) and recommended enhancements are integrated.

---

## Remediation Plan & Suggested Edits

Below are the exact suggested modifications for `docs/specs/improve-analyze-report-structure-and-ux.spec.md`:

### 1. Fix Link Path Relativity (P2)
**In Section "Requirements" (Item 6):**
```diff
- 6. File paths in links are **relative to the input record root** (vault root).
+ 6. File paths in links are **relative to the project root** (working directory).
```

### 2. Retain Aggregate Metrics Section (P1)
**In Section "Requirements" (Item 9):**
```diff
- 9. Metrics section groups by input record when more than one input record contributes requirements. When only one input record exists, render flat (current layout).
+ 9. Metrics section always presents the top-level aggregate system metrics first. When more than one input record contributes requirements, an additional "Metrics by Input Record" subsection breakdown is rendered underneath.
```

### 3. Add Defensive Error Coercion & Canonical Category Order (E1, P3)
**In Section "Proposed Solution -> Data Model" (`report.py`):**
```diff
  GLOBAL_INPUT = '__global__'

+ CANONICAL_CATEGORY_ORDER = [
+     CAT_EXTRACTION,
+     CAT_STRUCTURE,
+     CAT_SCHEMA,
+     CAT_ATTRIBUTE,
+     CAT_REFERENCE,
+     CAT_TRACE,
+     CAT_DUPLICATE,
+ ]

  @dataclass
  class ReportError:
      message: str
      category: str
      input_record: str | None = None   # None → grouped under "Global"
      artifact_id: str | None = None
      artifact_type: str | None = None
      file_path: str | None = None
      line_range: tuple[int, int] | None = None

+     @classmethod
+     def from_any(cls, err: 'ReportError | str') -> 'ReportError':
+         if isinstance(err, ReportError):
+             return err
+         return cls(message=str(err), category=CAT_STRUCTURE)
```

### 4. Enhance `ReportError.__str__()` Fallback (E2)
**In Section "Proposed Solution -> Data Model" (`report.py`):**
```diff
      def __str__(self) -> str:
          """Backward-compatible plain-text representation."""
          loc = ''
          if self.artifact_type and self.artifact_id and self.file_path:
              lines = f':{self.line_range[0]}-{self.line_range[1]}' if self.line_range else ''
              loc = f' ({self.artifact_type}።{self.artifact_id}።{self.file_path}{lines})'
+         elif self.artifact_type and self.artifact_id:
+             loc = f' ({self.artifact_type}።{self.artifact_id})'
          elif self.file_path:
              loc = f' ({self.file_path})'
          return f'{self.message}{loc}'
```

---

## Action Required

Would you like me to apply these suggested changes to `docs/specs/improve-analyze-report-structure-and-ux.spec.md`?

Options:
- **all**: Apply all Must-Address items and Recommendations to the spec file.
- **select**: Select specific items to apply.
- **none**: Keep spec unchanged.
