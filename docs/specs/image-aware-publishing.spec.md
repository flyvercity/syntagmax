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
    I --> J[Collect image in copy manifest]
    J --> K[Rewrite to images/filename in output]
    
    L[CLI publish command] --> M[render_block_tree returns markdown + image manifest]
    M --> N[Copy images to output_dir/images/]
    M --> O[Write markdown]
    O --> P[Pandoc conversion]
```

### Data Model

- `ImageManifest`: accumulates `(source_absolute_path → target_relative_path)` pairs during rendering. Handles filename collisions by prefixing with directory components.
- `RenderContext`: holds `config: Config`, `manifest: ImageManifest`, `source_file_path: str | None` (the current FileRecord.path being rendered). Passed through the rendering pipeline.

### Image Resolution Strategy

- **Obsidian `![[filename.ext]]`**: search all input record filepaths for a file matching the filename. If found, resolve to absolute path via `base_dir`, add to manifest, rewrite to `![alt](images/resolved_name.ext)`.
- **Standard `![alt](path)`**: resolve path relative to the source file's directory (using `context.source_file_path` and `base_dir`), add to manifest, rewrite path to `images/filename.ext`.
- **Sidecar image artifacts**: check `artifact.location.loc_file` extension against image extensions set. If image, emit `![<title or id>](images/<filename>)` before metadata rendering.

### Filename Collision Handling

When two images from different directories have the same filename (e.g. `chapter1/fig.png` and `chapter2/fig.png`), prefix with the parent directory: `chapter1-fig.png`, `chapter2-fig.png`.

### Image Extensions

```python
IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.gif', '.svg', '.bmp', '.webp'})
```

### Output Structure

```
.syntagmax/reports/
├── system-requirements.md
├── software-requirements.md
├── system-diagrams.md
└── images/
    ├── diagram.png
    └── architecture.svg
```

### Return Type Change

`render_block_tree()` returns `tuple[str, ImageManifest]` instead of `str`. All callers updated.

## Task Breakdown

### Task 1: Create `RenderContext` and `ImageManifest` data structures

**Objective:** Introduce a `RenderContext` dataclass that holds the config, base_dir, and an `ImageManifest` accumulator.

**Implementation guidance:**
- Create `src/syntagmax/publish_context.py`
- `ImageManifest` holds a dict mapping `target_relative_path → source_absolute_path`
- `RenderContext` holds: `config: Config`, `manifest: ImageManifest`, `source_file_path: str | None`
- Add helper `resolve_image_to_manifest(image_ref: str, context: RenderContext) -> str` that resolves an image reference, adds it to manifest, returns the rewritten output path (`images/filename.png`)
- Collision handling: when a filename already exists in the manifest with a different source, prefix with parent directory component

**Test requirements:**
- Unit test `ImageManifest.add()` deduplication and collision handling (two images with same filename from different directories)
- Unit test `resolve_image_to_manifest` for both Obsidian and standard syntax

**Demo:** `pytest tests/test_publish_images.py::TestImageManifest` passes.

---

### Task 2: Implement image reference parsing and rewriting for TextBlocks

**Objective:** Parse `![[filename.ext]]` (Obsidian) and `![alt](path)` (standard markdown) patterns within text content, resolve them against the project file tree, and rewrite to the output-relative path.

**Implementation guidance:**
- Add function `rewrite_image_references(content: str, context: RenderContext) -> str` in `publish.py`
- Regex patterns:
  - Obsidian: `!\[\[([^\]]+)\]\]` — captures filename (may include optional `|alt` after pipe)
  - Standard: `!\[([^\]]*)\]\(([^)]+)\)` — captures alt and path; skip non-image extensions
- For Obsidian: search all input record filepaths for a file matching the filename. If found, resolve absolute path, add to manifest, rewrite to `![alt](images/resolved_name.ext)`
- For standard markdown: resolve path relative to the source file's directory (using `context.source_file_path`), add to manifest, rewrite path
- If image cannot be resolved, log a warning and leave the reference unchanged
- Call this function in `render_block()` for TextBlocks (both plain and marked) before returning content
- Do NOT rewrite references inside fenced code blocks (`` ``` ``)

**Test requirements:**
- Test Obsidian `![[diagram.png]]` rewriting with a mock file tree
- Test standard `![alt](../assets/fig.png)` rewriting with correct relative resolution
- Test unresolvable reference is left unchanged with a logged warning
- Test mixed content with multiple image references
- Test references inside code blocks are not rewritten

**Demo:** Unit test with a TextBlock containing `![[diagram.png]]` produces `![diagram](images/diagram.png)`.

---

### Task 3: Implement image embed for sidecar image artifacts

**Objective:** When rendering an `ArtifactBlock` whose underlying artifact uses `FileLocation` and the `loc_file` has an image extension, emit a markdown image embed in addition to the metadata table.

**Implementation guidance:**
- In `render_block()` for `ArtifactBlock`, check if `artifact.location` is a `FileLocation` and `loc_file` ends with an image extension
- If so, resolve the image source path from `base_dir / loc_file`, add to manifest, and prepend `![<title or id>](images/<filename>)\n\n` before the existing metadata rendering
- Define `IMAGE_EXTENSIONS` as a module-level frozenset in `publish_context.py`
- Respect the existing render config: if a publish config `render` section is defined for the artifact type, add the image embed before the configured sections; otherwise add before the fallback rendering

**Test requirements:**
- Test sidecar artifact with `.png` location emits image embed
- Test non-image sidecar artifact (e.g. `.pdf`) does not emit image embed
- Test image embed uses `title` field as alt-text, falling back to `aid`

**Demo:** Publishing the example `obsidian-driver` project produces `system-diagrams.md` with `![System architecture diagram](images/diagram.png)`.

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
  - Determine the output directory (from `out_p.parent` for single mode, or `out_p` for separate mode)
  - Create `<output_dir>/images/` if the manifest is non-empty
  - For each entry in the manifest, copy the source file to the target path using `shutil.copy2`
  - Log the number of images copied
- Handle missing source files gracefully (log warning, skip)
- For `--single` mode, the images directory is alongside the single output file
- For separate mode, each record's images go into the shared `<output_dir>/images/` (since all records output to the same directory)

**Test requirements:**
- CLI integration test: publish a project with an image reference, verify the image file is copied to `<output_dir>/images/`
- Test missing source image logs warning and doesn't crash
- Test that the markdown content references `images/filename.png` correctly

**Demo:** `uv run syntagmax --cwd ./example/obsidian-driver publish --all` produces `.syntagmax/reports/images/diagram.png` alongside the markdown files.

---

### Task 6: Pass `--resource-path` to Pandoc for robust DOCX/PDF conversion

**Objective:** Ensure Pandoc can find images when converting the published markdown to DOCX/PDF.

**Implementation guidance:**
- In `pandoc.py`'s `convert()` function, add an optional `resource_path: Path | None = None` parameter
- When provided, add `--resource-path=<path>` to the Pandoc command
- In `cli.py`'s `_run_pandoc_conversion`, pass the output directory (markdown file's parent) as `resource_path`
- This ensures Pandoc resolves `images/diagram.png` relative to the output directory

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
  - Image copying behaviour (self-contained `images/` subdirectory)
  - Output structure example
  - Collision handling
- Update README publishing section briefly mentioning image support

**Test requirements:**
- Running the example publish command produces correct output with images

**Demo:** `uv run syntagmax --cwd ./example/obsidian-driver publish --all` shows image handling in action.
