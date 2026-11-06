# Syntagmax Application Logic — Publishing Subsystem

> Covers block-tree construction, rendering, heading/path structure, metadata modes, image resolution, plugins, and Pandoc conversion. Source: `publish.py`, `blocks.py`, `publish_context.py`, `pandoc.py`, `publish_config.py`.

## 1. Publish data model

```text
BlockTree
└─ InputBlock(name)
   └─ FileRecord(path)
      └─ Block
         ├─ ArtifactBlock(artifact, raw_text)
         ├─ TextBlock(content, marker, id, explicit_id, source_offset)
         └─ ErrorBlock(message, raw_text)
```

`build_block_tree(config)`:

1. Iterate input records in config order.
2. Instantiate the configured extractor.
3. Sort existing files by path relative to record base.
4. Extract blocks from each file.
5. Store paths relative to project base.
6. Assign deterministic IDs to marked text blocks without explicit IDs:

```text
SHA256(marker + ':' + filepath + ':' + content)[:8]
```

7. Check explicit `(marker, id)` uniqueness; scope is global or per input according to `cross_input_duplicates`.
8. Return tree plus duplicate errors.

## 2. Rendering pipeline

```text
BlockTree
→ record/path headings
→ block renderer
→ image reference rewriting + ImageManifest
→ Markdown plugin transforms
→ output Markdown
→ optional Pandoc conversion
```

`render_block_tree()`:

- loads per-record publish config;
- optionally emits record heading in multi-record mode;
- decomposes file paths into directory/file heading components;
- strips numeric prefixes when configured;
- collapses repeated path prefixes;
- recognizes a file whose stem equals `contents_marker` as headingless body content;
- computes content heading level, capped at six;
- renders each block and normalizes excessive blank lines to two newlines.

## 3. Text block rendering

- `HEADING` marker is treated as unmarked text.
- Unmarked text is omitted when `include_plain_text=false`.
- Otherwise headings are shifted by `start_level` and numeric prefixes may be removed.
- Configured marker render rules are matched case-insensitively.
- Marker sections support `block` and `inline` label modes.
- If no marker rule exists, `_default_marker_` is tried; otherwise raw content is emitted.
- Incompatible section types produce warnings and are skipped.

## 4. Artifact rendering

Lookup order:

1. render rules for exact artifact type, case-insensitive;
2. `_default_` render rules;
3. fallback renderer.

Fallback output:

1. artifact ID heading;
2. `contents` body, with image rewriting;
3. sorted metadata table excluding `id` and `contents`.

Configured artifact sections:

- `TableSection`: rows from named attributes or `_remaining_`.
- `TextSection`: named values as block/inline labeled text.
- `MarkerRenderSection` under artifact config is incompatible and skipped.

Attribute presence:

- `values-only`: omit empty values;
- `all`: include configured values even when empty;
- `mandatory`: include empty values only when metamodel marks them mandatory.
- Without a metamodel, `mandatory` degrades to `values-only` with warning.

`_remaining_` expands the union of actual fields and metamodel attributes, removes explicitly listed attributes plus `id`/`contents`, and sorts case-insensitively.

Values:

- lists join with `, `;
- pipes are escaped;
- newlines become `<br>` in tables;
- values containing angle brackets are wrapped in backticks.

## 5. Heading/path rules

- Source ATX headings are shifted by `start_level - 1`, capped at level 6.
- Numeric prefixes include forms such as `1.2.3 Title`, `1 - Title`, and `1 Title`.
- Record headings appear only when `multi_record=true`.
- File path components are relative to configured record directory and extension is removed.
- Content files named by `contents_marker` emit directory headings but not the file stem.

## 6. Image handling

Supported extensions:

```text
.png .jpg .jpeg .gif .svg .bmp .webp
```

References:

- Obsidian `![[file.ext|alt]]` → resolved by attachment folder first, then filename scan across input files.
- Standard `![alt](relative/path.ext)` → resolved relative to source file.
- Remote `http://`, `https://`, and protocol-relative URLs remain unchanged.
- References inside fenced code remain unchanged.
- Unsafe paths escaping base directory are rejected.
- Missing images remain unchanged and produce warnings.

`ImageManifest`:

- deduplicates by resolved absolute source path;
- flattens relative path components with `-` into `images/<name>`;
- can merge manifests for multi-file output.

CLI copy phase removes stale files directly under output `images/`, then copies existing manifest sources.

## 7. Plugin integration

Publishing calls configured plugins in order:

1. `transform_blocks(tree, config, params)`;
2. optional named `filter_block` pre-filter once per block;
3. render;
4. `transform_markdown(markdown, config, params)`.

Invalid hook types or exceptions are fatal. Plugin discovery/configuration is documented in the Plugins subsystem document.

## 8. Pandoc integration

- `check_pandoc()` checks PATH.
- Conversion command starts with `pandoc source.md -o output`.
- DOCX may add `--reference-doc`; all formats may add `--resource-path`.
- Subprocess timeout: 120 seconds.
- Missing executable, timeout, nonzero status, and truncated stderr return `(False, message)`.
- Markdown remains written before conversion; CLI decides whether conversion failure exits nonzero.
- Template resolution: per-record override → default template → bundled `template.dotm`; explicit `none` disables.

## 9. Publishing invariants

- Block ID errors do not prevent tree construction; CLI displays them before rendering.
- A renderer can produce an empty string for omitted blocks.
- Output formatting is configuration-driven but fallback rendering is always available.
- **`UNVERIFIED`:** exact interactions between multiple transforms that mutate block identity/order require plugin integration coverage.
