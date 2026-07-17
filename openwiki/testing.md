# Testing Guide

The test suite is broad and is one of the best sources of behavioral truth for this repository. Tests are grouped by feature rather than by internal module, which makes them useful as executable documentation.

## Test areas
- Config and initialization: `tests/test_init.py`, `tests/test_init_cmd.py`, `tests/test_publish_config.py`
- Extraction and drivers: `tests/test_extractors.py`, `tests/test_ipynb_extractor.py`, `tests/test_marked_fragments.py`, `tests/test_multiple_records_same_driver.py`
- Metamodel and validation: `tests/test_metamodel.py`, `tests/test_metamodel_schema_validation.py`, `tests/test_reference_validation.py`, `tests/test_multiplicity_validation.py`, `tests/test_id_validation.py`
- Tree and analysis: `tests/test_dag.py`, `tests/test_impact.py`, `tests/test_report.py`, `tests/test_traces.py`
- Git behavior: `tests/test_git_utils.py`, `tests/test_git_revisions.py`
- Publishing: `tests/test_publish.py`, `tests/test_pandoc.py`, `tests/test_multiple_attributes_e2e.py`
- Plugins: `tests/test_plugin.py`
- MCP: `tests/test_mcp.py`
- Artifact validation and edge cases: `tests/test_artifact_validation.py`, `tests/test_enum_multiple.py`, `tests/test_custom_boolean.py`, `tests/test_hyphen_support.py`, `tests/test_suspicious_tree_marks.py`

## What to run when changing major areas
### Config / init / CLI
Run the init and publish integration tests first, because they exercise the real CLI options and config-file resolution.
Useful targets include `tests/test_init.py`, `tests/test_init_cmd.py`, and the CLI portions of `tests/test_publish.py`.

### Metamodel or validation rules
Run the validation-focused tests, especially `tests/test_metamodel.py`, `tests/test_metamodel_schema_validation.py`, and the edge-case validation files.
These tests capture what the DSL accepts and what should fail fast.

### Publish renderer
Run `tests/test_publish.py`, `tests/test_pandoc.py`, and `tests/benchmark_publish.py`.
The renderer has several interacting defaults: heading levels, plain-text filtering, fallback rendering, and optional Pandoc conversion. Recent changes include:
- **ATX heading splitting** in markdown extraction.
- **Image reference rewriting** for published documents.
- **Configurable table spacing** for improved readability.
- **Attribute presence mode** for filtering artifacts.
- **Case-insensitive field exclusions** for artifact rendering.

### Plugin system
Run `tests/test_plugin.py`.
This suite covers plugin discovery, ordering, disabling, runtime validation, and error handling.

### MCP
Run `tests/test_mcp.py` and the relevant analysis tests that feed it.
The MCP server depends on a fully initialized artifact graph, so failures often originate upstream.

## Change watch-outs
- Many tests rely on temporary directories and real filesystem layout. Small path changes can cascade into multiple fixtures.
- Some behaviors are intentionally fail-fast: invalid metamodels, missing config files, or bad plugin hooks should raise `FatalError`.
- The publish suite often encodes exact output snippets. If you change formatting, update the tests and check whether the README/spec docs also need alignment.
- If a change affects output filenames or defaults, inspect the README and the docs/specs pages for stale references.

## Suggested verification pattern
When making a broad change, run the most specific tests first, then one end-to-end test that crosses the boundary you changed.
For example:
- plugin work → `pytest tests/test_plugin.py`
- publishing work → `pytest tests/test_publish.py tests/test_pandoc.py`
- metamodel work → `pytest tests/test_metamodel.py tests/test_reference_validation.py`
el work → `pytest tests/test_metamodel.py tests/test_reference_validation.py`
