# Critique: Error Message Localization Specification

## Executive Summary

The **Error Message Localization** specification ([`docs/specs/error-message-localization.spec.md`](../specs/error-message-localization.spec.md)) provides a clear, highly structured plan to complete the i18n implementation for Syntagmax. It addresses a real user friction point where Russian reports contain mixed language content (Russian headers with English error details).

However, deep review across Product and Engineering lenses revealed several **Must-Address** gaps where hardcoded English sub-strings (`" in "`, `'Missing ID'`, `'Parse Error'`, `'expected true/false...'`) would bleed through into Russian reports despite template translation, as well as an omitted error message in `SidecarExtractor`. 

Overall Assessment: **⚠️ PROCEED WITH UPDATES**. The core design (format-string gettext, single catalog, translation at creation time) is sound, but the specification needs targeted updates to guarantee 100% language consistency in generated reports.

---

## Product Lens Findings

### 1a. Problem Validation
- **Strengths**: The problem statement correctly identifies that `--lang ru` produces an inconsistent UI experience where report section headers are translated into Russian while the error bodies remain in English.
- **Scope**: Scope is well-targeted on user-facing report content (`ReportError` objects and `report.j2` AI headers).

### 1b. User Value Assessment
- **Tangible Value**: Localizing error messages enables non-English speaking engineers and domain experts to immediately understand validation failures without translating technical jargon.
- **Completeness Gap (P1 - 🎯 Must-Address)**: In `extractors/text.py`, the spec localizes the outer message wrapper (`_('Driver "text": {error_type} in {location}\n...')`), but leaves literal argument strings passed to it (`'Missing ID'`, `'ID is required'`, `'Parse Error'`, `'Malformed artifact'`) in English. When rendered in Russian, users will see hybrid errors such as:
  ```text
  Драйвер "text": Missing ID в main.py:10-15
  При анализе [<REQ id=1>]
  Причина: ID is required
  ```
  *Recommendation*: Wrap all error category/reason literal strings in `_()` within `text.py`.

- **Completeness Gap (P2 - 🎯 Must-Address)**: `format_error()` in `report.py` hardcodes the English word `" in "` when joining artifact ID and file link (`" (REQ:REQ-001 in [spec.md](...))"`). Russian reports will render error lines containing `" in "` between Russian text and Markdown links.
  *Recommendation*: Localize the linking text in `report.py` using `_("{loc1} in {loc2}")` or `_("in")`.

- **Completeness Gap (P3 - 🎯 Must-Address)**: In `extractors/sidecar.py` (line 121), `ValidationError` handling constructs `msg = f'{self.driver()} :: Validation error in {sidecar_path}: {e}'`. This message was omitted from Task 4 breakdown and the translation table in the spec.
  *Recommendation*: Add `Validation error in {sidecar_path}: {e}` to Task 4 and the translation catalog.

### 1c. Alternative Approaches
- **Translate at Render vs Translate at Creation**: The spec chooses to translate at creation time (`ReportError` construction). This is simpler and fits Syntagmax's architecture where `Report` is a stateless container rendered immediately after analysis.

---

## Engineering Lens Findings

### 2a. Architecture Soundness & Data Models
- **Boolean Validation Error Interpolation (E1 - 🎯 Must-Address)**: In `analyse.py`, boolean validation generates dynamic strings for `expected_str`:
  ```python
  expected_str = f'expected {", ".join(...)} / {", ".join(...)}'
  # or
  expected_str = 'expected true/false, yes/no, 1/0'
  ```
  The spec passes `expected_str` as `{expected}` into `_("Attribute '{attr_name}' value '{val}' is not a valid boolean ({expected})")`. In Russian, this results in:
  `"Значение 'foo' атрибута 'is_active' не является допустимым булевым (expected true/false, yes/no, 1/0)"`.
  *Recommendation*: Localize `expected_str` directly before passing it into `.format()`.

### 2e. Testing Strategy
- **Integration Test Coverage (E2 - 💡 Recommendation)**: Task 7 tests isolated `_("...").format(...)` calls, but lacks end-to-end integration tests that run full `extract()` and `analyse_tree()` pipelines with `setup_i18n('ru')` and assert rendered `Report.render()` output.
  *Recommendation*: Add an end-to-end report rendering test in `tests/test_i18n.py`.

### 2f. Operational Readiness
- **Babel Extraction Rules (E3 - 💡 Recommendation)**: `babel.cfg` currently lists 8 explicit single-file rules.
  *Recommendation*: Simplify `babel.cfg` to `[python: src/syntagmax/**.py]` to automatically include present and future modules.

- **Logger Output vs Report Error Scope (E4 - 🤔 Question)**: The spec does not explicitly state whether `lg.warning()` / `lg.error()` lines emitted to console/logs should remain in technical English or be localized.
  *Recommendation*: Explicitly document in Design Decision 4 that internal logging (`lg.warning/error`) remains English for sysadmins, whereas user-facing `ReportError`/`ErrorBlock` messages are localized.

---

## Cross-Lens Insights

Both lenses converge on the principle of **Zero-Bleed Localization**:
1. **Product & Engineering Convergence**: Sub-string interpolation (`" in "`, `'Missing ID'`, `'expected...'`) must be fully localized. Partial localization creates an unpolished user experience and fails automated catalog completeness assertions.
2. **Maintenance & Extensibility**: Simplifying `babel.cfg` with wildcard patterns prevents future extraction gaps when new drivers or analysis modules are created.

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| P1 | Product | 🎯 | Edge Cases & UX | `TextExtractor` error template is localized, but literal argument strings (`'Missing ID'`, `'ID is required'`, `'Parse Error'`, `'Malformed artifact'`) are left in English. | Wrap error category and reason literals in `_()` inside `extractors/text.py`. |
| P2 | Product | 🎯 | Edge Cases & UX | `format_error()` in `report.py` hardcodes the English word `" in "` when linking artifact IDs to file locations (`" (REQ:REQ-001 in [spec.md](...))"`). | Localize linking text in `report.py` using `_("{loc1} in {loc2}")` or `_("in")`. |
| P3 | Product | 🎯 | MVP & Scope | `SidecarExtractor` contains an error message (`msg = f'{self.driver()} :: Validation error in {sidecar_path}: {e}'` at line 121) omitted from Task 4 breakdown. | Add `Validation error in {sidecar_path}: {e}` to Task 4 breakdown and translation tables. |
| E1 | Engineering | 🎯 | Failure Modes / Data Models | In `analyse.py`, `expected_str` contains hardcoded English ("expected...") injected into `{expected}` parameter of localized boolean error template. | Localize `expected_str` directly before formatting into the error message. |
| E2 | Engineering | 💡 | Testing Strategy | Task 7 test suite tests isolated `_("...").format(...)` calls, but lacks end-to-end integration tests asserting full `Report.render()` output in Russian. | Add full end-to-end integration tests running `extract()` and `analyse_tree()` under `setup_i18n('ru')`. |
| E3 | Engineering | 💡 | Operational Readiness | `babel.cfg` lists 8 individual python file patterns instead of using wildcard `[python: src/syntagmax/**.py]`. | Simplify `babel.cfg` to `[python: src/syntagmax/**.py]` to automatically capture all source files. |
| E4 | Engineering | 🤔 | Scope & Operational Readiness | Spec does not explicitly specify whether `lg.warning()` / `lg.error()` log messages remain in English or get localized. | Clarify in Design Decision 4 that internal logger outputs remain English, while `ReportError`/`ErrorBlock` messages are localized. |

---

## Verdict

⚠️ **PROCEED WITH UPDATES**

The overall direction of `docs/specs/error-message-localization.spec.md` is sound and ready for implementation once the 4 **Must-Address** items (P1, P2, P3, E1) and recommendations are incorporated into the specification.

---

## Offered Remediation

To resolve all identified issues, the following specific updates should be made to `docs/specs/error-message-localization.spec.md`:

1. **Update `text.py` in Task 4**:
   Add explicit localization for error sub-strings:
   ```python
   # text.py
   error = self._format_error(_('Missing ID'), location, section_start_string, _('ID is required'))
   error = self._format_error(_('Parse Error'), location, section_start_string, str(e))
   error = self._format_error(_('Malformed artifact'), location, section_start_string, str(e))
   ```

2. **Update `report.py` in Proposed Solution & Task 4/5**:
   Localize the `" in "` connector in `format_error()`:
   ```python
   # report.py format_error()
   if loc_parts:
       parts.append(_(" ({loc1} in {loc2})").format(loc1=loc_parts[0], loc2=loc_parts[1]))
   ```

3. **Add missing Sidecar Error to Task 4**:
   Add `_("{driver} :: Validation error in {path}: {error}").format(driver=self.driver(), path=sidecar_path, error=str(e))` to `extractors/sidecar.py`.

4. **Fix Boolean `expected_str` in Task 1**:
   Localize `expected_str` in `analyse.py`:
   ```python
   if 'custom_values' in type_info:
       expected_str = _("expected {true_vals} / {false_vals}").format(
           true_vals=", ".join(type_info["custom_values"]["true"]),
           false_vals=", ".join(type_info["custom_values"]["false"]),
       )
   else:
       expected_str = _("expected true/false, yes/no, 1/0")
   ```

5. **Simplify `babel.cfg` in Proposed Solution & Task 6**:
   ```ini
   [python: src/syntagmax/**.py]
   [jinja2: src/syntagmax/resources/*.j2]
   encoding = utf-8
   silent = false
   ```

6. **Add E2E Integration Test to Task 7**:
   Add an end-to-end test verifying `Report.render()` under `setup_i18n('ru')`.

---

Would you like me to apply these changes to `docs/specs/error-message-localization.spec.md`? (all / select / none)
