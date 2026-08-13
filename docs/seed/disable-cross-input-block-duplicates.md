# Disable Cross-Input Duplicate Block Numbering Checks

## Intent

The publish pipeline validates uniqueness of explicit block IDs (marker + id) across all input records globally. When multiple inputs legitimately reuse the same marker numbering scheme independently (e.g., `[COM 1]` in both `system-requirements` and `software-requirements`), this produces false-positive duplicate errors.

Add a configuration option to disable or scope the duplicate block ID check so that numbering is validated per-input only (not across inputs).

## Current Behavior

In `publish.py`, the `seen` dict accumulates `(marker, id)` keys across **all** input blocks in the tree. A `[COM 1]` in input A and `[COM 1]` in input B triggers a duplicate error even though they belong to different requirement sets.

## Desired Behavior

- New config option (e.g., `[publish] cross_input_duplicates = false`) disables the cross-input uniqueness check
- When disabled, duplicate block ID validation is scoped per-input record (each input has its own `seen` dict)
- When enabled (default, for backward compatibility), behavior is unchanged
- The option should be documentable in `config.toml` under a publish or validation section

## Example Config

```toml
[publish]
cross_input_duplicates = false   # don't flag duplicate block IDs across different inputs
```

## Follow-up

- Update `docs/reference/configuration.md` with the new option
- Add a test case with duplicate block IDs across inputs that passes when the check is disabled
