# Renumbering Algorithm for Specification Validattion

## Schema Resolution

For each element, it's idenfification schema is resolved, in order of precedence:
- if arfifact's ID contains a template, use it
- if not, metamodel's schema
- otherwise, fallback to `{atype}-{num:3}`


## Maximum Number Extraction

The first pass scans through all affected artifacts:
- if artifact's ID matches the resolved schema, and the schema contains the `{num}` macro, the corresponding sequential number is extracted.
- for each `atype`, the maximum existing sequential number is calculated.

Further renumbering starts from that maximum number, unless `--force` is specified. With `--force`, the renumbering starts from 1 for each `atype`.

## Renumbering

If `--force` is specified, all artifacts are renumbered according to their resolved schema.

Without `--force`, only arfifacts with absent, empty, or templated IDs are renumbered.

## Notes

Any schema can have only one `{num}` macro. If multiple `{num}` macros are detected in DSL, the metamodel loading shall fail. If multiple `{num}` macros are detected for any artifact ID, the renumber command shall fail prior to making any changes.

The `{num:x}` notation denotes padding, not a strict pattern. `REQ-1234` is valid under `REQ-{num:3}` pattern.

The `--schema` CLI option is superfluous and shall be removed.
