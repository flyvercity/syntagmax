# Syntagmax Application Logic — AI and MCP Subsystem

> Covers AI impact-task verification helpers and the MCP read server. Source: `ai.py`, `cli_ai.py`, `mcp/server.py`, package `resources/agents.yaml` and prompt template.

## 1. Agent registry

- If `config.ai.agents_file` is set, resolve it relative to config root and load YAML.
- Otherwise load packaged `resources/agents.yaml`.
- Registry must contain top-level `agents`; otherwise fatal.
- `resolve_agent()` requires an exact name and reports sorted available names on failure.
- CLI `--command` bypasses registry and creates `{command: pattern, description: ad-hoc command}`.

## 2. Impact task parsing

`parse_impact_task()` requires valid YAML frontmatter and parses:

- `id`;
- `status`;
- `parent_revision`;
- Parent Updated section: ID, Type, File, optional Input Record;
- Child Outdated section: ID, Type, File, optional Input Record.

Missing required structured fields raises `FatalError`. The CLI additionally requires task ID prefix `TASK-IMPACT-` and status `open`.

## 3. Prompt construction

`render_verify_prompt()` loads `ai-verify-impact.j2` and injects:

- configured persona;
- task path;
- parent/child IDs/types/files;
- repository roots and relative paths;
- parent revision;
- agent name;
- current UTC date;
- amendment flag.

## 4. Agent invocation

`invoke_agent()`:

1. Write prompt to a temporary Markdown file.
2. Substitute `{prompt}` in configured command pattern with the temporary path.
3. Split command using platform-aware `shlex` behavior.
4. Resolve executable through `shutil.which` where possible.
5. Run subprocess in configured base directory.
6. Return subprocess exit code.
7. Delete temporary prompt file in `finally`.

Missing executable raises `FatalError`; the subprocess itself is not given shell execution through a shell string.

## 5. Post-edit validation

### Task file

`validate_task_post_edit()` requires:

- readable file;
- valid frontmatter;
- unchanged task ID;
- status `open` or `closed`;
- `## Verification Report` section.

### Child artifact

`validate_child_post_edit()` requires:

- file still exists;
- nonzero size;
- readable content;
- valid frontmatter when content starts with `---`.

It does not perform full metamodel validation. `UNVERIFIED`: whether this lightweight integrity check is sufficient for all drivers.

## 6. CLI verification state machine

```text
validate flags
→ load config/task
→ require TASK-IMPACT-* and open status
→ resolve parent/child paths
→ select agent
→ render prompt
→ invoke agent
→ validate task
→ optional child validation
→ report closed / amended / more work
```

- `--agent` and `--command` are mutually exclusive.
- Custom command must contain `{prompt}`.
- Dirty Git state warns but does not stop verification.
- Nonzero agent exit, invalid task output, or invalid amendment child exits nonzero.
- A valid task that remains non-closed reports “requires more work” without an explicit failure exit in the CLI implementation.

## 7. MCP server initialization

`SyntagmaxMCPServer` creates a `FastMCP` server, default host `127.0.0.1`, port `8000`, SSE path `/`.

Before serving:

1. extract artifacts;
2. build artifact map;
3. populate parent IDs;
4. build tree;
5. run artifact analysis;
6. abort startup if any errors;
7. retain the analyzed artifact map.

## 8. MCP tools

### `list_artifacts`

- Returns Markdown list sorted by artifact ID.
- Omits synthetic `ROOT`.
- Displays type and `title`/`summary` when present.
- Empty map returns `No artifacts loaded.`

### `search_artifacts(query)`

- Lowercases query and searches substring matches in ID, type, and all scalar/list field values.
- Omits `ROOT`.
- Results sorted by ID.
- No match returns a plain no-results message.

### `get_artifact_content(artifact_id)`

Returns Markdown containing:

- artifact ID/type;
- source location;
- latest revision;
- parent links with nominal revisions and suspicious markers;
- sorted children;
- sorted fields excluding `contents` from the field list;
- body in a fenced Content section.

Missing IDs return an explanatory message with the first ten available IDs.

## 9. Transport and status

- `mcp run` selects `stdio` or `sse` transport.
- MCP server is read-only at the exposed tool layer.
- **`UNVERIFIED`:** exact FastMCP transport startup/error behavior and tool-schema serialization are not covered by the inspected focused tests.
