# Code Review: [Incomplete-Localization]
- **Date**: 2026-08-06
- **Target Branch**: `main`
- **Files Changed**: 21

## 1. Architectural & Design Overview
This branch completes the localization infrastructure of Syntagmax by localizing error message templates across all stage-1 and stage-2 analysis modules (`analyse.py`, `tree.py`, `extract.py`, `metrics.py`, `artifact.py`, `report.py`, and extractor drivers). 

The design follows a **Format-String Gettext** approach (`_("template {param}").format(param=value)`). This guarantees:
- **Translator Flexibility**: Translators can reorder positional/named parameters to produce grammatically correct target language sentences.
- **Creation-Time Translation**: Errors are localized at the point of `ReportError` / `ErrorBlock` instantiation using the active language catalog configured during CLI initialization.
- **Clean Fallback**: `setup_i18n('en')` uses `NullTranslations` (passthrough), guaranteeing 100% byte-for-byte identical output for default/English users.

## 2. Security & Performance Audit
- **Security Concerns**: No security risks identified. Gettext catalog lookups use constant string keys, and `.format()` operations use explicit keyword parameters, preventing format string injection vectors.
- **Performance & Scalability**: Zero measurable impact on runtime performance. `gettext` dictionary lookups are $O(1)$ and `.po`/`.mo` compiled catalogs are small (~14KB). All 1000 unit/integration tests executed in 34.78s.

## 3. Detailed File-by-File Findings

### `src/syntagmax/analyse.py`
- **[Severity: Low]** Lines 112–129 & 201–210: Parametric error strings cleanly wrapped in `_()`.
  - **Context**: Dynamic `expected_str` for custom/default booleans is localized separately before being injected into the outer error template, preventing hardcoded English words ("expected...") from appearing in Russian error messages.

### `src/syntagmax/report.py`
- **[Severity: Low]** Lines 99: `format_error()` linking string localized via `_(" ({loc1} in {loc2})")`.
  - **Context**: Ensures the connecting word ("in" vs "в") between artifact IDs and file links is localized according to active locale.

### `src/syntagmax/extractors/text.py`
- **[Severity: Low]** Lines 129–133 & 189–210: Both the `_format_error()` template and error sub-string literals (`Missing ID`, `ID is required`, `Parse Error`, `Malformed artifact`) are wrapped in `_()`.
  - **Context**: Prevents mixed English/Russian output when text driver parse or validation errors occur.

### `babel.cfg`
- **[Severity: Low]** Line 1: `[python: src/syntagmax/**.py]` wildcard rule implemented.
  - **Context**: Replaced explicit file-by-file rules with a recursive wildcard, ensuring any future Python modules automatically participate in `pybabel extract`.

### `tests/test_i18n.py`
- **[Severity: Low]** Lines 114–229: Added `TestErrorMessageTranslation` and `TestReportRenderingLocalized`.
  - **Context**: Exercises individual string formatters under `ru` and `en` locales, as well as end-to-end `Report.render()` output validation.

## 4. Test Coverage & Edge Cases
- **Coverage**: High. 100% of new localized strings are verified by pytest assertions in `tests/test_i18n.py`.
- **Edge Cases Handled**:
  - `NullTranslations` passthrough verified for English locale.
  - Named parameter survival under `.format()` verified.
  - Multi-line format templates in `text.py` and `report.py` tested.

## 5. Actionable Next Steps
- [x] Merge PR #128 into `main`.
- [ ] Maintain `messages.po` / `messages.mo` when adding new user-facing error templates in future PRs.
