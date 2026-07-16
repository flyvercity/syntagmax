# [x] Task 10: Documentation Updates

## Objective

Update all relevant project documentation to cover the new `change report` command, its options, behavior, and examples.

## Target Files

- `README.md`
- `docs/reference/CLI.md` (create if not exists)

## Dependencies

- **Task 7** (CLI wiring — need final command interface to document accurately)

Can be written in draft form early, finalized after Task 7 is complete.

## Implementation

### README.md Updates

Add a new section after "Tracing Export" (or in a logical position):

```markdown
## Change Reports

Syntagmax can generate change reports comparing artifacts between two Git revisions. Reports analyze changes at the artifact level (added, modified, removed requirements) with attribute-level detail.

### Basic Usage

```bash
# Compare last commit against current HEAD
syntagmax change report --base HEAD~1 --target HEAD

# Compare two tags
syntagmax change report --base v1.2.0 --target v1.3.0

# Compare branches
syntagmax change report --base release --target develop
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--base` | (required) | Base Git revision |
| `--target` | (required) | Target Git revision |
| `--output` | `.syntagmax/reports/change/` | Output directory or `console` for stdout |
| `--include-non-artifact` | off | Include non-artifact text block changes |
| `--single` | off | Generate a single consolidated report |
| `-f, --config-file` | `.syntagmax/config.toml` | Path to config file |

### Supported Revisions

- Commit hash (full or short)
- Tag name
- Branch name
- `HEAD`, `HEAD~N`
- `working` — compare against uncommitted changes

### Output

Reports are generated per input record with filenames:
```
<section>-<base_rev>-to-<target_rev>-<YYYYMMDD>.md
```

Use `--single` to generate one consolidated report across all records.
```

### docs/reference/CLI.md Updates

Document the full `change` command group:

```markdown
## `change` — Change Analysis Commands

### `change report` — Generate Change Report

Generates a Markdown report comparing artifacts between two Git revisions.

#### Synopsis

```bash
syntagmax change report --base <revision> --target <revision> [OPTIONS]
```

#### Options

(full table with all options, defaults, descriptions)

#### Examples

(3-5 practical examples)

#### Output Format

(brief description of report sections)

#### Error Handling

(brief note on fallback behavior)

#### Prerequisites

- Git version >= 2.5
- `.syntagmax/worktrees/` must be in `.gitignore`
```

### Document the `working` Keyword

In both README and reference docs, explain:
- `working` bypasses worktree creation for that revision
- Reads files directly from the current working directory
- Useful for previewing uncommitted changes before committing
- Limitation: uncommitted changes are not stable — results may change if files are modified during execution

## Technical Notes

- Match the existing documentation style (see current README sections for tone/format)
- Use the same table format as other command documentation
- Include links to the spec for deeper details if appropriate
- If `docs/reference/CLI.md` does not exist, check if there's another location for CLI reference (e.g., `docs/reference/commands.md`)

## Test Requirements

- Verify `README.md` mentions the `change report` command
- Verify reference docs cover all command options
- Verify examples in documentation are syntactically correct (could run `syntagmax change report --help` and compare)
- No broken internal links

## Verification

Run `syntagmax change report --help` after implementation and verify the output matches the documented options.
