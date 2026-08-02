# Bug Fix: DOCX Image Publication Ordering

## Problem Statement

When publishing individual records (non-`--single` mode) with `--docx`, images are missing
from the generated DOCX file on a fresh output directory. Re-running the same command without
clearing the output directory produces correct DOCX output because images from the first run
are already present on disc.

### Root Cause

In the multi-record publish path (`cli.py`, the `else` branch of the `publish` command),
Pandoc conversion is called **inside** the per-record loop, immediately after writing each
markdown file. However, `_copy_manifest_images` is called **after** the loop completes.

```
for record in selected_records:
    ...
    file_path.write_text(markdown)             # ← markdown references images/...
    _run_pandoc_conversion(file_path, ...)     # ← Pandoc looks for images/ — not yet present
    ...

_copy_manifest_images(combined_manifest, out_p)  # ← images finally copied here
```

Pandoc uses `--resource-path=<md_path.parent>` to locate images. Since the `images/`
subdirectory doesn't exist at conversion time, Pandoc silently omits them.

The `--single` path does **not** have this bug — it copies images before calling Pandoc.

## Requirements

1. Images MUST be present on disc before Pandoc is invoked for any record.
2. The fix MUST NOT change semantics for `--single` mode (already correct).
3. Stale image cleanup (existing behaviour in `_copy_manifest_images`) MUST still occur.
4. No new dependencies or configuration options.

## Background

- `_copy_manifest_images(manifest, output_dir)` handles mkdir + stale cleanup + copy.
- Each per-record `manifest` is merged into `combined_manifest` inside the loop.
- Pandoc's `--resource-path` is set to `md_path.parent` (i.e. the output directory).
- In multi-record mode, all files share the same `out_p` directory.

## Proposed Solution

Move `_copy_manifest_images(combined_manifest, out_p)` to execute **before** any Pandoc
conversion. Since we need the complete manifest (all records' images) before any conversion,
the simplest correct fix is:

1. Keep the rendering loop as-is (write markdown, accumulate manifest).
2. **Remove** the in-loop Pandoc call.
3. After the loop: copy images via `_copy_manifest_images`.
4. Then run Pandoc conversion for each record's markdown file in a second pass.

This mirrors the structure of the `--single` path: render → copy images → convert.

### Code Change (cli.py, multi-record branch)

```python
# Current (buggy):
for record in selected_records:
    ...
    file_path.write_text(markdown, encoding='utf-8')
    ...
    if pandoc_available:
        reference_doc = _resolve_template_for_record(record) if docx else None
        _run_pandoc_conversion(file_path, docx, pdf, reference_doc=reference_doc)

# Copy images after all records are processed
_copy_manifest_images(combined_manifest, out_p)
```

```python
# Fixed:
published_files = []  # collect (file_path, record) tuples for deferred Pandoc

for record in selected_records:
    ...
    file_path.write_text(markdown, encoding='utf-8')
    ...
    published_files.append((file_path, record))

# Copy images before Pandoc conversion
_copy_manifest_images(combined_manifest, out_p)

# Pandoc conversion (images now available)
if pandoc_available:
    for file_path, record in published_files:
        reference_doc = _resolve_template_for_record(record) if docx else None
        _run_pandoc_conversion(file_path, docx, pdf, reference_doc=reference_doc)
```

## Task Breakdown

1. **Fix ordering in cli.py** — defer Pandoc calls to after image copy.
2. **Verify** — run existing test suite; confirm no regressions.
3. **Documentation** — no user-facing doc changes required (this is a bug fix, not a behaviour change).
