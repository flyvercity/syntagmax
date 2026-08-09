# Metamodel DSL Reference

Syntagmax allows defining a custom metamodel for artifacts and their attributes using a simple DSL. This metamodel is used for static validation of requirements and other artifacts.

**Companion VS Code Extension:** [syntagmax-vscode](https://github.com/flyvercity/syntagmax-vscode)

## Example

```model
artifact REQ:
    attribute id is mandatory string
    attribute contents is mandatory string
    attribute parent is optional reference to parent
    attribute status is mandatory enum [draft, active, retired]
    attribute verify is optional string
    attribute priority is mandatory integer
```

The attributes `id` and `contents` are always mandatory for all artifacts, but the type is flexible.

## Syntax Reference

Python-style comments (`# ...`) are supported.

| Rule | Description |
|------|-------------|
| `artifact <NAME>:` | Defines a new artifact type. Rules must be indented. |
| `id is <type> [as <schema>]` | Defines the id attribute and its optional schema. |
| `attribute <ATTR> is <presence> [multiple] <type>` | Defines a general attribute rule. |

**Presence:** `mandatory` or `optional`.

**Modifier:**
- `multiple`: (Optional) Allows an attribute to have multiple values. Multiple values are extracted into a list. If a `multiple` attribute is missing, it defaults to an empty list `[]`.

**Types:**
- `string`: Any text.
- `integer`: A whole number.
- `boolean`: `true` or `false`.
  - **Custom Values**: You can define custom truthy and falsy values: `boolean [true: "yes", "on", false: "no", "off"]`. If custom values are defined, validation becomes exhaustive (standard `true`/`false` will be rejected unless explicitly included). Comparison is case-insensitive.
- `reference [to parent]`: A reference to another artifact (e.g., `SRS-001`). The optional `to parent` modifier marks the attribute as a parent indicator, used for building the artifact hierarchy. 
  - **Nominal Revision**: For "via commit" traces, you can specify a parent's revision using the `@` symbol: `parent: SRS-001@c2d94e4`. This allows for impact analysis to identify if a requirement is outdated relative to its parent.
- `enum [<values>]`: A fixed set of allowed values (comma-separated). Add the optional `multiple` modifier to allow the attribute to have multiple values.

## Multiple Enum Extraction

Multiple values for an enum can be specified by repeating the attribute or by using a comma-separated list in a single attribute:

```
[<
ID = REQ-1
allocation = HW
allocation = SW
>>>
This requirement has multiple allocations.
>]
```

Or:

```
[<
ID = REQ-2
allocation = HW, SW
>>>
This requirement also has multiple allocations.
>]
```

## Examples of Multiple Attributes

Multiple values can be specified by repeating the attribute:

```
[<
ID = REQ-1
tag = security
tag = performance
>>>
This requirement has multiple tags.
>]
```

In this case, `artifact.fields['tag']` will be `['security', 'performance']`.

In Obsidian (YAML):
```yaml
attrs:
  author:
    - Alice
    - Bob
```
This will result in `artifact.fields['author']` being `['Alice', 'Bob']`.

## Trace Modes

Metamodel traces can specify an analysis mode:

```model
trace from REQ to SYS is mandatory via commit
trace from SYS to ARCH is optional via timestamp
```

- `via commit`: Requires specific revision pinning in the artifact (e.g. `parent: SYS-001@c2d94e4`).
- `via timestamp`: Uses modification times to detect potential staleness. Defaults to `older` nominal revision if not specified.

## Impact Analysis Logic

When impact analysis is enabled (`[impact] enabled = true`), Syntagmax performs the following checks:

1. **Via Commit**: If a parent reference includes a revision (e.g., `SRS-001@c2d94e4`), Syntagmax compares it with the parent's actual latest revision. If they differ, the link is marked as suspicious.
2. **Via Timestamp**: If no revision is specified and the metamodel trace mode is `timestamp`, the link is marked as suspicious if the parent was modified later than the artifact.

Suspicious links are highlighted in the artifact tree (printed in yellow) and included in the impact analysis report.

> **Note**: Impact analysis requires a clean git worktree. You can bypass this check using the `--allow-dirty-worktree` flag.
