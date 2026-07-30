# YAML Boolean Value Coercion Bug

GitHub: https://github.com/flyvercity/syntagmax/issues/109

## Problem

When a metamodel declares a boolean attribute with custom labels (e.g. `[true: "yes", false: "no"]`), and a user writes `safety: no` in a YAML attrs block, PyYAML parses `no` as Python `False`. The extractor then converts the value via `str(False)` → `"False"`. During validation, `"false"` is compared against the custom label set `{"no"}` and fails.

Error produced:
```
Attribute 'safety' value 'False' is not a valid boolean (expected yes / no)
```

## Root Cause

`benedict.from_yaml()` uses PyYAML which implements YAML 1.1 — all of `yes/no/on/off/true/false` are parsed as Python booleans. The markdown extractor converts YAML values to strings with `str(value)`, which for booleans produces `"True"` or `"False"` rather than the original label.

## Fix

In the markdown extractor's YAML value conversion loop (line ~543 of `markdown.py`), when `value` is a Python `bool`, convert it back to the first custom label from the metamodel for the matching truth/falsity. Fallback to `"yes"`/`"no"` when no custom labels are defined (matching YAML 1.1 conventions).

The same fix applies to the sidecar extractor and simple-markdown extractor wherever `str(value)` is used on YAML-parsed values.
