# Spec Critique: Log Level Option for CLI and Configuration

- **Target Specification:** [docs/specs/log-level-option.spec.md](docs/specs/log-level-option.spec.md)
- **Date:** 2026-07-27
- **Reviewers:** Antigravity (Product & Engineering Lenses)

---

## Executive Summary

The proposed specification introduces a unified `--log` global CLI option with levels `debug|info|warning|error|silent` to control console log verbosity, replacing the older `--verbose` and `--suppress-warnings` options. It also integrates `warnings_as_errors` into the config-resolution chain (CLI > project config > global config > default).

While the overall direction is highly beneficial for improving logging control, our critique reveals several critical design and architectural risks:
1. **Breaking CLI Changes:** Immediate removal of `--verbose` and `--suppress-warnings` will break existing user scripts and automation.
2. **Circular Dependency:** Updating a global `_warnings_handler` in `cli.py` from `config.py` creates a circular import risk.
3. **Type-Safety/Testing Failures:** Modifying the strict `Params` TypedDict will break dozens of existing unit tests that instantiate `Params` without the new keys.
4. **Test Isolation Violations:** Tests trying to verify the global config resolution chain could overwrite the local user's real configuration file at `~/.config/syntagmax/config.toml`.
5. **Log Leakage UX Issue:** Reconfiguring logging *after* reading config files means the initial configuration-loading logs will always leak at `INFO` level.

We recommend proceeding with updates to keep deprecated CLI flag aliases, implement a shared logging module, make TypedDict fields optional, normalize case sensitivity, optimize root logger levels, and mock global config paths in tests.

**Verdict:** ⚠️ **PROCEED WITH UPDATES**

---

## Product Lens Findings

### 1b. User Value & Compatibility
* **P1: Breaking CLI Changes (Severity: 💡 Recommendation)**
  - *Finding:* The spec proposes removing `--verbose` and `--suppress-warnings` entirely. This will immediately break user scripts, CI/CD integrations, and wrapper tools that rely on these flags.
  - *Suggestion:* Keep `--verbose` and `--suppress-warnings` as deprecated, hidden click options. Map `--verbose` to `--log debug` and `--suppress-warnings` to `--log error` or `--log silent` to ensure a smooth migration path.

### 1d. Edge Cases & User Experience
* **P2: Log Leakage during Config Load (Severity: 💡 Recommendation)**
  - *Finding:* `Config` logs several `INFO` level messages (e.g., `"Using configuration file: ..."` and `"Loading global configuration from ..."`) while reading and merging the configuration files. Since the log level is only resolved and reconfigured *after* config loading is complete, these initial logs will always print, even if the user configured `--log warning` or `--log silent`.
  - *Suggestion:* Extract and apply the log level and warnings-as-errors settings immediately after loading raw TOML dictionaries, before validating the full Pydantic model or printing configuration status logs.

---

## Engineering Lens Findings

### 2a. Architecture Soundness
* **E1: Circular Dependency in Logger State (Severity: 🎯 Must-Address)**
  - *Finding:* `Config.__init__` (in `config.py`) resolves `warnings_as_errors` and attaches the `WarningsAsErrorsHandler`. However, `process_result` (in `cli.py`) needs to access this handler to raise errors. Since `cli.py` imports `config.py`, `config.py` cannot import `cli.py` to update a global helper/reference without causing a circular import.
  - *Suggestion:* Define `WarningsAsErrorsHandler`, `SuppressWarningsFilter`, and helper functions (like `_cleanup_logging` or `get_warnings_handler`) in a separate shared module (e.g., `syntagmax/log_utils.py`) or within `config.py` itself, so both `cli.py` and `config.py` can import them safely.

* **E2: TypedDict Strictness & Type Errors in Tests (Severity: 🎯 Must-Address)**
  - *Finding:* `Params` is a strict `TypedDict`. Adding `log_level` and `warnings_as_errors` as required keys will cause compiler and type-checking errors (e.g., in mypy/pyright) across dozens of existing unit tests that instantiate `Params` with only the old keys.
  - *Suggestion:* Keep `verbose: bool` in the `Params` definition, and specify the new keys as optional using `NotRequired[...]` or change `Params` to inherit from `TypedDict(total=False)`.

* **E3: Boolean Resolution and CLI Overrides (Severity: 💡 Recommendation)**
  - *Finding:* Resolving with `self.params.get('warnings_as_errors') or config_model.warnings_as_errors or False` does not allow disabling `warnings_as_errors` via the CLI if it is enabled in the configuration file.
  - *Suggestion:* Define the CLI option with a dual flag name (e.g., `--warnings-as-errors/--no-warnings-as-errors`), setting `default=None`, and resolve using explicit `is not None` checks.

### 2b. Failure Mode & Test Isolation
* **E4: Test Isolation and Global Config Mocking (Severity: 🎯 Must-Address)**
  - *Finding:* Integration tests verifying the resolution chain will read from and write to the user's local path `~/.config/syntagmax/config.toml`. This risks modifying or deleting the developer's actual configuration file, and may fail in CI environments with restricted file access.
  - *Suggestion:* The codebase should allow overriding the global configuration directory path via an environment variable (e.g., `SYNTAGMAX_HOME`), which tests can mock/patch to point to a temporary directory.

### 2d. Performance & Validation
* **E5: Case-Insensitivity Normalization (Severity: 💡 Recommendation)**
  - *Finding:* String case mismatches (e.g., `DEBUG` or `Debug` vs `debug`) in config files or CLI arguments will trigger validation failures.
  - *Suggestion:* Use `case_sensitive=False` in `click.Choice` and normalize strings via `.lower()` in the Pydantic `@field_validator('log_level')`.

* **E6: Root Logger Level Performance (Severity: 💡 Recommendation)**
  - *Finding:* Setting the root logger to `DEBUG` always creates extra `LogRecord` objects even if `warnings_as_errors` is disabled and the log level is set to `error`, causing minor runtime overhead.
  - *Suggestion:* Set the root logger level to `lg.DEBUG` if `log_level == 'debug'` else `lg.WARNING` (when `warnings_as_errors` is active) or the resolved log level (when `warnings_as_errors` is inactive).

---

## Cross-Lens Synthesis

* **X1: Backward Compatibility (Severity: 🎯 Must-Address)**
  - *Product Perspective:* Prevents breaking existing user shell scripts and automated CLI pipelines.
  - *Engineering Perspective:* Avoids breaking dozens of existing tests that instantiate `Params` with `verbose`.
* **X2: Early Log Normalization (Severity: 💡 Recommendation)**
  - *Product Perspective:* Guarantees a completely silent/error-only CLI experience by suppressing configuration bootstrap messages.
  - *Engineering Perspective:* Normalizes casing and prevents invalid configuration keys from polluting validation traces.

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| P1 | Product | 💡 | Compatibility | Removing `--verbose` and `--suppress-warnings` entirely breaks user workflows. | Retain them as deprecated, hidden click option aliases. |
| P2 | Product | 💡 | UX / Log Leakage | Config load logs leak at `INFO` level before configuration is parsed. | Extract log settings early from raw TOML data and reconfigure before logging starts. |
| E1 | Engineering | 🎯 | Architecture | Circular import between `cli.py` and `config.py` when managing logger state. | Place handlers and helper functions in a shared module. |
| E2 | Engineering | 🎯 | Architecture | Strict `Params` TypedDict changes break existing unit test compiles. | Keep `verbose` and use `NotRequired` or `total=False` for new fields. |
| E3 | Engineering | 💡 | Resolution | Fallback chain prevents overriding config-enabled warnings-as-errors to false in CLI. | Use `--warnings-as-errors/--no-warnings-as-errors` with `default=None` and explicit checks. |
| E4 | Engineering | 🎯 | Testing | Integration tests risk writing to or reading from developer's real `~/.config`. | Implement `SYNTAGMAX_HOME` environment override and mock it during tests. |
| E5 | Engineering | 💡 | Validation | Case mismatches in log level choices trigger validation failures. | Use case-insensitive choice options and `.lower()` normalization in Pydantic validation. |
| E6 | Engineering | 💡 | Performance | Root logger set to `DEBUG` always causes minor runtime log object generation overhead. | Set root logger to resolved level when `warnings_as_errors` is inactive, and `WARNING` or lower when active. |

---

## Verdict & Offer of Remediation

### Verdict: ⚠️ **PROCEED WITH UPDATES**

To address the findings and recommendations, we suggest editing [docs/specs/log-level-option.spec.md](docs/specs/log-level-option.spec.md) with the following updates:

#### Suggested Changes to Specification

1. **Update Problem Statement and Requirements to include compatibility and global path overrides:**
   ```diff
   - - Replace `--verbose` flag and `--suppress-warnings` flag with a unified `--log` option accepting: `debug`, `info`, `warning`, `error`, `silent`
   + - Replace `--verbose` flag and `--suppress-warnings` flag with a unified `--log` option accepting: `debug`, `info`, `warning`, `error`, `silent` (keeping `--verbose` and `--suppress-warnings` as deprecated hidden aliases)
   - - Log level resolution order: CLI `--log` > project `config.toml` `log_level` > global `~/.config/syntagmax/config.toml` `log_level` > default `info`
   + - Log level resolution order: CLI `--log` > project `config.toml` `log_level` > global config `log_level` (resolved via `~/.config/syntagmax/config.toml` or `SYNTAGMAX_HOME/config.toml`) > default `info`
   - - Remove `--verbose` and `--suppress-warnings` flags entirely
   + - Deprecate `--verbose` and `--suppress-warnings` flags, mapping them internally to `--log debug` and `--log error`/`silent` respectively
   ```

2. **Update Proposed Solution (Architecture & Level Mapping) to address root logger levels and shared state:**
   ```diff
   -     G --> H[Root logger: DEBUG always]
   +     G --> H[Root logger: DEBUG if debug level, WARNING if warnings_as_errors, else resolved log level]
   ```

3. **Update Task 1 Guidance to keep `verbose` and support non-strict TypedDict:**
   ```diff
   - - In `params.py`: remove `verbose: bool`, add `log_level: str` and `warnings_as_errors: bool`
   + - In `params.py`: keep `verbose: bool` (deprecated), add `log_level: NotRequired[str]` and `warnings_as_errors: NotRequired[bool]`. Set `total=False` on `Params` or use `NotRequired` to preserve compatibility.
     - Define `VALID_LOG_LEVELS = ('debug', 'info', 'warning', 'error', 'silent')` in `params.py`
     - In `config.py` `ConfigFile` model: add `log_level: str = Field(default='info', description='Console log verbosity')` with `@field_validator` checking against `VALID_LOG_LEVELS`
   +   Normalize input to lowercase in `@field_validator('log_level')`.
   ```

4. **Update Task 2 Guidance to prevent circular import and support deprecated flags:**
   ```diff
   - - Remove `--verbose` and `--suppress-warnings` options from `rms` group
   + - Retain `--verbose` and `--suppress-warnings` options in `rms` group but mark them as deprecated and hidden.
     - Add `@click.option('--log', 'log_level', type=click.Choice(['debug', 'info', 'warning', 'error', 'silent']), default=None, help='Console log verbosity level')`
   - - Add `@click.option('--warnings-as-errors', is_flag=True, default=False, help='Treat all warnings as fatal errors')`
   + - Add `@click.option('--warnings-as-errors/--no-warnings-as-errors', 'warnings_as_errors', is_flag=True, default=None, help='Treat all warnings as fatal errors')`
     - In `rms()` body:
   -   - Set root logger to `DEBUG` always
   +   - Define and import logging classes/helpers (e.g. `WarningsAsErrorsHandler`, `_cleanup_logging`) from a shared module (`syntagmax/log_utils.py` or `config.py`) to avoid circular imports.
   +   - Map `--verbose` to `--log debug` and `--suppress-warnings` to `--log error` if provided.
   ```

5. **Update Task 3 Guidance to resolve config early and support environment overrides:**
   ```diff
   - - In `Config.__init__`, after merging global + project config:
   + - In `Config._read_config`, perform log level resolution and reconfiguration immediately after loading the raw global and project TOML configuration dictionaries, before validating or logging.
   + - Support the `SYNTAGMAX_HOME` environment variable to override the default global config directory location `~/.config/syntagmax/`.
   ```

6. **Update Task 6 Guidance to mock global config directories:**
   ```diff
   - - Use `CliRunner` with temp directories and generated config files
   + - Use `CliRunner` with temp directories and generated config files. Mock `SYNTAGMAX_HOME` environment variable during tests to isolate tests from local system configuration files.
   ```
