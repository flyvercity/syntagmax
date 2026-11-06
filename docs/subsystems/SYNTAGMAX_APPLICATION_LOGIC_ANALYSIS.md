# Syntagmax Application Logic — Analysis Subsystem

> Covers orchestration after configuration: dependency planning, Git revisions, metrics, impact detection, task generation, and report assembly. Source: `src/syntagmax/main.py`, `git_utils.py`, `metrics.py`, `impact.py`, `tasks.py`, `report.py`.

## 1. Pipeline contract

```text
extract
→ build_artifact_map
→ populate_pids
→ build_tree
→ tree (= analyse_tree)
→ metrics

build_artifact_map → populate_revisions
build_tree + populate_revisions → impact
```

- `STEPS` maps internal step names to functions.
- `DEPS` defines prerequisite sets.
- Public targets: `extract`, `tree`, `impact`, `metrics`.
- `get_execution_plan()` walks dependencies backward, filters to the closure, then topologically orders it.
- `process(requested_step, config)` executes the plan once and accumulates errors in one `Report`.
- `--no-git` skips `populate_revisions`.
- Missing required intermediate state (`artifacts_list` or artifact map) raises `FatalError`.
- `ROOT` tree text is rendered only when `--render-tree` is enabled and a root exists.

## 2. Step behavior

### `extract`

- Delegates to configured extractors for every input record.
- Returns a flat artifact list.
- Converts extractor error strings into categorized `ReportError` values.

### `build_artifact_map`

- Key = artifact ID.
- Missing/`<undefined>` IDs produce extraction errors and are excluded.
- Duplicate IDs produce duplicate errors and retain the first map entry.

### `populate_pids`

- Resolves parent-reference fields into `artifact.pids` and `ParentLink` objects.
- Supports multiple values and comma-separated references.
- Reference syntax can include `AID@REVISION`.
- Timestamp-mode links without an explicit revision receive nominal revision `older`.
- Conflicting nominal revisions for the same parent produce a reference error.

### `build_tree` / `tree`

- `build_tree` adds child IDs to referenced parents.
- Artifacts without resolved parents become root children.
- `--suppress-tracing` also promotes artifacts whose parent IDs are all unresolved to root-level nodes.
- Adds a synthetic `ROOT` artifact.
- Traverses descendants to populate ancestor sets and detect circular/deep structures.
- `analyse_tree` validates every non-ROOT artifact; root count must equal one.

### `populate_revisions`

- Uses Git history for each non-ROOT artifact.
- Line locations use `git blame` over the artifact line range.
- File/sidecar locations use the latest commit affecting each file.
- Revision fields: full hash, 7-character hash, commit timestamp, author email.
- Revisions are cached per derived artifact directory/repository.

### `impact`

- Examines every parent link with a resolved parent and revision metadata.
- Timestamp link (`nominal_revision == older`) is suspicious when parent latest timestamp is newer than child latest timestamp.
- Commit link is suspicious when nominal hash differs from parent latest short and long hashes.
- Produces `suspicious_links`, `total_suspicious`, and a filtered suspicious tree.

### `metrics`

- Builds a Polars table from artifacts.
- `requirement_type`, `status_field`, `verify_field`, and `tbd_marker` come from config.
- If no requirements match, adds `Metrics: No requirements found` and returns empty metrics.
- Otherwise returns:
  - `total_requirements`;
  - `requirements_by_status`;
  - percentage without verification field;
  - percentage containing the TBD marker in any field/list item.
- `process()` also calculates per-input metrics when more than one input contributes requirement artifacts.

## 3. Git worktree policy

- `RepoCache` searches upward from each artifact location for a Git repository.
- Dirty repositories add an error unless `allow_dirty_worktree` is set.
- Missing repositories add an error and skip revision extraction.
- `--no-git` skips the entire revision step; consumers may then have no latest revisions.
- `UNVERIFIED`: exact impact/metrics semantics when revisions are absent depend on downstream report and task consumers.

## 4. Impact task generation

When `impact.tasks_enabled` is true:

1. Create task directory.
2. Scan existing Markdown tasks by frontmatter ID/status/revisions.
3. For each suspicious link, derive ID `TASK-IMPACT-{child}-{parent}`.
4. Skip only when both current parent and child revisions equal stored values; status does not prevent regeneration when revisions changed.
5. Select task type from `parent_atype/child_atype` map, fallback `TASK`.
6. Resolve template: record-level → global → built-in `task.j2`.
7. Render and write sanitized task filename.
8. Return `{created, skipped}` summary.

Tasks carry parent/child IDs, types, records, paths, nominal/actual revisions, and short/long revision hashes. Task atypes receive implicit `id`, `contents`, and `status` metamodel definitions when absent.

## 5. Report model

`Report` stores:

- `errors`;
- optional tree text;
- global and per-input metrics;
- impact data;
- task summary;
- report formatting config.

Error categories and canonical order:

```text
extraction → structure → schema → attribute → reference → trace → duplicate
```

Grouping rules:

- Normalize strings into `ReportError` with structure category.
- Group by input record; missing record becomes `Global`.
- Global group first; named inputs alphabetical.
- Categories follow canonical order; unknown categories last.
- Error location may include type, ID, path, and line range.
- `report.path_as_links` enables links; `wiki_links` chooses Obsidian syntax, otherwise Markdown links with URL encoding and line anchors.
- Final Markdown is rendered by `resources/report.j2` with i18n translations.

## 6. Analysis invariants

- Downstream steps consume exact intermediate shapes; changing a step requires checking all consumers.
- Errors are generally accumulated into the report rather than immediately aborting.
- Configuration/model/plugin failures abort before the pipeline is useful.
- `UNVERIFIED`: performance optimizations in comments are not treated as behavior unless tests confirm them.
