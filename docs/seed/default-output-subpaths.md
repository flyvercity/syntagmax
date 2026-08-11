# Default Output Subpaths for Trace and Publish

## Intent

Currently, trace and publish outputs land directly in `output_path/` (default `.syntagmax/outputs/`). This makes the output directory flat and cluttered when multiple commands are used. Organize outputs into dedicated subdirectories by default:

- Trace exports → `<output_path>/trace/`
- Publish outputs → `<output_path>/publish/`
- Reports remain at `<output_path>/report.md` (unchanged)

## Desired Behavior

- `syntagmax trace --child REQ --parent SYS` writes to `<output_path>/trace/trace-REQ-SYS-<date>.csv` by default (instead of `<output_path>/trace-REQ-SYS-<date>.csv`)
- `syntagmax publish --all` writes to `<output_path>/publish/` by default (instead of `<output_path>/`)
- `syntagmax publish --all --single` writes to `<output_path>/publish/published.md` by default
- Explicit `--output <path>` still overrides everything (no change)
- The `analyze` command report stays at `<output_path>/report.md`

## Backward Compatibility

- This is a default-path change only; explicit `--output` is unaffected
- Subdirectories are created automatically if they don't exist
- Document the new defaults in CLI reference and configuration docs

## Follow-up

- Update README examples that reference default output paths
- Update `docs/reference/CLI.md` default columns
- Update `docs/reference/publishing.md` defaults
