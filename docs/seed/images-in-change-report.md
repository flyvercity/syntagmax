# Images in Change Reports

## Intent

Detect and report changes to image/binary artifacts (managed via the sidecar driver) in change reports. Currently, the change pipeline only handles text-based artifacts meaningfully.

## Approaches

### 1. Metadata-Only Comparison (Simplest)

Compare only the sidecar YAML — field changes in `.stmx`/`.syntagmax` are already handled by `compare_artifacts`. Image binary changes are detected solely by git file status (Added/Modified/Removed from `get_changed_files`).

Report output: "Image file modified" + any sidecar attribute changes.

Pros: Zero new dependencies, works today with minor wiring.
Cons: No information about *what* changed in the image itself.

### 2. Hash-Based Binary Change Detection

Compute content hashes (SHA-256) of the image files at both revisions. Report whether the binary content changed without interpreting the change.

Report output: "Binary content changed (hash mismatch)" alongside sidecar attribute diffs.

Pros: Deterministic, no external dependencies. Clear signal that something changed.
Cons: Still no semantic information about the visual difference.

### 3. File Size + Dimensions Metadata

Extract basic image properties (file size, dimensions, colour depth) at each revision using `Pillow` or pure header parsing. Report these as pseudo-fields.

Example report output:

| Property | Previous | Current |
|----------|----------|---------|
| size | 45.2 KB | 52.1 KB |
| dimensions | 1024×768 | 1280×960 |

Pros: Gives reviewers a quick sense of the change magnitude. Pillow is lightweight.
Cons: Adds a dependency (though optional). Doesn't show *what* changed visually.

### 4. Side-by-Side Image Embedding in Report

Embed both old and new images as relative paths in the Markdown report. The reviewer opens the report and visually compares.

Example report output:

```markdown
##### Previous
![SYS-001 (base)](images/SYS-001_base.png)
##### Current
![SYS-001 (target)](images/SYS-001_target.png)
```

Pros: Human review becomes trivial. Works well with `--single` consolidated reports.
Cons: Requires copying image blobs out of git at both revisions. Report size grows. Only useful for visual inspection, not automation.

### 5. Perceptual Diff (Advanced)

Generate a pixel-level diff image highlighting changed regions (using something like `pixelmatch` logic or `Pillow` ImageChops). Store the diff image alongside the report.

Report output: Diff image embedded + percentage of pixels changed.

Pros: Precise, automatable threshold ("ignore changes < 1% pixels").
Cons: Heavy dependency. Only works for raster formats. SVG needs different handling.

### 6. SVG Text Diff (For Vector Graphics)

SVGs are XML — treat them as text and run unified diff. Report structural changes (added/removed elements, changed attributes like coordinates or colours).

Pros: Leverages existing text diff infrastructure. Very informative for hand-edited diagrams.
Cons: Machine-generated SVGs produce noisy diffs. Needs heuristics to suppress irrelevant attribute reordering.

## Recommended Layered Strategy

1. **Baseline (minimal effort):** Detect image file changes via git status + sidecar field diffs. Tag them as `Binary Changed` in the report. Ensure sidecar driver records participate in `filter_changed_files` and that `change_render` has a rendering branch for sidecar/image artifacts.

2. **Enhancement (optional):** Extract dimensions/size at both revisions (approach 3) and embed old/new images in the report (approach 4). Gate behind a `--include-images` flag to keep reports lean by default.

3. **Future (if demand exists):** Perceptual diff for raster, text diff for SVG.

## Key Implementation Gaps

- `change_extract.py` uses `DEFAULT_FILTERS` to glob files; sidecar isn't listed there. Need a sidecar-aware filter (`**/*.stmx` + `**/*.syntagmax`) or reliance on the record's configured glob.
- In `compare_artifacts`, sidecar artifacts have `FileLocation.loc_file` pointing to the image — need to detect when that file is binary and note its git status.
- In `change_render.py`, need a rendering path for image artifacts that shows "binary content changed" plus any sidecar attribute diffs.

## Expected CLI Interface

No new CLI flags for baseline. Enhancement adds:

```
syntagmax change report --base HEAD~1 --target HEAD --include-images
```

## Follow-up Tasks

- Amend README change report section to mention image/sidecar support
- Update docs/reference with image change details
- Add example with a sidecar-managed image artifact
