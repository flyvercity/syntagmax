# Log Level Option — Implementation Specification

## Problem Statement

Users find `--suppress-warnings` inconvenient. They want a single `--log` global CLI option with levels `debug|info|warning|error|silent` to control console log verbosity. Additionally, `--warnings-as-errors` should follow the same resolution pattern as other global options (configurable via project and global config files, not just CLI).

## Requirements

- Replace `--verbose` flag and `--suppress-warnings` flag with a unified `--log` option accepting: `debug`, `info`, `warning`, `error`, `silent` (keeping `--verbose` and `--suppress-warnings` as deprecated hidden aliases)
- `silent` means no console log output at all; report files are still written
- Log level resolution order: CLI `--log` > project `config.toml` `log_level` > global config `log_level` (resolved via `SYNTAGMAX_HOME/config.toml` or `~/.config/syntagmax/config.toml`) > default `info`
- `--warnings-as-errors` resolution order: CLI dual flag (`--warnings-as-errors/--no-warnings-as-errors`) > project config > global config > default `false`
- `--warnings-as-errors` must function correctly at any log level (including `silent` — warnings are not displayed but still trigger fatal error at exit)
- Deprecate `--verbose` and `--suppress-warnings` flags: `--verbose` maps to `--log debug`, `--suppress-warnings` maps to `--log error`. Both are hidden from `--help` output.
- Provide `SYNTAGMAX_HOME` environment variable to override the global config directory path (default `~/.config/syntagmax/`) for testability and sandbox safety

## Background

- Current CLI defines `--verbose` as a boolean flag in the `rms` group (`cli.py` line 32), toggling between `DEBUG` and `INFO` root logger levels
- `params['verbose']` is checked in `config.py:267` and `extract.py:40` to gate debug output
- `Params` TypedDict in `params.py` has `verbose: bool`
- The `--warnings-as-errors` feature exists on branch `feat-suppress-warnings-and-warnings-as-errors-*`:
  - `WarningsAsErrorsHandler` collects all WARNING-level log records
  - `SuppressWarningsFilter` filters warnings from display
  - `result_callback` raises `FatalError` if warnings were collected and `--warnings-as-errors` is active
  - `_cleanup_logging()` tears down filters/handlers
- Language follows the same resolution pattern: CLI `--lang` > project config `language` > global config `language` > default `'en'`
- `ConfigFile` pydantic model holds project-level config fields with validators
- Global config loaded from `~/.config/syntagmax/config.toml` and merged before project config
- Tests use `CliRunner` from `click.testing`

## Design Decisions

1. **Handler-level filtering** — Display filtering is applied on `RichHandler` only. The root logger level is set to the minimum of the resolved display level and `WARNING` when `warnings_as_errors` is active (ensuring WARNING records always reach the handler), or to the resolved display level when inactive.
2. **`silent` = `CRITICAL + 1`** — Applied to `RichHandler`, not root logger. No console output but all handlers (including `WarningsAsErrorsHandler`) still active.
3. **Deprecated aliases** — `--verbose` and `--suppress-warnings` are retained as hidden CLI options for backward compatibility, mapped internally to `--log debug` and `--log error` respectively. They are excluded from `--help` output.
4. **`--warnings-as-errors` orthogonal to `--log`** — Valid combination: `--log silent --warnings-as-errors` means "show nothing, but fail if any warnings emitted."
5. **Same resolution pattern for both settings** — Consistent with `language`. CLI overrides project config overrides global config overrides default.
6. **Boolean `--warnings-as-errors` in config** — Simple `warnings_as_errors = true` in TOML, not a complex structure. CLI uses dual flag (`--warnings-as-errors/--no-warnings-as-errors`) with `default=None` to allow explicit disabling.
7. **Shared logging module** — `WarningsAsErrorsHandler`, `_cleanup_logging`, and `_configure_log_display` live in a shared module (`syntagmax/log_utils.py`) importable by both `cli.py` and `config.py`, avoiding circular dependencies.
8. **Case-insensitive log level** — `click.Choice` uses `case_sensitive=False`. Pydantic validator normalizes to lowercase via `.lower()` before validation. Users can write `WARNING` or `warning` interchangeably in config files.
9. **Root logger level optimization** — Root logger is not unconditionally set to `DEBUG`. When `warnings_as_errors` is inactive, root logger matches the resolved display level (avoiding unnecessary `LogRecord` creation). When active, root logger is set to `min(resolved_level, WARNING)` to ensure warning records are generated.

## Proposed Solution

### Architecture

```mermaid
graph TD
    A[CLI --log / --warnings-as-errors] --> B{Config resolution}
    B --> C[CLI value if provided]
    B --> D[Project config.toml]
    B --> E[Global ~/.config/syntagmax/config.toml]
    B --> F[Default: info / false]
    
    C --> G[Resolved log_level + warnings_as_errors]
    D --> G
    E --> G
    F --> G
    
    G --> H[Root logger level: resolved level if warnings_as_errors is false, min(resolved_level, WARNING) if true]
    G --> I[RichHandler level: resolved display level]
    G --> J{warnings_as_errors?}
    J -- Yes --> K[Attach WarningsAsErrorsHandler]
    J -- No --> L[No handler]
    
    K --> M[result_callback checks collected warnings]
    M --> N{Any warnings?}
    N -- Yes --> O[FatalError]
    N -- No --> P[Clean exit]
```

### Level Mapping

| `--log` value | RichHandler level | Root logger level (wae=false) | Root logger level (wae=true) | Behavior |
|---------------|-------------------|-------------------------------|------------------------------|----------|
| `debug`       | `DEBUG`           | `DEBUG`                       | `DEBUG`                      | All messages shown |
| `info`        | `INFO`            | `INFO`                        | `INFO`                       | Info and above shown |
| `warning`     | `WARNING`         | `WARNING`                     | `WARNING`                    | Warnings and above shown |
| `error`       | `ERROR`           | `ERROR`                       | `WARNING`                    | Only errors shown (warnings still captured) |
| `silent`      | `CRITICAL + 1`    | `CRITICAL + 1`                | `WARNING`                    | Nothing shown (warnings still captured) |

*wae = warnings_as_errors*

### Config Example

```toml
# In .syntagmax/config.toml or ~/.config/syntagmax/config.toml
log_level = "warning"
warnings_as_errors = true
```

---

## Task Breakdown

### Task 1: Update `Params` TypedDict and `ConfigFile` Model

**Objective:** Add `log_level` and `warnings_as_errors` to `Params` (keeping `verbose` for backward compatibility). Add both fields to `ConfigFile` with validation.

**Implementation:**
- In `params.py`: keep `verbose: bool` (deprecated, used by hidden alias). Add `log_level: NotRequired[str]` and `warnings_as_errors: NotRequired[bool]` using `typing.NotRequired` to preserve test compatibility.
- Define `VALID_LOG_LEVELS = ('debug', 'info', 'warning', 'error', 'silent')` in `params.py`
- In `config.py` `ConfigFile` model: add `log_level: str = Field(default='info', description='Console log verbosity')` with `@field_validator` that normalizes input to lowercase via `.lower()` then checks against `VALID_LOG_LEVELS`
- Add `warnings_as_errors: bool = Field(default=False, description='Treat warnings as fatal errors')`

**Test requirements:**
- `ConfigFile(log_level='debug')` passes validation
- `ConfigFile(log_level='DEBUG')` passes validation (normalized to lowercase)
- `ConfigFile(log_level='Warning')` passes validation (normalized to lowercase)
- `ConfigFile(log_level='banana')` raises `ValidationError`
- `ConfigFile(warnings_as_errors=True)` passes
- Existing tests that instantiate `Params` without `log_level`/`warnings_as_errors` still pass (NotRequired)

**Demo:** Unit tests pass showing validation works for valid and invalid log levels, and case normalization.

---

### Task 2: Replace CLI Flags with `--log` and Integrate `--warnings-as-errors`

**Objective:** Add `--log` option and `--warnings-as-errors` dual flag. Retain `--verbose` and `--suppress-warnings` as deprecated hidden aliases. Implement handler-level filtering via a shared module.

**Implementation:**
- Create `src/syntagmax/log_utils.py` shared module containing:
  - `VALID_LOG_LEVELS` (imported from `params.py`)
  - `WarningsAsErrorsHandler` class (collects WARNING records)
  - `_cleanup_logging()` function (tears down handlers/filters)
  - `_configure_log_display(level_str: str)` helper (maps level string to Python log level, applies to RichHandler)
  - `get_warnings_handler() -> WarningsAsErrorsHandler | None` (returns the active handler if any)
- In `cli.py` `rms` group:
  - Keep `--verbose` as hidden deprecated flag: `@click.option('--verbose', is_flag=True, hidden=True, help='[DEPRECATED] Use --log debug')`
  - Keep `--suppress-warnings` as hidden deprecated flag: `@click.option('--suppress-warnings', is_flag=True, hidden=True, help='[DEPRECATED] Use --log error')`
  - Add `@click.option('--log', 'log_level', type=click.Choice(['debug', 'info', 'warning', 'error', 'silent'], case_sensitive=False), default=None, help='Console log verbosity level')`
  - Add `@click.option('--warnings-as-errors/--no-warnings-as-errors', 'warnings_as_errors', default=None, help='Treat all warnings as fatal errors')`
- In `rms()` body:
  - Map deprecated flags: if `verbose` and no `log_level`, set `log_level = 'debug'`. If `suppress_warnings` and no `log_level`, set `log_level = 'error'`.
  - Determine initial root logger level (default `INFO` before config resolution)
  - Create `RichHandler` with level based on `log_level` (default to `INFO` if None — config resolution happens later in `Config.__init__`)
  - Map `'silent'` to `lg.CRITICAL + 1`
  - Call `lg.basicConfig(level=resolved_root_level, handlers=[handler], force=True)`
  - If `warnings_as_errors` is `True`: attach `WarningsAsErrorsHandler` to root logger
- Add `@rms.result_callback()` that checks `WarningsAsErrorsHandler` (via `get_warnings_handler()`) and raises `FatalError` if warnings collected, then calls `_cleanup_logging()`
- Store `log_level` and `warnings_as_errors` in `ctx.obj` (Params)

**Test requirements:**
- `--log debug` produces debug-level output
- `--log silent` suppresses all console log messages
- `--log silent --warnings-as-errors` still fails if warnings emitted
- `--log error` suppresses info and warning from display
- `--no-warnings-as-errors` overrides config-level `warnings_as_errors = true` to false
- `--verbose` (deprecated) behaves same as `--log debug`
- `--suppress-warnings` (deprecated) behaves same as `--log error`
- `--verbose` and `--suppress-warnings` are not shown in `--help` output

**Demo:** `syntagmax --log silent analyze` writes report with no console log output. `syntagmax --log silent --warnings-as-errors analyze` exits non-zero on warnings. `syntagmax --verbose analyze` still works (deprecated alias).

---

### Task 3: Implement Resolution Order and Early Configuration in `Config._read_config`

**Objective:** During config file loading in `Config._read_config`, re-resolve `log_level` and `warnings_as_errors` following CLI > project > global > default, and reconfigure logging immediately to prevent initial `INFO` log leakage.

**Implementation:**
- In `Config._read_config`, after loading and merging raw TOML config data (and before validating Pydantic models or calling `lg.info`):
  - Support `SYNTAGMAX_HOME` environment override for determining the global config path (`~/.config/syntagmax/config.toml` by default, or `$SYNTAGMAX_HOME/config.toml`).
  - Resolve log level: `resolved_log = self.params.get('log_level') or raw_config.get('log_level') or 'info'`
  - Resolve warnings as errors:
    ```python
    resolved_wae = self.params.get('warnings_as_errors')
    if resolved_wae is None:
        resolved_wae = raw_config.get('warnings_as_errors')
    if resolved_wae is None:
        resolved_wae = False
    ```
  - Store resolved values: `self.params['log_level'] = resolved_log` and `self.params['warnings_as_errors'] = resolved_wae`
  - Reconfigure logging early: update the root logger level and find/update the level of the existing `RichHandler`. If `resolved_wae` is true and `WarningsAsErrorsHandler` is not already attached, attach it.
- Add helper `_configure_log_display(level_str: str)` that maps string to Python log level and applies to RichHandler

**Test requirements:**
- Project config `log_level = "warning"` with no CLI flag → only warnings/errors displayed (early logs like "Using configuration file" are not shown)
- CLI `--log error` overrides project config `log_level = "debug"`
- Project config `warnings_as_errors = true` works without CLI flag
- CLI `--warnings-as-errors` flag overrides config `false`
- Global config fallback works when project config omits the field

**Demo:** Set `log_level = "warning"` in config.toml; run `syntagmax analyze` — only warnings/errors appear in console.

---

### Task 4: Migrate `params['verbose']` Usage Sites

**Objective:** Replace all `params['verbose']` checks with `params.get('log_level') == 'debug'`. The `verbose` key remains in `Params` (for the deprecated alias) but is no longer read directly by business logic.

**Implementation:**
- `config.py:267`: `if self.params['verbose']:` → `if self.params.get('log_level') == 'debug':`
- `extract.py:40`: `if config.params['verbose']:` → `if config.params.get('log_level') == 'debug':`
- Note: `verbose` still exists as a key in `Params` and is set by the hidden deprecated `--verbose` flag. The mapping from `verbose=True` to `log_level='debug'` happens in `rms()` (Task 2). Business logic should only check `log_level`.

**Test requirements:**
- `--log debug` triggers config JSON dump in `Config.__init__`
- `--log debug` triggers raw artifact listing in `extract.py`
- `--log info` does not trigger either

**Demo:** `syntagmax --log debug analyze` shows config dump and raw artifact listing (same as old `--verbose`).

---

### Task 5: Update Documentation

**Objective:** Update README.md and reference docs to reflect the new `--log` option and `warnings_as_errors` config.

**Implementation:**
- In `README.md`:
  - Replace all `--verbose` references with `--log debug`
  - Remove any `--suppress-warnings` references
  - Add section documenting `--log` levels and behavior
  - Document `log_level` and `warnings_as_errors` in config.toml examples
  - Document resolution order (same as language)
- In `docs/reference/configuration.md` (if exists): add `log_level` and `warnings_as_errors` fields
- Update CLI help strings to be clear and concise

**Test requirements:** N/A (documentation only).

**Demo:** README shows `--log` in examples; config.toml reference documents both new fields with resolution order.

---

### Task 6: Integration Tests for Full Resolution Chain

**Objective:** End-to-end tests covering `log_level` and `warnings_as_errors` resolution across CLI, project config, and global config.

**Implementation:**
- Create `tests/test_cli_log_level.py` with:
  - Test: no `--log`, no config → default `info` (root logger DEBUG, handler INFO)
  - Test: project config `log_level = "error"` → handler at ERROR
  - Test: `--log warning` overrides project config `log_level = "debug"`
  - Test: `--log silent` suppresses all output but report written
  - Test: `warnings_as_errors = true` in config → warnings cause exit code 1
  - Test: `--warnings-as-errors` flag overrides config `false`
  - Test: `--log silent --warnings-as-errors` → no output, exits non-zero on warnings
  - Test: `--log debug` shows debug-level messages
  - Test: CLI `--no-warnings-as-errors` overrides config `true`
- Use `CliRunner` with temp directories and generated config files
- Use `caplog` or output inspection to verify log presence/absence
- Mock `SYNTAGMAX_HOME` environment variable to isolate tests from developer's real `~/.config/` directory.

**Test requirements:** All scenarios pass.

**Demo:** Full test suite passes covering all resolution combinations.
