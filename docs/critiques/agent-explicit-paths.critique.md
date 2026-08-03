# Critique Report: Pass Full Filenames and Repo Paths to Agents

**Target Specification:** `docs/specs/agent-explicit-paths.spec.md`  
**Date:** 2026-08-03  
**Verdict:** ⚠️ **PROCEED WITH UPDATES**

---

## Executive Summary

The proposed specification (`docs/specs/agent-explicit-paths.spec.md`) addresses a clear usability and efficiency bottleneck in `syntagmax ai verify`: AI agents struggle or waste turns locating artifact files when given un-segmented paths. By introducing explicit `Relative Path (in repo)` fields in the Jinja2 verification prompt and leveraging input record configuration to map files to git repositories, the proposed feature provides unambiguous path context to agents.

Overall, the design is well-structured and minimizes friction. However, the technical review identified potential runtime failure modes concerning `ValueError` during path relative calculations across drives/symlinks, potential `KeyError` during task parsing for older task formats, and missing cross-platform path normalization assertions (`as_posix()`).

With minor updates to address error handling and path normalization edge cases, this spec is ready for implementation.

---

## Product Lens Findings

### 1a. Problem Validation
- **Clear Problem Definition:** The problem is well-defined. Passing absolute file paths along with git root paths without an explicit relative path forces the AI agent to compute relative paths mentally, leading to navigation delays.
- **Appropriate Scope:** The scope is tightly focused on prompt enhancement and runtime resolution without breaking task file templates or backward compatibility.

### 1b. User Value Assessment
- **Tangible User Value:** Faster prompt interpretation directly improves agent response time and verification success rate.
- **Backwards Compatibility:** The fallback mechanism ensures old tasks (generated without `- **Input Record:**` fields) continue to work seamlessly.

### 1c. Alternative Approaches
- **CLI Workspace Context Injection vs Template Update:** Injecting relative paths into the verification prompt template is the cleanest solution, as it doesn't require modifying the persisted task files on disk.

### 1d. Edge Cases & User Experience
- **Path Formatting (P1):** Mixed slash conventions (`\` on Windows vs `/` on Linux/macOS) in prompts can confuse LLM agents. All relative paths passed to the prompt must be normalized to forward slashes.

### 1e. Success Measurement
- **Observability (P2):** Debug logs should explicitly trace resolved repo roots and relative paths during `syntagmax ai verify --log debug` execution to allow easy troubleshooting.

---

## Engineering Lens Findings

### 2a. Architecture Soundness
- **Safely Parsing Task Metadata (E1):** In `parse_impact_task()`, reading `'Input Record'` from `parent_fields` and `child_fields` must use `.get('Input Record', '')` rather than direct key indexing `parent_fields['Input Record']` to prevent `KeyError` when parsing task files created with legacy templates.

### 2b. Failure Mode Analysis
- **Robust Path Relative Resolution (E2):** `Path.relative_to()` raises `ValueError` if `abs_path` is not a strict subpath of `repo_root` (e.g. across Windows drive letters `C:` vs `D:`, symlinked directories, or when `base_dir` lies outside the git tree). `resolve_artifact_paths()` must catch `ValueError` and fall back gracefully to `abs_path.as_posix()`.

### 2e. Testing Strategy
- **Cross-Platform Normalization Testing (E3):** Task 2 test requirements should explicitly mandate asserting forward-slash formatting (`/`) for `relative_path` across operating systems.

---

## Cross-Lens Insights

### X1: Path Normalization & Graceful Fallbacks
Both Product and Engineering perspectives converge on path normalization and fallback safety. For Product UX, clean forward-slash relative paths ensure consistent agent understanding across OS platforms. For Engineering, wrapping `relative_to()` with `try...except ValueError` and safely parsing frontmatter keys guarantees zero runtime crashes on legacy or unusual directory setups.

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|----|------|----------|----------|---------|------------|
| P1 | Product | 💡 | Edge Cases & UX | Windows backslashes in `Relative Path` may confuse AI models | Enforce `as_posix()` for all relative paths in prompt rendering |
| P2 | Product | 💡 | Success Measurement | Lack of debug log visibility for resolved relative paths | Log resolved `repo_root` and `relative_path` at `DEBUG` level in `cli_ai.py` |
| E1 | Engineering | 🎯 | Failure Modes | `Path.relative_to()` raises unhandled `ValueError` if paths are on different drives or outside repo | Wrap `relative_to()` in `try...except ValueError` and fall back to `abs_path.as_posix()` |
| E2 | Engineering | 🎯 | Architecture | Direct indexing `parent_fields['Input Record']` risks `KeyError` on legacy tasks | Use `parent_fields.get('Input Record', '')` during `ImpactTaskInfo` construction |
| E3 | Engineering | 💡 | Testing Strategy | Task 2 tests do not explicitly verify forward-slash normalization on Windows | Add assertion for forward slashes in `test_resolve_artifact_paths` test suite |

---

## Verdict

⚠️ **PROCEED WITH UPDATES**

The spec is solid and solves the targeted problem effectively. Applying the remediation updates below will resolve potential edge-case crashes and ensure robust cross-platform behavior.

---

## Proposed Remediation (Spec Amendments)

### Amendment 1: Update Requirement 6 (Error Handling & Path Normalization)
In Section **Requirements**, update item 6 and add item 10:
```markdown
6. If the input record name is missing from the task file (backward compatibility with old tasks) or not found in the current config, the system must fall back to the existing `_resolve_repo_path()` git-walk behavior.
10. All relative paths passed to the prompt must be normalized to forward slashes using `.as_posix()`. If `relative_to()` raises a `ValueError` (e.g. cross-drive or outside repo), the helper must fall back gracefully to returning `file_path`.
```

### Amendment 2: Update Task 1 Implementation Guidance
In **Task 1: Extend `ImpactTaskInfo` and `parse_impact_task()`**:
```markdown
- In `parse_impact_task()`, extract "Input Record" safely using `parent_fields.get('Input Record', '')` and `child_fields.get('Input Record', '')` (defaulting to empty string if missing).
```

### Amendment 3: Update Task 2 Implementation Guidance & Tests
In **Task 2: Add `ArtifactPaths` dataclass and `resolve_artifact_paths()` helper**:
```markdown
- Implement `resolve_artifact_paths(config, record_name, file_path)`:
  1. Compute `abs_path = config.base_dir() / file_path`
  2. If `record_name` is non-empty, look up record in `config.input_records()` by name
  3. If found, resolve git repo from `record.record_base` using `git.Repo(search_parent_directories=True)`
  4. Compute `relative_path`: try `abs_path.resolve().relative_to(repo_root).as_posix()`. On `ValueError`, catch exception and fall back to `Path(file_path).as_posix()`.
  5. If lookup fails at any step, fall back: resolve git repo from `abs_path.parent` directly.
```
