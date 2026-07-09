# Image-Aware Publishing

## Problem Statement

Published markdown files reference images by filename only (Obsidian `![[image.png]]` wiki-link syntax or standard `![alt](image.png)` with relative paths). Since the published output lands in `.syntagmax/reports/` (or a custom directory), these image paths don't resolve correctly — neither for markdown viewers nor for Pandoc DOCX/PDF conversion. Additionally, sidecar image artifacts render only their metadata text without embedding the actual image.

## Requirements

1. Support both Obsidian wiki-link image embeds (`![[image.png]]`) and standard markdown images (`![alt](path/to/image.png)`) in text blocks.
2. For sidecar artifacts whose primary file is an image, emit a markdown image embed (`![title](path)`) in the published output.
3. Copy referenced image files to an `images/` subdirectory alongside the output markdown, and rewrite all paths to point there (self-contained output).
4. Pandoc conversion should work correctly with the rewritten paths (since images are co-located with the markdown).
5. Unresolvable image references are left unchanged with a logged warning — no crash.
6. Determinism: identical inputs produce identical outputs (stable image naming/ordering).
7. **Security:** Resolved image paths must reside within the project workspace (`base_dir`). Paths that escape the workspace are skipped with a warning.
8. **Remote URLs:** Image references using remote URLs (`http://`, `https://`, `//`) are left unmodified — not downloaded, not added to the manifest.
9. **Stale cleanup:** The `images/` output subdirectory is emptied at the start of each publish run to prevent stale images from accumulating.

## Success Criteria

- Published markdown renders images correctly in standard markdown viewers (VS Code preview, GitHub, Obsidian).
- Pandoc DOCX/PDF conversion completes without "image not found" warnings for all resolved images.
- No files outside `base_dir` are ever copied into the output.
- Repeated publish runs produce identical output for identical inputs.

## Background

- `publish.py` → `render_block_tree()` produces the final markdown string. `render_block()` handles both `TextBlock` (verbatim content pass-through) and `ArtifactBlock` (field-based rendering).
- The markdown extractor (`extractors/markdown.py`) captures text between artifacts as `TextBlock.content` without parsing image syntax.
- Sidecar extractor produces `ArtifactBlock` with `FileLocation(loc_file='SYS/diagram.png', loc_sidecar='SYS/diagram.png.stmx')`. The `loc_file` is the image path relative to `base_dir`.
- `Config.base_dir()` is the project root. `Config.derive_path(filepath)` gives the path relative to base_dir.
- Output files are written in `cli.py` via `Path.write_text()`. The output directory is resolved there.
- Pandoc is called via `subprocess.run` without `--resource-path` or `cwd` override.
- Obsidian wiki-link resolution is vault-wide filename search (no path, just `filename.ext`).
- Standard markdown image paths are relative to the file containing them.

## Proposed Solution

### Architecture

```mermaid
flowchart TD
    A[render_block_tree] --> B[render_block for TextBlock]
    A --> C[render_block for ArtifactBlock]
    B --> D[rewrite_image_references]
    C --> E{Is sidecar image?}
    E -->|Yes| F[emit ![title](images/filename)]
    E -->|No| G[existing rendering]
    D --> H[Parse !double-bracket and !standard-bracket]
    H --> I[Resolve source path via base_dir]
    I --> V{Path within base_dir?}
    V -->|Yes| J[Collect image in copy manifest]
    V -->|No| W[Log warning, leave unchanged]
    J --> K[Rewrite to images/filename in output]
    
    L[CLI publish command] --> M[render_block_tree returns markdown + image manifest]
    M --> N[Clean + copy images to output_dir/images/]
    M --> O[Write markdown]
    O --> P[Pandoc conversion with --resource-path]
```

### Data Model

- `ImageManifest`: maps `source_absolute_path → target_relative_path` (primary direction). Also maintains a reverse lookup `target_relative_path → source_absolute_path` for collision detection. This ensures O(1) deduplication — if the same source image is referenced multiple times, it reuses the existing target name.
- `RenderContext`: holds `config: Config`, `manifest: ImageManifest`, `source_file_path: str | None` (the current FileRecord.path being rendered). Passed through the rendering pipeline.

### Image Resolution Strategy

- **Remote URLs** (`http://`, `https://`, `//`): left unmodified, not added to manifest, no warning.
- **Obsidian `![[filename.ext]]`**: search all input record filepaths for a file matching the filename. If found, resolve to absolute path via `base_dir`. Validate it resides within `base_dir`. Add to manifest, rewrite to `![alt](images/target_name.ext)`.
- **Standard `![alt](path)`**: URL-decode the path (`urllib.parse.unquote`), resolve relative to the source file's directory (using `context.source_file_path` and `base_dir`). Validate it resides within `base_dir`. Add to manifest, rewrite path to `images/target_name.ext`.
- **Sidecar image artifacts**: check `artifact.location.loc_file` extension against image extensions set. If image, resolve via `base_dir`, add to manifest, emit `![<title or id>](images/<target_name>)` before metadata rendering.

### Security: Path Containment

After resolving any image path to an absolute path, validate:
```python
resolved.resolve().is_relative_to(base_dir.resolve())
```
If this check fails, log a warning (`Image path escapes project workspace: {path}`) and leave the reference unchanged. Never copy files from outside `base_dir`.

### Filename Collision Handling

Target filenames in `images/` are derived by flattening the image's relative path from `base_dir`, replacing path separators with `-`. This guarantees uniqueness because repository-relative paths are unique.

Examples:
- `SYS/diagram.png` → `images/SYS-diagram.png`
- `REQ/assets/figure.png` → `images/REQ-assets-figure.png`
- `docs/images/arch.svg` → `images/docs-images-arch.svg`

This avoids the ambiguity of single-parent-prefix approaches where `a/images/f.png` and `b/images/f.png` would collide.

### Image Extensions

```python
IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.gif', '.svg', '.bmp', '.webp'})
```

### Output Directory Resolution

The `images/` subdirectory is always placed relative to the **parent directory of the output markdown file**:

- **Single mode** (`--single --output path/to/doc.md`): images go to `path/to/images/`
- **Separate mode** (`--output path/to/dir/`): images go to `path/to/dir/images/`

### Output Structure

```
.syntagmax/reports/
├── system-requirements.md
├── software-requirements.md
├── system-diagrams.md
└── images/
    ├── SYS-diagram.png
    └── REQ-assets-architecture.svg
```

### Stale Image Cleanup

At the start of each publish run, if the `images/` output subdirectory exists, it is emptied (all files removed). This prevents stale images from previous runs accumulating. The directory itself is preserved.

### Return Type Change

`render_block_tree()` returns `tuple[str, ImageManifest]` instead of `str`. All callers updated.

## Task Breakdown

### Task 1: Create `RenderContext` and `ImageManifest` data structures

**Objective:** Introduce a `RenderContext` dataclass that holds the config, base_dir, and an `ImageManifest` accumulator.

**Implementation guidance:**
- Create `src/syntagmax/publish_context.py`
- `ImageManifest`:
  - Primary mapping: `dict[Path, str]` — `source_absolute_path → target_relative_path` (e.g. `Path('/project/SYS/diagram.png') → 'images/SYS-diagram.png'`)
  - Provides `add(source: Path, base_dir: Path) -> str` that computes the flattened target name from the source path's relative position to `base_dir`, stores the mapping, and returns the target relative path
  - If the same source path is added again, returns the existing target (O(1) dedup)
- `RenderContext` holds: `config: Config`, `manifest: ImageManifest`, `source_file_path: str | None`
- Add helper `resolve_image_to_manifest(image_ref: str, context: RenderContext, is_obsidian: bool) -> str | None`:
  - Resolves the image reference to an absolute path
  - Validates path containment within `base_dir`
  - URL-decodes the path for standard references
  - Returns the target relative path (e.g. `images/SYS-diagram.png`) or `None` if unresolvable/unsafe
- Define `IMAGE_EXTENSIONS` frozenset here
- Collision handling via path flattening: replace `/` with `-` in the relative path from base_dir

**Test requirements:**
- Unit test `ImageManifest.add()` deduplication (same source twice returns same target)
- Unit test path flattening produces unique names for files in different directories
- Unit test `resolve_image_to_manifest` rejects paths outside base_dir
- Unit test `resolve_image_to_manifest` handles URL-encoded paths

**Demo:** `pytest tests/test_publish_images.py::TestImageManifest` passes.

---

### Task 2: Implement image reference parsing and rewriting for TextBlocks

**Objective:** Parse `![[filename.ext]]` (Obsidian) and `![alt](path)` (standard markdown) patterns within text content, resolve them against the project file tree, and rewrite to the output-relative path.

**Implementation guidance:**
- Add function `rewrite_image_references(content: str, context: RenderContext) -> str` in `publish.py`
- Regex patterns:
  - Obsidian: `!\[\[([^\]]+)\]\]` — captures filename (may include optional `|alt` after pipe)
  - Standard: `!\[([^\]]*)\]\(([^)]+)\)` — captures alt and path
- **Skip conditions** (leave reference unchanged, no warning):
  - Remote URLs: path starts with `http://`, `https://`, or `//`
  - Non-image extensions in standard syntax (e.g. `![doc](file.pdf)`)
- **Skip conditions** (leave reference unchanged, log warning):
  - Unresolvable file (not found in project)
  - Path escapes `base_dir` (security)
- For Obsidian: search all input record filepaths for a file matching the filename. If found, resolve absolute path, add to manifest, rewrite to `![alt](images/target_name.ext)`. The `alt` comes from the pipe syntax (`![[file.png|caption]]`) or defaults to the file stem.
- For standard markdown: URL-decode the path (`urllib.parse.unquote`), resolve relative to the source file's directory, add to manifest, rewrite path
- Call this function in `render_block()` for TextBlocks (both plain and marked) before returning content
- Do NOT rewrite references inside fenced code blocks (`` ``` ``)

**Test requirements:**
- Test Obsidian `![[diagram.png]]` rewriting with a mock file tree
- Test Obsidian `![[diagram.png|Architecture]]` uses "Architecture" as alt-text
- Test standard `![alt](../assets/fig.png)` rewriting with correct relative resolution
- Test URL-encoded path `![alt](my%20diagram.png)` resolves correctly
- Test remote URL `![logo](https://example.com/logo.png)` is left unchanged (no warning)
- Test unresolvable reference is left unchanged with a logged warning
- Test path traversal `![x](../../../etc/passwd)` is rejected with warning
- Test mixed content with multiple image references
- Test references inside code blocks are not rewritten

**Demo:** Unit test with a TextBlock containing `![[diagram.png]]` produces `![diagram](images/SYS-diagram.png)`.

---

### Task 3: Implement image embed for sidecar image artifacts

**Objective:** When rendering an `ArtifactBlock` whose underlying artifact uses `FileLocation` and the `loc_file` has an image extension, emit a markdown image embed in addition to the metadata table.

**Implementation guidance:**
- In `render_block()` for `ArtifactBlock`, check if `artifact.location` is a `FileLocation` and `loc_file` ends with an image extension
- If so, resolve the image source path from `base_dir / loc_file`, validate path containment, add to manifest, and prepend `![<title or id>](images/<target_name>)\n\n` before the existing metadata rendering
- Define `IMAGE_EXTENSIONS` as a module-level frozenset in `publish_context.py` (shared)
- Respect the existing render config: if a publish config `render` section is defined for the artifact type, add the image embed before the configured sections; otherwise add before the fallback rendering

**Test requirements:**
- Test sidecar artifact with `.png` location emits image embed
- Test non-image sidecar artifact (e.g. `.pdf`) does not emit image embed
- Test image embed uses `title` field as alt-text, falling back to `aid`
- Test path containment check applies to sidecar artifacts too

**Demo:** Publishing the example `obsidian-driver` project produces `system-diagrams.md` with `![System architecture diagram](images/SYS-diagram.png)`.

---

### Task 4: Integrate RenderContext into `render_block_tree` and update function signatures

**Objective:** Wire the `RenderContext` through the rendering pipeline so that `render_block` has access to path resolution and the image manifest.

**Implementation guidance:**
- Modify `render_block_tree(tree, config, multi_record)` to create a `RenderContext` internally and pass it through
- Modify `render_block(block, pub_config)` → `render_block(block, pub_config, context: RenderContext | None = None)`
- Before rendering each `FileRecord`, set `context.source_file_path = file_record.path`
- `render_block_tree` returns `tuple[str, ImageManifest]` instead of just `str`
- Update all callers (in `cli.py` and `test_publish.py`)
- When `context` is None (backward compat for tests), image rewriting is skipped

**Test requirements:**
- Existing tests continue to pass (backward compatibility — provide a default empty context when config is None)
- Integration test: build_block_tree + render_block_tree with a file containing image references produces correct markdown and a populated manifest

**Demo:** `pytest tests/test_publish.py` all green; `pytest tests/test_publish_images.py` integration test passes.

---

### Task 5: Implement image copying in the CLI publish command

**Objective:** After rendering, copy all images from the manifest to `<output_dir>/images/` and ensure the published markdown is self-contained.

**Implementation guidance:**
- In `cli.py`'s `publish` command, after `render_block_tree()` returns `(markdown, manifest)`:
  - Determine the output directory:
    - Single mode: `output_dir = out_p.parent`
    - Separate mode: `output_dir = out_p`
  - If the manifest is non-empty:
    - Create `output_dir / 'images'` directory
    - **Clean existing images:** if the `images/` directory already exists, remove all files within it before copying
    - For each entry in the manifest, copy the source file to `output_dir / target_relative_path` using `shutil.copy2`
    - Log the number of images copied
- Handle missing source files gracefully (log warning, skip — do not crash)
- For separate mode with multiple records, accumulate a combined manifest across all records before copying (avoids redundant copies and ensures cleanup happens once)

**Test requirements:**
- CLI integration test: publish a project with an image reference, verify the image file is copied to `<output_dir>/images/`
- Test missing source image logs warning and doesn't crash
- Test that the markdown content references `images/target_name.png` correctly
- Test that stale images from a previous run are cleaned up
- Test that the same image referenced by two records is only copied once

**Demo:** `uv run syntagmax --cwd ./example/obsidian-driver publish --all` produces `.syntagmax/reports/images/SYS-diagram.png` alongside the markdown files.

---

### Task 6: Pass `--resource-path` to Pandoc for robust DOCX/PDF conversion

**Objective:** Ensure Pandoc can find images when converting the published markdown to DOCX/PDF.

**Implementation guidance:**
- In `pandoc.py`'s `convert()` function, add an optional `resource_path: Path | None = None` parameter
- When provided, add `--resource-path=<path>` to the Pandoc command
- In `cli.py`'s `_run_pandoc_conversion`, pass the output directory (markdown file's parent) as `resource_path`
- This ensures Pandoc resolves `images/SYS-diagram.png` relative to the output directory

**Test requirements:**
- Unit test that `convert()` includes `--resource-path` in the command when provided
- Unit test that `convert()` omits `--resource-path` when not provided (backward compat)

**Demo:** `uv run syntagmax --cwd ./example/obsidian-driver publish --all --docx` produces a DOCX file without image resolution errors.

---

### Task 7: Add example with image references and update documentation

**Objective:** Add an image reference to the example project and update README/reference docs.

**Implementation guidance:**
- Add `![[diagram.png]]` to `example/obsidian-driver/SYS/SYS-001.md` (in the Rationale section) to demonstrate inline image embedding
- Regenerate the example publish output (committed to repo)
- Update `docs/reference/publishing.md` with a section on image handling:
  - Supported syntaxes (`![[filename]]` and `![alt](path)`)
  - Remote URLs are left as-is (not downloaded)
  - Image copying behaviour (self-contained `images/` subdirectory)
  - Output structure example
  - Path flattening naming convention
  - Security: only images within the project workspace are copied
  - Stale image cleanup behaviour
- Update README publishing section briefly mentioning image support

**Test requirements:**
- Running the example publish command produces correct output with images

**Demo:** `uv run syntagmax --cwd ./example/obsidian-driver publish --all` shows image handling in action.
