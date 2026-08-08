# Code Review: [Fix-Publish]
- **Date**: 2026-08-07
- **Target Branch**: `main`
- **PR**: [#130 More Publish Diagnostics](https://github.com/flyvercity/syntagmax/pull/130)
- **Files Changed**: 2 (`src/syntagmax/config.py`, `tests/test_publish_config.py`)
- **Commit**: `0e4d24a` — feat: add diagnostic warning for misplaced publish configuration

## 1. Architectural & Design Overview

This is a small, well-scoped UX diagnostic on the config-load path. After input records are materialised, `Config._read_config` heuristically detects a common TOML scoping mistake:

> User meant a **global** `publish = "..."` but placed it inside the first `[[input]]` table, so only that record gets the publish config and others silently fall back.

The guard is intentionally conservative:

| Condition | Effect |
|---|---|
| No global `publish` | Required to fire |
| `len(input_records) > 1` | Required (single-record is unambiguous) |
| Exactly **one** record has `publish_config` | Required (all records = intentional per-record) |
| Otherwise | Silent |

That design matches real TOML footguns and avoids spamming valid multi-publish setups. Placement right after `_read_input_records` is correct: records must already carry `publish_config`.

**Overall verdict**: Approve with minor follow-ups. The feature is useful, tests pass (4/4), and blast radius is low. The main correctness concern is the **suggested remediation path**, which can mislead users about path resolution bases.

## 2. Security & Performance Audit

- **Security Concerns**: None. Pure local config inspection; no user input reaches a shell, filesystem write, or network path beyond existing config load. Log message interpolates record name and path already present in the loaded config (no secret leakage pattern).
- **Performance & Scalability**: Negligible — one list comprehension over input records at startup (`O(n)` with tiny `n`).

## 3. Detailed File-by-File Findings

### `src/syntagmax/config.py`

- **[Severity: Medium]** Lines 327–330: Warning remediation suggests reusing the **per-record path string** as a **global** value.

  ```python
  f'move \'publish = "{records_with_publish[0].publish_config}"\' above the first [[input]] section in config.toml.'
  ```

  - **Context**: Documented resolution differs by scope (`docs/reference/publishing.md`):
    - Per-record `publish` → relative to **`base`** (often project root when `base = ".."`).
    - Global `publish` → relative to **config file directory** (typically `.syntagmax/`).
  - The branch’s own tests encode this difference: the “misplaced” fixture writes `publish.yaml` under the **project root**, while the “global OK” fixture writes it under **`.syntagmax/`**.
  - Blindly moving `publish = "publish.yaml"` to the top level can therefore produce a **file-not-found fatal error** (or pick a different file), undoing the diagnostic’s value.
  - **Suggested Fix**: Soften the remediation text and call out the path base change, e.g.:

    ```suggestion
    lg.warning(
        f'Only input record "{records_with_publish[0].name}" has a "publish" field set, '
        f'and no global "publish" is defined. If you intended this to apply to all records, '
        f'move the publish setting above the first [[input]] section in config.toml. '
        f'Note: global paths are relative to the config directory (.syntagmax/), '
        f'while per-record paths are relative to base '
        f'(current value: "{records_with_publish[0].publish_config}").'
    )
    ```

    Optionally compute a relative path from `_root_dir` when the file exists under `base`, and suggest that concrete global path.

- **[Severity: Medium]** Lines 323–331 × `warnings_as_errors`: Legitimate “publish only one of N records” configs will trip this heuristic and **fail hard** when warnings are promoted to errors (CI / strict projects).

  - **Context**: Per-record publish is a first-class, documented feature. The message’s “If you intended…” clause is soft, but `WarningsAsErrorsHandler` is not.
  - **Suggested Fix** (pick one):
    1. Keep warning, but document the false-positive case in `docs/reference/publishing.md`.
    2. Downgrade to `lg.info` / a dedicated diagnostic channel that does not participate in WAE (if such a channel exists or is planned).
    3. Only warn when the sole `publish` sits on the **first** `[[input]]` *and* the path looks like a shared name (`publish.yaml` / `publish.toml`), which correlates more strongly with the TOML footgun.

- **[Severity: Low]** Lines 327–330: User-facing string is plain English, not passed through `syntagmax.i18n._`.

  - **Context**: PR #128 localised many analysis/report errors. Most `lg.warning(...)` call sites remain untranslated today, and `setup_i18n` runs **after** this block (lines 346–350), so `_()` would still be English unless i18n setup is moved earlier.
  - **Suggested Fix**: Accept as tech debt for now; if config diagnostics should be localised later, move `setup_i18n` before diagnostic emission (language is already known from CLI/config_data) and wrap the template.

- **[Severity: Low]** Line 325: Heuristic uses truthiness of `r.publish_config`.

  - **Context**: Empty string would be falsy and skip the warning; pydantic/config loading likely normalises this already. No action required unless empty strings can survive validation.

### `tests/test_publish_config.py`

- **[Severity: Low]** Lines 977–1135: `TestMisplacedPublishWarning` covers the four primary branches well (warn / global OK / all per-record OK / single record OK). All four tests passed locally.
  - **Context**: Good signal for the intended matrix.
  - **Suggested Fix** (optional completeness):
    - Add **2-of-3 records have publish** → expect no warning (partial multi-record intent).
    - Add **WAE interaction** smoke: with `warnings_as_errors`, confirm behaviour is intentional (error vs still warning).
    - Extract shared fixture/helper for the repeated `tmp_path` project scaffolding to cut ~100 lines of duplication.

- **[Severity: Low]** Assertion style matches on `'move' in message and 'publish' in message`.
  - **Context**: Brittle if the remediation wording changes (exactly the Medium finding above). Prefer a stable substring (e.g. `misplaced` / `Only input record`) or a dedicated logger event name if you refine the message.

## 4. Test Coverage & Edge Cases

- **Missing Tests**:
  - Partial coverage: *k of n* records with publish where `1 < k < n`.
  - Interaction with `warnings_as_errors`.
  - Global auto-discovery present (`.syntagmax/publish.yaml` exists) while one record also sets `publish` — today: still warns because global field is unset; behaviour is defensible but worth an explicit decision/test.
- **Edge Cases to Handle**:
  - Path base change when following the remediation (see Medium finding).
  - Record name containing quotes / special characters in the log line (cosmetic).
  - Config loaded with only drivers that never publish — warning still fires on load even if user never runs `publish` (acceptable for config hygiene).

## 5. Actionable Next Steps

- [ ] **(High)** Fix or reword the remediation so it does not imply the per-record path string is valid as a global path without adjustment.
- [ ] **(Medium)** Decide WAE policy for this diagnostic (document, narrow heuristic, or exclude from WAE).
- [ ] **(Low)** Optional tests: 2-of-3 publish, auto-discovery coexistence, stable assertion token.
- [ ] **(Low)** Optional doc note under Global Publish Config in `docs/reference/publishing.md` describing the diagnostic.
- [ ] **(Low / later)** Localise config diagnostics after early `setup_i18n`.

## 6. Summary

| Area | Assessment |
|---|---|
| Intent | Clear, user-valuable, minimal surface area |
| Correctness of detection | Sound heuristic for the TOML footgun |
| Correctness of guidance | Path-base mismatch in suggested fix |
| Tests | Solid happy/negative matrix; small gaps |
| Security / perf | Clean |
| Merge readiness | **Yes**, ideally after rewording the warning message |

No blocking security or runtime defects. Prefer landing the path-guidance fix in this PR if the branch is still open; otherwise track as a fast follow.
