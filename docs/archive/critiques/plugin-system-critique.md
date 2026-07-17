# Spec Critique: Plugin System for Syntagmax

## Executive Summary

The proposed plugin system specification provides a solid foundation for extending the Syntagmax publish pipeline. It supports both local (directory-based) and packaged (entry-points) plugins, which meets the requirement of keeping niche transforms outside the core codebase. 

However, before proceeding to implementation, several key architectural and developer experience issues must be addressed. Specifically, using flat configuration fields for plugin parameters introduces schema collision risks, and a lack of hook return-type validation leaves the pipeline vulnerable to cryptic runtime errors. 

With minor updates to the configuration schema and the inclusion of runtime type validation and trace logging, the specification will be ready for implementation.

**Verdict:** ⚠️ **PROCEED WITH UPDATES**

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| X1 | Both | 🎯 | Pydantic Schema | Flat fields parsed via `model_extra` risk namespace collisions with future core configuration options. | Use an explicit, nested `params` dictionary field in the `[[plugin]]` block configuration. |
| E1 | Engineering | 🎯 | Failure Modes | Hook return types are not validated, which could lead to cryptic crashes deep in the pipeline if a hook returns `None` or incorrect types. | Validate that `transform_blocks` returns a `BlockTree` and `transform_markdown` returns a `str`, raising a clean `FatalError` if they do not. |
| P1 | Product | 💡 | Edge Cases & UX | There is no way to temporarily disable a plugin without deleting or commenting out its config block. | Add an optional `enabled: bool = True` field to the `PluginConfig` model. |
| E2 | Engineering | 💡 | Architecture | Local plugins are restricted to single `.py` files, limiting their ability to organize code or use helper modules. | Support loading local plugins from either a single `{name}.py` file or a directory named `{name}` containing `__init__.py`. |
| E3 | Engineering | 💡 | Operational Readiness | Suppressing or wrapping exceptions without logging the original traceback makes debugging plugin code extremely difficult. | Log the original stack trace of any plugin hook exception at the `DEBUG` level before raising a `FatalError`. |
| E4 | Engineering | 💡 | Architecture | Dynamic loading of local modules without a unique namespace in `sys.modules` can lead to module naming collisions. | Register dynamically loaded local modules in `sys.modules` under a clean namespace, such as `syntagmax.plugins.local.{name}`. |

---

## Product Lens Findings

### Edge Cases & User Experience
* **P1: Plugin Enable/Disable Toggle (Severity: 💡 Recommendation)**
  * *Finding:* Currently, to disable a plugin, a user has to remove or comment out its block from `config.toml`. This is inconvenient, especially for debugging or temporary pipeline adjustments.
  * *Suggestion:* Introduce an `enabled: bool = True` field in `PluginConfig`. If `enabled` is `False`, the loader should skip loading and executing the plugin.

---

## Engineering Lens Findings

### Architecture Soundness
* **X1: Parameter Schema Collisions (Severity: 🎯 Must-Address)**
  * *Finding:* Allowing any extra TOML keys in `[[plugin]]` via `model_extra` to serve as plugin parameters is risky. If Syntagmax later needs to add new fields to `PluginConfig` (like `enabled`, `priority`, or `description`), this will break compatibility with plugins already using those names as parameters.
  * *Suggestion:* Nest all plugin-specific parameters under a dedicated `params` table in `config.toml` (e.g. `[plugin.params]`).
* **E2: Local Plugin Directory Support (Severity: 💡 Recommendation)**
  * *Finding:* Restricting local plugins to a single file (`.syntagmax/plugins/{name}.py`) prevents users from organizing local plugins with multiple files, assets, or utilities.
  * *Suggestion:* Update the loader to support loading local plugins from either a single `{name}.py` file or a folder `{name}/` containing `__init__.py`.
* **E4: Module Namespace Pollution (Severity: 💡 Recommendation)**
  * *Finding:* Loading local Python files directly into Python's module namespace can lead to collisions if two projects or plugins use identical module names.
  * *Suggestion:* Register the dynamically loaded module under a unique path in `sys.modules` (e.g., `syntagmax.plugins.local.{name}`).

### Failure Mode Analysis
* **E1: Return Type Validation for Hooks (Severity: 🎯 Must-Address)**
  * *Finding:* If a plugin hook contains a bug or simply returns `None` or an incorrect type, downstream rendering functions will fail with unhelpful stack traces (e.g. `AttributeError: 'NoneType' object has no attribute...`).
  * *Suggestion:* The plugin execution engine must perform runtime type checks on the return values of hooks:
    * `transform_blocks` must return an instance of `BlockTree`.
    * `transform_markdown` must return an instance of `str`.
    Raise a descriptive `FatalError` if these checks fail.

### Operational Readiness
* **E3: Debug Traceback Logging (Severity: 💡 Recommendation)**
  * *Finding:* Catching plugin exceptions and re-raising them as `FatalError` hides the traceback details of the crash, making it very hard for a plugin developer to locate the line that errored.
  * *Suggestion:* Log the full traceback at `lg.DEBUG` level before raising the `FatalError`.

---

## Cross-Lens Insights

* **Configuration Clarity vs. Future-Proofing (X1):**
  Isolating plugin parameters under a `params` block reduces cognitive load for developers (they know exactly what parameters are being passed to their hook) and guarantees that the core Pydantic configuration schema can grow in the future without breaking user configurations.
* **Fail-Fast Behavior (E1):**
  Validating the return types of plugin hooks immediately upon their completion ensures that pipeline failures are pinned to the offending plugin. This saves time for both users debugging their local plugins and maintainers fielding bug reports.
