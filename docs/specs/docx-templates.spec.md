# Spec: Pandoc DOCX Export Templates

## Problem Statement

The current Pandoc DOCX export uses a plain `pandoc` invocation without any `--reference-doc` template. Users need to apply corporate styling (headers, footers, fonts, margins) to exported Word documents. The default template (`src/syntagmax/resources/template.dotm`) should be applied automatically, but users should be able to override it per input record or disable it entirely.

## Requirements

1. Export DOCX files using a Pandoc `--reference-doc` template
2. Configure templates per input record via `docx-template` section in `publish.yaml`
3. Use `src/syntagmax/resources/template.dotm` as the bundled default template
4. Ensure the default template is included in the Python package distribution
5. If template setting is set to `"none"`, export without a template

## Background

- `pandoc.py` module already exists with `convert(source_md, output_path, output_format)` — currently passes no `--reference-doc` flag
- `publish_config.py` contains the `PublishConfig` Pydantic model loaded from `publish.yaml`
- The `_run_pandoc_conversion` helper in `cli.py` calls `pandoc.convert()` per format without any template context
- Resources are in `src/syntagmax/resources/` and the package is built with Hatch (`hatchling`), which includes the `resources/` directory because it's under the `src/syntagmax` package tree
- The existing `report.py` resolves resources via `Path(__file__).parent / 'resources'`
- `PublishConfig` is loaded per input record via `Config.load_publish_config(record)`

## Proposed Solution

Add a top-level `docx-template` section to `publish.yaml` with:
- `default-template`: path to the default `.dotm`/`.docx` reference doc (relative to the config directory), or `"none"` to disable
- Per-record overrides: keyed by input record name

When no `docx-template` section is present or a record has no override, use the bundled `template.dotm`. The `pandoc.convert()` function gains an optional `reference_doc` parameter. The CLI plumbing resolves the template path per record before calling conversion.

### Configuration Example

```yaml
start_level: 1
docx-template:
  default-template: "templates/corporate.dotm"
  overrides:
    system-requirements: "templates/sys-template.dotm"
    implementation: "none"
```

### Resolution Order

0. CLI option `--docx-template` (if provided, overrides everything else for all records)
1. Per-record override in `docx-template.overrides.<record_name>` if specified:
   - If `"none"`, export without a template.
   - Otherwise, resolve path relative to project config root (`config.toml` directory).
2. `docx-template.default-template` if specified:
   - If `"none"`, export without a template.
   - Otherwise, resolve path relative to project config root.
3. Otherwise (section absent, or config values are omitted/None), use the bundled `template.dotm`

## Task Breakdown

### Task 1: Add `DocxTemplate` model to `publish_config.py`

**Objective:** Extend the publish config YAML schema with a `docx-template` section.

**Implementation guidance:**
- Add a new Pydantic model `DocxTemplate` with:
  - `default_template: str | None = None` (YAML key: `default-template`) — path to default template or `"none"`
  - `overrides: dict[str, str] = {}` — map of record name → template path or `"none"`
- Add `docx_template: DocxTemplate | None = None` (YAML key: `docx-template`) field to `PublishConfig`
- When `docx_template` is `None` (absent from YAML), the caller will use the bundled default

**Test requirements:**
- Unit test: parsing a `publish.yaml` with `docx-template` section produces correct model values
- Unit test: absent `docx-template` section results in `None`
- Unit test: `"none"` values are preserved as strings

**Demo:** `uv run pytest tests/test_publish_config.py` passes with new template config tests.

### Task 2: Add `reference_doc` parameter to `pandoc.convert()`

**Objective:** Allow passing a `--reference-doc` argument to the Pandoc subprocess.

**Implementation guidance:**
- Add optional parameter `reference_doc: Path | None = None` to `convert()`
- If `reference_doc` is not None, append `['--reference-doc', str(reference_doc)]` to the `cmd` list
- Only apply `--reference-doc` when `output_format == 'docx'` (it's irrelevant for PDF)

**Test requirements:**
- Unit test: when `reference_doc` is provided and format is `docx`, the subprocess command includes `--reference-doc`
- Unit test: when `reference_doc` is `None`, no `--reference-doc` argument is passed
- Unit test: when format is `pdf`, `--reference-doc` is not passed even if `reference_doc` is provided

**Demo:** `uv run pytest tests/test_pandoc.py` passes with updated tests.

### Task 3: Add template resolution helper function

**Objective:** Create a function that resolves the correct template path for a given record.

**Implementation guidance:**
- Add a function `resolve_docx_template(pub_config: PublishConfig, record_name: str, config_root: Path) -> Path | None` (in `pandoc.py` or a new helper location)
- Resolution logic:
  1. Check `pub_config.docx_template` overrides for `record_name`:
     - If override is `"none"`, return `None`.
     - If a path is specified, resolve relative to `config_root`. If the resolved file does not exist, raise a `FatalError`.
  2. Check `pub_config.docx_template` default-template:
     - If `"none"`, return `None`.
     - If a path is specified, resolve relative to `config_root`. If the resolved file does not exist, raise a `FatalError`.
  3. If no override/default path is defined, return the bundled default path: `Path(__file__).parent / 'resources' / 'template.dotm'`.

**Test requirements:**
- Unit test: absent `docx-template` → returns bundled template path
- Unit test: `default-template` set to a path → resolves relative to config root
- Unit test: per-record override → overrides the default
- Unit test: `"none"` at any level → returns `None`
- Unit test: nonexistent path → raises `FatalError`

**Demo:** `uv run pytest tests/test_pandoc.py` passes.

### Task 4: Wire template resolution into CLI `_run_pandoc_conversion`

**Objective:** Pass the resolved template to `pandoc.convert()` during DOCX export.

**Implementation guidance:**
- Modify `_run_pandoc_conversion` signature to accept an optional `reference_doc: Path | None` parameter.
- Pass `reference_doc` to `pandoc.convert()` when format is `docx`
- Add a new option `--docx-template` to the `publish` command in `cli.py` to allow manual template overrides.
- In the `publish` command body (both single-file and per-record branches):
  - If `--docx-template` CLI option is provided:
    - If it is `"none"`, set template path to `None`.
    - Otherwise, verify it exists (raising `FatalError` if missing) and use it as the template path.
  - Otherwise, load the `PublishConfig` for the record(s) and call `resolve_docx_template()` to get the template path.
  - In `--single` mode:
    - Resolve the template path using the first record.
    - Check if any other selected records have conflicting template resolutions. If so, print a warning to console indicating which template is being applied.
  - Pass the resolved template to `_run_pandoc_conversion()`

**Test requirements:**
- Integration test: CLI with `--docx` invokes `pandoc.convert` with the correct `reference_doc` path
- Integration test: `publish.yaml` with `docx-template.default-template = "none"` → no `--reference-doc` in Pandoc call
- Integration test: per-record override is respected
- Integration test: `--docx-template` CLI option overrides config-based resolution
- Integration test: `--single` with conflicting per-record templates emits a warning

**Demo:** `uv run syntagmax --cwd ./example/obsidian-driver publish --all --docx` uses the bundled template by default.

### Task 5: Ensure bundled template is packaged correctly

**Objective:** Verify that `template.dotm` is included in the built wheel and accessible at runtime.

**Implementation guidance:**
- The file is already at `src/syntagmax/resources/template.dotm` and Hatch includes `src/syntagmax` as a package, so it should be bundled automatically
- Add an explicit check: a test that verifies the resource file exists relative to the module path
- Optionally add `include = ["src/syntagmax/resources/**"]` to the Hatch wheel config if needed (verify first)

**Test requirements:**
- Unit test: `Path(syntagmax.__file__).parent / 'resources' / 'template.dotm'` exists

**Demo:** `uv run python -c "from pathlib import Path; import syntagmax; print((Path(syntagmax.__file__).parent / 'resources' / 'template.dotm').exists())"` prints `True`.

### Task 6: Update documentation and JSON schema

**Objective:** Document the new `docx-template` configuration and regenerate the publish config JSON schema.

**Implementation guidance:**
- Update `README.md` DOCX/PDF section to mention template support and the `docx-template` config
- Add example `publish.yaml` snippet showing `docx-template` usage
- Document the `"none"` keyword behavior
- Run `syntagmax schema publish` to regenerate `docs/schemas/publish-config.schema.json`

**Test requirements:** N/A (documentation).

**Demo:** README and JSON schema reflect the new feature.
