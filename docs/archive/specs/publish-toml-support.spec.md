# Specification: TOML Format Support for Publish Configuration

## Problem Statement

Users want to use `publish.toml` as an alternative to `publish.yaml` for the publish configuration file. The system should detect format by file extension, support both in the fallback resolution chain, and error if both formats exist at the same location.

## Requirements

1. If both `publish.yaml` and `publish.toml` exist in the same fallback location, raise a `FatalError`.
2. Per-record `publish` field detects format by file extension (`.toml` → TOML parser, `.yaml`/`.yml` → YAML parser).
3. Both hyphenated keys (`docx-template`) and underscored keys (`docx_template`) work regardless of format (already supported by Pydantic's `populate_by_name=True`).

## Background

- `tomllib` (stdlib) is already used in `config.py` for loading `config.toml`.
- The `PublishConfig` Pydantic model uses `alias` + `populate_by_name=True`, so both naming styles are accepted during validation.
- The fallback resolution in `Config.load_publish_config()` checks 3 locations: project root, `.syntagmax/`, parent `.syntagmax/`.
- Current `load_publish_config()` in `publish_config.py` uses `yaml.safe_load()` exclusively.

## Tasks

### Task 1: Add format-aware parsing to `load_publish_config()`

- **File:** `src/syntagmax/publish_config.py`
- **Objective:** Make `load_publish_config()` detect file extension and use `yaml.safe_load()` for `.yaml`/`.yml` or `tomllib.loads()` for `.toml`.
- **Implementation guidance:**
  - Import `tomllib` at the top of `publish_config.py`.
  - In `load_publish_config()`, check `resolved_path.suffix.lower()` to choose the parser (case-insensitive extension matching).
  - Use `.is_file()` instead of `.exists()` when validating if the path exists (prevents issues with directories of the same name).
  - For unknown extensions, raise a `FatalError` with a descriptive message.
- **Test requirements:**
  - Add `test_load_publish_config_toml_file(tmp_path)` — write a `.toml` file, load it, verify parsing.
  - Add `test_load_publish_config_unknown_extension(tmp_path)` — verify error on `.json` etc.
  - Add `test_load_publish_config_toml_underscore_keys(tmp_path)` — verify `docx_template` works in TOML.
- **Demo:** `load_publish_config(Path('publish.toml'), root)` successfully parses a TOML publish config.

### Task 2: Add dual-format conflict detection helper

- **File:** `src/syntagmax/publish_config.py`
- **Objective:** Create a helper function that checks a directory for both `publish.yaml`/`.yml` and `publish.toml` and errors if both exist, otherwise returns the one that exists (or `None`).
- **Implementation guidance:**
  - Add a function `resolve_publish_file(directory: Path) -> Path | None` in `publish_config.py`.
  - Check for `publish.yaml`, `publish.yml`, and `publish.toml` using `.is_file()`.
  - If both a YAML variant (either `.yaml` or `.yml`) and a TOML variant exist, raise a `FatalError` with a clear message (e.g., "Both publish.yaml and publish.toml found in {directory}. Please use only one.").
  - If one exists, return its full resolved path (e.g., `directory / filename`); if none, return `None`.
- **Test requirements:**
  - `test_resolve_publish_file_yaml_only` — returns full yaml path.
  - `test_resolve_publish_file_yml_only` — returns full yml path.
  - `test_resolve_publish_file_toml_only` — returns full toml path.
  - `test_resolve_publish_file_both_error` — raises FatalError (yaml + toml).
  - `test_resolve_publish_file_yml_and_toml_error` — raises FatalError (yml + toml).
  - `test_resolve_publish_file_neither` — returns None.
- **Demo:** Calling with a directory containing both files raises a clear error.

### Task 3: Update `Config.load_publish_config()` fallback chain

- **File:** `src/syntagmax/config.py`
- **Objective:** Replace hardcoded `publish.yaml` lookups with calls to the new `resolve_publish_file()` helper, supporting both formats at each fallback level.
- **Implementation guidance:**
  - Import `resolve_publish_file` from `publish_config`.
  - For per-record explicit path: keep as-is (extension detection handles it in `load_publish_config`).
  - For fallback locations (root, `.syntagmax/`, parent `.syntagmax/`): use `resolve_publish_file()` to find the file.
  - Pass the full path returned by `resolve_publish_file()` directly to `load_publish_config()`.
- **Test requirements:**
  - Update `test_config_resolution` to add a variant with `.toml` fallback.
  - Add `test_config_resolution_toml_per_record` — per-record `publish = "custom.toml"` works.
  - Add `test_config_resolution_conflict_error` — both formats in same dir raises error.
- **Demo:** A project with `.syntagmax/publish.toml` (and no `.yaml`) loads correctly via the fallback chain.

### Task 4: Update documentation

- **Files:** `docs/reference/publishing.md`, `README.md`
- **Objective:** Document TOML support for publish configuration.
- **Implementation guidance:**
  - In `publishing.md`, rename the section from "publish.yaml Reference" to "Publish Configuration Reference".
  - Note that both `publish.yaml` and `publish.toml` are supported.
  - Update the resolution order to mention both formats and the conflict error.
  - Add a TOML example alongside the existing YAML example.
  - Update per-record `publish` field documentation to show `.toml` extension works.
- **Test requirements:** N/A (documentation only).
- **Demo:** Documentation clearly shows both YAML and TOML config examples.

### Task 5: Verify JSON schema generation

- **File:** `src/syntagmax/cli.py`
- **Objective:** Ensure the CLI `syntagmax schema publish` command remains correct with TOML support.
- **Implementation guidance:**
  - The schema is generated from the Pydantic model and is format-agnostic — no structural changes needed.
  - Verify existing schema tests still pass.
- **Test requirements:** Run existing schema-related tests.
- **Demo:** `syntagmax schema publish` output unchanged (format-agnostic schema).
