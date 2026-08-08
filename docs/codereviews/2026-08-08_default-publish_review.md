# Code Review: default-publish

- **Date**: 2026-08-08
- **Target Branch**: `origin/main`
- **Files Changed**: 5 (`src/syntagmax/publish.py`, `src/syntagmax/publish_config.py`, `tests/test_publish.py`, `docs/specs/publish-default-render-section.spec.md`, `docs/critiques/publish-default-render-section.critique.md`)

---

## 1. Architectural & Design Overview

The branch implements default render configuration support (`_default_` for artifact types, `_default_marker_` for text markers) and the `_remaining_` pseudo-attribute in `syntagmax` publishing pipeline.

Key design changes:
1. **Reserved Key Constants**: Added `DEFAULT_ARTIFACT_KEY` (`_default_`), `DEFAULT_MARKER_KEY` (`_default_marker_`), and `REMAINING_SENTINEL` (`_remaining_`) in `src/syntagmax/publish_config.py`.
2. **Fallback Cascading**: Updated `render_block()` in `src/syntagmax/publish.py` to inspect type/marker specific configurations first, falling back to `_default_` / `_default_marker_` before defaulting to hardcoded fallback renderers.
3. **Dynamic `_remaining_` Expansion**: Implemented `_resolve_remaining_fields()` to discover remaining attributes not explicitly listed in any section of the render config, subject to field formatting (`format_field_label`) and attribute presence rules.
4. **Dynamic Marker Name Substitution**: Added `{marker}` placeholder expansion in `MarkerRenderSection.alias` under `_default_marker_`.

---

## 2. Security & Performance Audit

- **Security Concerns**: None. No untrusted string execution, SQL injection, or path traversal vectors are introduced. All field rendering continues to use standard markdown cell escaping (`_escape_table_value`) and image link rewriting (`rewrite_image_references`).
- **Performance & Scalability**:
  - `collect_explicit_attributes()` is executed once per artifact block rendering step, building a set of explicit attributes. This is $O(N)$ with respect to section attribute count and introduces negligible memory overhead.
  - Dict lookups for `_default_` and `_default_marker_` in `render_block()` currently iterate over `pub_config.render.items()` (minor linear scan optimization opportunity noted below).

---

## 3. Detailed File-by-File Findings

### `src/syntagmax/publish.py`

- **[Severity: High]** Line 346: Incorrect dictionary key lookup for metamodel artifact definitions in `_resolve_remaining_fields()`.
  - **Context**: `_resolve_remaining_fields()` attempts to merge metamodel attribute definitions into `_remaining_` candidates using `metamodel.get('artifact_types', {})`. In `syntagmax`, the metamodel dictionary uses `'artifacts'` as its root key for artifact definitions (e.g. `metamodel['artifacts']`). Because of this mismatch, `artifact_types` is always empty `{}` and metamodel-defined attributes missing from the artifact instance are never discovered during `_remaining_` expansion when `attribute_presence` is `'all'` or `'mandatory'`.
  - **Suggested Fix**:
    ```suggestion
    if metamodel:
        atype_upper = artifact.atype.upper()
        artifacts = metamodel.get('artifacts', {})
        for type_name, type_def in artifacts.items():
            if type_name.upper() == atype_upper:
                if hasattr(type_def, 'attributes'):
                    candidates.update(type_def.attributes.keys())
                elif isinstance(type_def, dict):
                    candidates.update(type_def.get('attributes', {}).keys())
                break
    ```

- **[Severity: Medium]** Lines 408-411 & 479-482: Redundant linear scan loops for default key lookups in `pub_config.render`.
  - **Context**: `pub_config.render` is a standard `dict[str, list[RenderSection]]`. Iterating over `pub_config.render.items()` to check `k == DEFAULT_MARKER_KEY` or `k == DEFAULT_ARTIFACT_KEY` can be simplified to a direct $O(1)$ dictionary lookup `pub_config.render.get(...)`.
  - **Suggested Fix**:
    ```suggestion
    default_marker_sections = pub_config.render.get(DEFAULT_MARKER_KEY)
    ```

---

### `src/syntagmax/publish_config.py`

- **[Severity: Medium]** Line 95: Untyped `list` generic parameter in `collect_explicit_attributes()`.
  - **Context**: `def collect_explicit_attributes(sections: list) -> set[str]:` omits the generic element type, which deviates from strict type annotations in the rest of `publish_config.py`.
  - **Suggested Fix**:
    ```suggestion
    def collect_explicit_attributes(sections: list[RenderSection]) -> set[str]:
    ```

---

## 4. Test Coverage & Edge Cases

- **Coverage Assessment**: Comprehensive unit tests added to `tests/test_publish.py` covering `_default_`, `_default_marker_`, `{marker}` placeholder expansion, title-case field label formatting, and cross-section exclusion.
- **Missing Tests**:
  - A test verifying that `_remaining_` correctly discovers metamodel attributes defined in `metamodel['artifacts']` when `attribute_presence` is `'all'` and the field is absent from `artifact.fields`.

---

## 5. Actionable Next Steps

- [ ] **Task 1 (High Priority)**: Fix `metamodel.get('artifact_types', {})` -> `metamodel.get('artifacts', {})` in `src/syntagmax/publish.py`.
- [ ] **Task 2 (Medium Priority)**: Update `collect_explicit_attributes(sections: list[RenderSection])` signature in `src/syntagmax/publish_config.py`.
- [ ] **Task 3 (Medium Priority)**: Simplify default key lookups in `render_block()` to `pub_config.render.get(...)`.
- [ ] **Task 4 (Low Priority)**: Add test case for `_remaining_` candidate expansion with metamodel definitions.
