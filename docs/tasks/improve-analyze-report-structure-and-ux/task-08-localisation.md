# [x] Task 8: Localisation Updates

**Spec:** `docs/specs/improve-analyze-report-structure-and-ux.spec.md`

## Objective

Add translated strings for error categories and new report structure elements.

## Dependencies

- Task 6 (template uses `{{ _(...) }}` for category names — need translations to exist)

## Implementation

### `src/syntagmax/resources/locales/en/LC_MESSAGES/messages.po`

Add entries:
- `"Schema Errors"` → `"Schema Errors"`
- `"Attribute Errors"` → `"Attribute Errors"`
- `"Reference Errors"` → `"Reference Errors"`
- `"Trace Errors"` → `"Trace Errors"`
- `"Duplicate Errors"` → `"Duplicate Errors"`
- `"Extraction Errors"` → `"Extraction Errors"`
- `"Structure Errors"` → `"Structure Errors"`
- `"Global"` → `"Global"`
- `"errors"` → `"errors"`
- `"Metrics by Input Record"` → `"Metrics by Input Record"`

### `src/syntagmax/resources/locales/ru/LC_MESSAGES/messages.po`

Add Russian translations for all new strings.

### Compile `.mo` files

```bash
msgfmt src/syntagmax/resources/locales/en/LC_MESSAGES/messages.po -o src/syntagmax/resources/locales/en/LC_MESSAGES/messages.mo
msgfmt src/syntagmax/resources/locales/ru/LC_MESSAGES/messages.po -o src/syntagmax/resources/locales/ru/LC_MESSAGES/messages.mo
```

## Test Requirements

- With `language = "ru"`, report renders category names in Russian.
- English report uses English category names.

## Demo

`syntagmax --lang ru analyze` produces report with Russian category headings.

## Files Modified

- `src/syntagmax/resources/locales/en/LC_MESSAGES/messages.po`
- `src/syntagmax/resources/locales/en/LC_MESSAGES/messages.mo`
- `src/syntagmax/resources/locales/ru/LC_MESSAGES/messages.po`
- `src/syntagmax/resources/locales/ru/LC_MESSAGES/messages.mo`
